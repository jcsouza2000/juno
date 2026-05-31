"""
runtime.py - leituras CRUD + execucao de Actions sobre a ontologia.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from .audit import audit_action
from .expressions import ExpressionError, compute_properties, evaluate_bool
from .metrics import time_action, time_call
from .permissions import (
    PermissionDenied,
    build_markings_index,
    can_execute,
    can_read,
    filter_columns,
    get_row_level_filter,
)

if TYPE_CHECKING:
    pass


class ObjectNotFound(Exception):
    """Objeto nao existe OU markings bloqueiam acesso."""


class ValidationFailed(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"Validation failed: {len(errors)} error(s)")


_MODEL_CACHE: dict[str, type] = {}
_HANDLER_CACHE: dict[str, Any] = {}


def _resolve_model(dotted_path: str) -> type:
    if dotted_path in _MODEL_CACHE:
        return _MODEL_CACHE[dotted_path]
    module_path, _, class_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    _MODEL_CACHE[dotted_path] = cls
    return cls


def _resolve_handler(dotted_path: str):
    if dotted_path in _HANDLER_CACHE:
        return _HANDLER_CACHE[dotted_path]
    module_path, _, func_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    fn = getattr(module, func_name)
    _HANDLER_CACHE[dotted_path] = fn
    return fn


def _row_to_dict(row, object_type) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for prop_name in object_type.spec.properties:
        out[prop_name] = getattr(row, prop_name, None)
    return out


def _apply_filters(query, model, filters: dict[str, Any]):
    if not filters:
        return query
    for key, value in filters.items():
        if "__" in key:
            field_name, op = key.rsplit("__", 1)
        else:
            field_name, op = key, "eq"
        col = getattr(model, field_name, None)
        if col is None:
            continue
        if op == "eq":
            query = query.filter(col == value)
        elif op == "ne":
            query = query.filter(col != value)
        elif op == "in":
            query = query.filter(col.in_(value or [-1]))
        elif op == "gte":
            query = query.filter(col >= value)
        elif op == "lte":
            query = query.filter(col <= value)
        elif op == "like":
            query = query.filter(col.like(f"%{value}%"))
    return query


def _load_row(object_type_spec, object_id, *, user, db):
    """Carrega a row crua do banco aplicando row-level filter. Sem markings de coluna."""
    model = _resolve_model(object_type_spec.spec.backing.model)
    pk = object_type_spec.spec.backing.primary_key
    pk_col = getattr(model, pk if isinstance(pk, str) else pk[0])
    query = db.query(model).filter(pk_col == object_id)
    query = _apply_filters(query, model, get_row_level_filter(user, object_type_spec))
    return query.first()


# =============================================================================
# Leitura
# =============================================================================


def fetch_by_id(object_type, object_id, *, user, db, registry) -> dict[str, Any]:
    with time_call("fetch_by_id", object_type):
        obj_spec = registry.get_object_type(object_type)
        markings_idx = build_markings_index(registry._marking_sets)

        if not can_read(user, obj_spec, markings_idx):
            raise PermissionDenied(f"sem acesso a ObjectType '{object_type}'")

        row = _load_row(obj_spec, object_id, user=user, db=db)
        if row is None:
            raise ObjectNotFound(f"{object_type} #{object_id}")

        data = _row_to_dict(row, obj_spec)
        if obj_spec.spec.computed_properties:
            data.update(compute_properties(obj_spec.spec.computed_properties, data))
        return filter_columns(user, obj_spec, data, markings_idx)


def list_objects(
    object_type, *, user, db, registry, filters=None, limit=50, offset=0, order_by=None
) -> dict[str, Any]:
    with time_call("list_objects", object_type):
        obj_spec = registry.get_object_type(object_type)
        markings_idx = build_markings_index(registry._marking_sets)

        if not can_read(user, obj_spec, markings_idx):
            raise PermissionDenied(f"sem acesso a ObjectType '{object_type}'")

        model = _resolve_model(obj_spec.spec.backing.model)
        base_query = db.query(model)
        base_query = _apply_filters(base_query, model, get_row_level_filter(user, obj_spec))
        base_query = _apply_filters(base_query, model, filters or {})

        total = base_query.count()

        if order_by:
            col = getattr(model, order_by.lstrip("-"), None)
            if col is not None:
                base_query = base_query.order_by(col.desc() if order_by.startswith("-") else col)

        rows = base_query.offset(offset).limit(limit).all()

        items = []
        for row in rows:
            data = _row_to_dict(row, obj_spec)
            if obj_spec.spec.computed_properties:
                data.update(compute_properties(obj_spec.spec.computed_properties, data))
            items.append(filter_columns(user, obj_spec, data, markings_idx))

        return {"items": items, "total": total, "limit": limit, "offset": offset}


def search_objects(
    object_type, query_text, *, user, db, registry, limit=20
) -> list[dict[str, Any]]:
    obj_spec = registry.get_object_type(object_type)
    title_prop = obj_spec.spec.title_property
    return list_objects(
        object_type,
        user=user,
        db=db,
        registry=registry,
        filters={f"{title_prop}__like": query_text},
        limit=limit,
    )["items"]


def resolve_link(object_type, object_id, link_name, *, user, db, registry):
    obj_spec = registry.get_object_type(object_type)
    link = obj_spec.spec.links.get(link_name)
    if link is None:
        raise KeyError(f"ObjectType '{object_type}' nao tem link '{link_name}'")

    src = fetch_by_id(object_type, object_id, user=user, db=db, registry=registry)
    cardinality = link.cardinality.value
    backing = link.backing

    if cardinality in ("many_to_one", "one_to_one"):
        fk_col = backing.column or f"{link_name}_id"
        target_id = src.get(fk_col)
        if target_id is None:
            return None
        try:
            return fetch_by_id(link.target, target_id, user=user, db=db, registry=registry)
        except ObjectNotFound:
            return None

    if cardinality == "one_to_many":
        target_fk = backing.target_column
        if target_fk is None:
            return []
        result = list_objects(
            link.target,
            user=user,
            db=db,
            registry=registry,
            filters={target_fk: src["id"]},
            limit=200,
        )
        return result["items"]

    if cardinality == "many_to_many":
        return []

    return None


# =============================================================================
# Validation de inputs e regras
# =============================================================================


def _validate_inputs(action_spec, inputs: dict[str, Any]) -> list[dict]:
    """Verifica required/min/max/max_length contra a PropertySpec dos inputs."""
    errors: list[dict] = []
    spec_inputs = action_spec.spec.inputs
    for name, prop in spec_inputs.items():
        present = name in inputs
        if prop.required and not present:
            errors.append({"field": name, "rule": "required", "message": f"'{name}' e obrigatorio"})
            continue
        if not present:
            continue
        v = inputs[name]
        if prop.min is not None:
            try:
                if float(v) < prop.min:
                    errors.append(
                        {
                            "field": name,
                            "rule": "min",
                            "message": f"'{name}' deve ser >= {prop.min}",
                        }
                    )
            except (TypeError, ValueError):
                pass
        if prop.max is not None:
            try:
                if float(v) > prop.max:
                    errors.append(
                        {
                            "field": name,
                            "rule": "max",
                            "message": f"'{name}' deve ser <= {prop.max}",
                        }
                    )
            except (TypeError, ValueError):
                pass
        if prop.max_length is not None and isinstance(v, str) and len(v) > prop.max_length:
            errors.append(
                {
                    "field": name,
                    "rule": "max_length",
                    "message": f"'{name}' excede max_length={prop.max_length}",
                }
            )
    return errors


def _eval_validation_rules(action_spec, context: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Avalia regras de validation. Retorna (errors, warnings)."""
    errors: list[dict] = []
    warnings: list[str] = []
    for rule in action_spec.spec.validation:
        try:
            ok = evaluate_bool(rule.rule, context)
        except ExpressionError as e:
            errors.append(
                {"field": None, "rule": rule.rule, "message": f"regra invalida: {e.detail}"}
            )
            continue
        if ok:
            continue
        # regra falhou
        severity = rule.severity.value if hasattr(rule.severity, "value") else rule.severity
        if severity == "error":
            errors.append({"field": None, "rule": rule.rule, "message": rule.message})
        else:
            warnings.append(rule.message)
    return errors, warnings


# =============================================================================
# Actions
# =============================================================================


class ActionResult:
    def __init__(
        self, *, success, before, after, audit_id, warnings=None, dry_run=False, diff=None
    ):
        self.success = success
        self.before = before
        self.after = after
        self.audit_id = audit_id
        self.warnings = warnings or []
        self.dry_run = dry_run
        self.diff = diff or {}

    def to_dict(self):
        return {
            "success": self.success,
            "before": self.before,
            "after": self.after,
            "audit_id": self.audit_id,
            "warnings": self.warnings,
            "dry_run": self.dry_run,
            "diff": self.diff,
        }


def execute_action(
    action_type: str,
    target_id: Any,
    inputs: dict[str, Any],
    *,
    user,
    db,
    registry,
    dry_run: bool = False,
    actor_type: str = "user",
    confirmed_by: int | None = None,
) -> ActionResult:
    """Wrapper que cronometra e delega para _execute_action_inner."""
    with time_action(action_type, dry_run):
        return _execute_action_inner(
            action_type,
            target_id,
            inputs,
            user=user,
            db=db,
            registry=registry,
            dry_run=dry_run,
            actor_type=actor_type,
            confirmed_by=confirmed_by,
        )


def _execute_action_inner(
    action_type: str,
    target_id: Any,
    inputs: dict[str, Any],
    *,
    user,
    db,
    registry,
    dry_run: bool = False,
    actor_type: str = "user",
    confirmed_by: int | None = None,
) -> ActionResult:
    """
    Executa uma Action com validacao + autorizacao + audit + transacao.

    Fluxo:
      1. Resolve ActionType + target ObjectType
      2. Authorization (roles + markings + require_confirmation se IA)
      3. Carrega target (com row-level filter)
      4. Valida inputs (PropertySpec) + regras asteval (no contexto target + inputs)
      5. Audit START (cursor com before snapshot)
      6. Chama handler (handler muta target)
      7. Audit COMMIT (after snapshot + persiste em audit_logs)
      8. Em dry_run: rollback. Caso contrario, db.flush() (commit fica para o caller).

    Args:
        actor_type: 'user' (default) | 'ai_coordinator' | 'system'
        confirmed_by: para Actions propostas por IA, id do user humano que confirmou

    Raises:
        KeyError: action ou target_type nao existe
        ObjectNotFound: target nao existe / sem acesso
        PermissionDenied: sem role/marking
        ValidationFailed: input ou regra falhou
    """
    action_spec = registry.get_action_type(action_type)
    target_type = action_spec.spec.target
    obj_spec = registry.get_object_type(target_type)

    # 1. Authorization
    is_ai = actor_type == "ai_coordinator"
    if not can_execute(user, action_spec, is_ai_actor=is_ai, confirmed_by=confirmed_by):
        raise PermissionDenied(
            f"sem permissao para '{action_type}' "
            f"(role={user.role}, markings={user.markings_granted})"
        )

    # 2. Carrega target
    target_row = _load_row(obj_spec, target_id, user=user, db=db)
    if target_row is None:
        raise ObjectNotFound(f"{target_type} #{target_id}")

    target_data = _row_to_dict(target_row, obj_spec)
    if obj_spec.spec.computed_properties:
        target_data.update(compute_properties(obj_spec.spec.computed_properties, target_data))

    # 3. Valida inputs (PropertySpec)
    errors = _validate_inputs(action_spec, inputs)
    if errors:
        raise ValidationFailed(errors)

    # 4. Avalia regras de validation
    eval_context = {**target_data, **inputs}
    rule_errors, rule_warnings = _eval_validation_rules(action_spec, eval_context)
    if rule_errors:
        raise ValidationFailed(rule_errors)

    # 5. Audit + execucao + rollback se dry_run
    handler = _resolve_handler(action_spec.spec.effect.handler)

    savepoint = db.begin_nested()  # SAVEPOINT — permite rollback parcial em dry_run
    try:
        with audit_action(
            db=db,
            user=user,
            action=action_spec,
            target_type=target_type,
            target_id=target_id,
            inputs=inputs,
            actor_type=actor_type,
            confirmed_by=confirmed_by,
            dry_run=dry_run,
        ) as cur:
            # warnings de regras (severity=warning) entram no cursor
            for w in rule_warnings:
                cur.add_warning(w)

            cur.set_before(target_data)
            handler(target_row, inputs, db=db, user=user, cursor=cur)
            db.flush()  # garante que mutacoes batem no DB para o snapshot after

            # Recarrega depois do flush
            after_data = _row_to_dict(target_row, obj_spec)
            if obj_spec.spec.computed_properties:
                after_data.update(compute_properties(obj_spec.spec.computed_properties, after_data))
            cur.set_after(after_data)

        # ao sair do with: audit foi persistido (se nao dry_run)
        if dry_run:
            savepoint.rollback()
            return ActionResult(
                success=True,
                before=target_data,
                after=cur._after,
                audit_id=None,
                warnings=cur._warnings,
                dry_run=True,
                diff=cur.diff(),
            )

        savepoint.commit()
        return ActionResult(
            success=True,
            before=target_data,
            after=cur._after,
            audit_id=cur.audit_id,
            warnings=cur._warnings,
            dry_run=False,
            diff=cur.diff(),
        )

    except Exception:
        savepoint.rollback()
        raise
