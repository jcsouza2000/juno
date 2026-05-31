"""
audit.py - auditoria automatica de Actions.

Integra com app.models.AuditLog existente. Cada Action gera 1 row com:
  - action: nome da Action (ex: 'atualizarPreco')
  - source_table: ObjectType target (ex: 'Produto')
  - details: JSON com target_id, before, after, inputs, actor_type,
             confirmed_by, dry_run, warnings, status
  - user_id, user_name: ator (humano ou ai_coordinator)
  - created_at: timestamp utc

Uso:
    with audit_action(db=db, user=user_ctx, action=spec, target_id=10, inputs={...}) as cur:
        cur.set_before(load_target())
        ... executa handler ...
        cur.set_after(load_target())
    # ao sair do with -> persiste em audit_logs com status='committed'
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class AuditCursor:
    """Mantem estado before/after/extra durante a execucao da Action."""

    def __init__(self):
        self.audit_id: int | None = None
        self._before: dict[str, Any] = {}
        self._after: dict[str, Any] = {}
        self._extra: dict[str, Any] = {}
        self._status: str = "pending"
        self._warnings: list[str] = []

    def set_before(self, snapshot: dict[str, Any]) -> None:
        self._before = dict(snapshot)

    def set_after(self, snapshot: dict[str, Any]) -> None:
        self._after = dict(snapshot)

    def add_context(self, key: str, value: Any) -> None:
        self._extra[key] = value

    def add_warning(self, msg: str) -> None:
        self._warnings.append(msg)

    def diff(self) -> dict[str, dict[str, Any]]:
        """{field: {'before': X, 'after': Y}} para campos que mudaram."""
        changed: dict[str, dict[str, Any]] = {}
        for k in set(self._before) | set(self._after):
            b, a = self._before.get(k), self._after.get(k)
            if b != a:
                changed[k] = {"before": b, "after": a}
        return changed


def _user_name_from(user) -> str:
    """Extrai um identificador legivel do user/UserContext."""
    if hasattr(user, "user_id") and user.user_id is not None:
        return f"user:{user.user_id}"
    return getattr(user, "email", None) or getattr(user, "full_name", None) or "anonymous"


@contextmanager
def audit_action(
    *,
    db,
    user,
    action,
    target_type: str,
    target_id: Any,
    inputs: dict[str, Any],
    actor_type: str = "user",
    confirmed_by: int | None = None,
    dry_run: bool = False,
) -> Iterator[AuditCursor]:
    """
    Context manager que:
      1. cria cursor
      2. cede para o handler popular before/after
      3. ao sair sem exception: persiste row 'committed' em audit_logs (se nao dry_run)
      4. ao sair COM exception: persiste row 'failed' em audit_logs (se nao dry_run)

    Em dry_run, nada e' persistido — apenas o cursor com diff e' retornado.
    """
    cur = AuditCursor()
    try:
        yield cur
        cur._status = "committed"
    except Exception:
        cur._status = "failed"
        # Persiste tentativa falha tambem (forensics), exceto em dry_run
        if not dry_run:
            _persist(
                db,
                user,
                action,
                target_type,
                target_id,
                inputs,
                cur,
                actor_type=actor_type,
                confirmed_by=confirmed_by,
                dry_run=False,
            )
        raise

    if dry_run:
        return  # nada a persistir

    cur.audit_id = _persist(
        db,
        user,
        action,
        target_type,
        target_id,
        inputs,
        cur,
        actor_type=actor_type,
        confirmed_by=confirmed_by,
        dry_run=False,
    )


def _persist(
    db, user, action, target_type, target_id, inputs, cur, *, actor_type, confirmed_by, dry_run
) -> int | None:
    """Insere row em audit_logs. Retorna id."""
    from app.models import AuditLog  # import lazy para evitar ciclos no startup

    details = {
        "ontology_action": action.metadata.name,
        "target_type": target_type,
        "target_id": target_id,
        "inputs": _safe_serialize(inputs),
        "before": _safe_serialize(cur._before),
        "after": _safe_serialize(cur._after),
        "diff": _safe_serialize(cur.diff()),
        "extra_context": _safe_serialize(cur._extra),
        "actor_type": actor_type,
        "confirmed_by": confirmed_by,
        "dry_run": dry_run,
        "warnings": cur._warnings,
        "status": cur._status,
    }

    company_id = getattr(user, "company_id", None)
    if company_id is None:
        company_ids = getattr(user, "company_ids", None)
        if company_ids:
            company_id = company_ids[0]
    if company_id is None:
        company_id = details.get("after", {}).get("company_id") or details.get("before", {}).get(
            "company_id"
        )
    if company_id is None:
        return None

    row = AuditLog(
        company_id=company_id,
        user_id=getattr(user, "user_id", None),
        action=action.metadata.name,
        resource_type=target_type,
        resource_id=target_id,
        old_values=json.dumps(details.get("before"), default=str, ensure_ascii=False),
        new_values=json.dumps(details, default=str, ensure_ascii=False),
        success=cur._status == "committed",
        severity="info" if cur._status == "committed" else "warning",
    )
    db.add(row)
    db.flush()  # garante id sem fechar transacao
    return row.id


def _safe_serialize(obj: Any) -> Any:
    """Converte recursivamente para algo JSON-serializavel."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    # datetime, Decimal, etc -> string
    return str(obj)
