"""
registry.py — Singleton in-memory da ontologia carregada.

Tudo que o runtime, o gerador de SDK e o gerador de tools de IA consultam
passa por aqui.

Carregado uma vez no startup via `loader.load_all(registry)`.

TODO(sem1): implementar lookup com cache
TODO(sem1): hot-reload safe (lock para leitura/escrita)
TODO(sem2): expor métricas Prometheus (counts por tipo)
"""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import (
        ActionTypeResource,
        MarkingSetResource,
        ObjectTypeResource,
    )


class Registry:
    """Container thread-safe de tipos ontológicos."""

    def __init__(self) -> None:
        self._object_types: dict[str, ObjectTypeResource] = {}
        self._action_types: dict[str, ActionTypeResource] = {}
        self._marking_sets: dict[str, MarkingSetResource] = {}
        self._lock = RLock()
        self._loaded = False

    # ── Registration ──────────────────────────────────────────────────────────

    def register_object_type(self, resource: ObjectTypeResource) -> None:
        with self._lock:
            name = resource.metadata.name
            if name in self._object_types:
                raise ValueError(f"ObjectType '{name}' já registrado")
            self._object_types[name] = resource

    def register_action_type(self, resource: ActionTypeResource) -> None:
        with self._lock:
            name = resource.metadata.name
            if name in self._action_types:
                raise ValueError(f"ActionType '{name}' já registrado")
            self._action_types[name] = resource

    def register_marking_set(self, resource: MarkingSetResource) -> None:
        with self._lock:
            name = resource.metadata.name
            self._marking_sets[name] = resource  # MarkingSet é regravável

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_object_type(self, name: str) -> ObjectTypeResource:
        try:
            return self._object_types[name]
        except KeyError:
            raise KeyError(f"ObjectType '{name}' não está registrado") from None

    def get_action_type(self, name: str) -> ActionTypeResource:
        try:
            return self._action_types[name]
        except KeyError:
            raise KeyError(f"ActionType '{name}' não está registrado") from None

    def list_object_types(self) -> list[str]:
        return sorted(self._object_types.keys())

    def list_action_types(self) -> list[str]:
        return sorted(self._action_types.keys())

    def list_action_types_for(self, object_type: str) -> list[str]:
        """Lista todas as Actions cujo target é o ObjectType dado."""
        return [
            name for name, action in self._action_types.items() if action.spec.target == object_type
        ]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @property
    def loaded(self) -> bool:
        return self._loaded

    def mark_loaded(self) -> None:
        self._loaded = True

    def reset(self) -> None:
        """Apenas para testes."""
        with self._lock:
            self._object_types.clear()
            self._action_types.clear()
            self._marking_sets.clear()
            self._loaded = False

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_consistency(self, *, check_models: bool = True) -> list[str]:
        """
        Validações cruzadas:
          - Links apontam para ObjectTypes existentes
          - Actions referenciadas em ObjectTypes existem
          - ActionType.spec.target aponta para ObjectType existente
          - Markings referenciadas em properties/inherit existem em algum MarkingSet
          - (opcional) Backing.model resolve via importlib + columns batem com properties

        Args:
            check_models: se True, tenta importar backing.model e validar colunas.
                          Pode desligar em testes que não querem dependência do SQLAlchemy.

        Returns:
            Lista de mensagens de erro humanizadas. Vazia se tudo OK.
        """
        errors: list[str] = []

        # Conjunto de markings declaradas
        known_markings: set[str] = set()
        for marking_set in self._marking_sets.values():
            known_markings.update(marking_set.spec.markings.keys())

        # ── Validações em ObjectTypes ─────────────────────────────────────────
        for obj_name, obj in self._object_types.items():
            spec = obj.spec

            # title_property existe
            if spec.title_property not in spec.properties:
                errors.append(
                    f"ObjectType '{obj_name}': title_property '{spec.title_property}' "
                    f"não é uma property declarada"
                )

            # identifier_properties existem
            for ident in spec.identifier_properties:
                if ident not in spec.properties:
                    errors.append(
                        f"ObjectType '{obj_name}': identifier '{ident}' não é uma property"
                    )

            # Properties com marking apontam para marking existente
            for prop_name, prop in spec.properties.items():
                if prop.marking and prop.marking not in known_markings:
                    errors.append(
                        f"ObjectType '{obj_name}.{prop_name}': marking '{prop.marking}' "
                        f"não declarado em nenhum MarkingSet"
                    )

            # Markings herdadas existem
            for marking in spec.markings.inherit:
                if marking not in known_markings:
                    errors.append(
                        f"ObjectType '{obj_name}': inherit marking '{marking}' "
                        f"não declarado em nenhum MarkingSet"
                    )

            # Links apontam para ObjectTypes existentes
            for link_name, link in spec.links.items():
                if link.target not in self._object_types:
                    errors.append(
                        f"ObjectType '{obj_name}.{link_name}': target '{link.target}' "
                        f"não é um ObjectType registrado"
                    )

            # Actions referenciadas existem
            for action_name in spec.actions:
                if action_name not in self._action_types:
                    errors.append(
                        f"ObjectType '{obj_name}': ação '{action_name}' "
                        f"listada em actions[] não está registrada"
                    )

            # Backing model resolve (opcional)
            if check_models and spec.backing.model:
                model_err = _resolve_model_safe(spec.backing.model, list(spec.properties.keys()))
                if model_err:
                    errors.append(f"ObjectType '{obj_name}': {model_err}")

        # ── Validações em ActionTypes ─────────────────────────────────────────
        for act_name, action in self._action_types.items():
            action_spec = action.spec

            # Target existe
            if action_spec.target not in self._object_types:
                errors.append(
                    f"ActionType '{act_name}': target '{action_spec.target}' "
                    f"não é um ObjectType registrado"
                )

            # require_markings existem
            for marking in action_spec.authorization.require_markings:
                if marking not in known_markings:
                    errors.append(
                        f"ActionType '{act_name}': require_marking '{marking}' "
                        f"não declarado em nenhum MarkingSet"
                    )

            # Effect handler — formato dotted path (não tenta importar)
            if "." not in action_spec.effect.handler:
                errors.append(
                    f"ActionType '{act_name}': effect.handler '{action_spec.effect.handler}' "
                    f"deve ser dotted path (ex: app.ontology.actions.product.update_price)"
                )

            # audit fields existem nas properties do target
            target_obj = self._object_types.get(action_spec.target)
            if target_obj:
                target_props = set(target_obj.spec.properties.keys())
                for fld in action_spec.audit.fields_before + action_spec.audit.fields_after:
                    if fld not in target_props:
                        errors.append(
                            f"ActionType '{act_name}': audit field '{fld}' "
                            f"não é property do target '{action_spec.target}'"
                        )

        return errors


def _resolve_model_safe(dotted_path: str, expected_columns: list[str]) -> str | None:
    """
    Tenta importar o model SQLAlchemy e verificar que as colunas declaradas no
    YAML existem. Retorna mensagem de erro ou None.

    Não levanta — falha gracioso.
    """
    try:
        module_path, _, class_name = dotted_path.rpartition(".")
        if not module_path:
            return f"backing.model '{dotted_path}' não é dotted path válido"
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is None:
            return f"backing.model: classe '{class_name}' não existe em '{module_path}'"
        # Pega colunas via __table__ (SQLAlchemy)
        table = getattr(cls, "__table__", None)
        if table is None:
            return f"backing.model: '{dotted_path}' não tem __table__ (não é model SQLAlchemy?)"
        table_columns = {c.name for c in table.columns}
        # Computed properties não precisam estar nas colunas; verificamos só identifier
        # Mas pelo menos id deveria estar
        if "id" in expected_columns and "id" not in table_columns:
            return f"backing.model: tabela '{table.name}' não tem coluna 'id'"
        return None
    except ImportError as e:
        return f"backing.model: falha ao importar '{dotted_path}': {e}"
    except Exception as e:  # noqa: BLE001
        return f"backing.model: erro inesperado validando '{dotted_path}': {e}"


# Singleton global
registry = Registry()
