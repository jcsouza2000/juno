"""
marking_grants.py - service de grant/revoke de markings sensiveis.

Toda operacao grava em audit_logs automaticamente. So' admin (ou role
'data_steward', no futuro) pode operar.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User, UserMarking
from app.ontology.permissions import invalidate_grant_cache


class MarkingGrantError(Exception):
    """Erro de operacao em user_markings."""


# =============================================================================
# Listagem
# =============================================================================


def list_grants(
    db: Session,
    *,
    user_id: int | None = None,
    marking: str | None = None,
    include_revoked: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Lista grants. Pode filtrar por user_id ou marking."""
    q = db.query(UserMarking)
    if user_id is not None:
        q = q.filter(UserMarking.user_id == user_id)
    if marking is not None:
        q = q.filter(UserMarking.marking == marking)
    if not include_revoked:
        q = q.filter(UserMarking.revoked == False)  # noqa: E712
    q = q.order_by(UserMarking.granted_at.desc()).limit(limit)
    return [_serialize(r) for r in q.all()]


def list_active_for_user(db: Session, user_id: int) -> list[str]:
    """Lista nomes de markings ativos (nao revogados, nao expirados) do user."""
    now = datetime.utcnow()
    rows = (
        db.query(UserMarking.marking, UserMarking.valid_until)
        .filter(UserMarking.user_id == user_id)
        .filter(UserMarking.revoked == False)  # noqa: E712
        .all()
    )
    return [m for m, vu in rows if vu is None or vu > now]


# =============================================================================
# Grant / Revoke
# =============================================================================


def grant_marking(
    db: Session,
    *,
    user_id: int,
    marking: str,
    granted_by: int,
    reason: str | None = None,
    valid_until: datetime | None = None,
) -> dict[str, Any]:
    """
    Concede marking a um usuario.

    Idempotente: se ja' existir grant ativo da mesma marking pro mesmo user,
    devolve o existente em vez de criar duplicata.

    Auditoria: insere row em audit_logs.
    """
    # User existe?
    if not db.query(User).filter(User.id == user_id).first():
        raise MarkingGrantError(f"user_id {user_id} nao existe")
    if not db.query(User).filter(User.id == granted_by).first():
        raise MarkingGrantError(f"granted_by {granted_by} nao existe")
    if not marking or len(marking) > 100:
        raise MarkingGrantError("marking invalido")

    # Idempotencia
    existing = (
        db.query(UserMarking)
        .filter(UserMarking.user_id == user_id)
        .filter(UserMarking.marking == marking)
        .filter(UserMarking.revoked == False)  # noqa: E712
        .first()
    )
    if existing is not None:
        return _serialize(existing)

    row = UserMarking(
        user_id=user_id,
        marking=marking,
        granted_by=granted_by,
        granted_at=datetime.utcnow(),
        valid_until=valid_until,
        reason=reason,
        revoked=False,
    )
    db.add(row)
    db.flush()

    _audit(db, granted_by, "grant_marking", row, extra={"reason": reason})
    invalidate_grant_cache(user_id)
    return _serialize(row)


def revoke_marking(
    db: Session,
    *,
    grant_id: int,
    revoked_by: int,
    reason: str | None = None,
) -> dict[str, Any]:
    """Revoga um grant. Mantem row no banco com revoked=True (auditoria)."""
    row = db.query(UserMarking).filter(UserMarking.id == grant_id).first()
    if row is None:
        raise MarkingGrantError(f"grant {grant_id} nao existe")
    if row.revoked:
        raise MarkingGrantError(f"grant {grant_id} ja' revogado")
    if not db.query(User).filter(User.id == revoked_by).first():
        raise MarkingGrantError(f"revoked_by {revoked_by} nao existe")

    row.revoked = True
    row.revoked_at = datetime.utcnow()
    row.revoked_by = revoked_by
    db.flush()

    _audit(db, revoked_by, "revoke_marking", row, extra={"reason": reason})
    invalidate_grant_cache(row.user_id)
    return _serialize(row)


# =============================================================================
# Helpers
# =============================================================================


def _serialize(row: UserMarking) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "marking": row.marking,
        "granted_by": row.granted_by,
        "granted_at": row.granted_at.isoformat() if row.granted_at else None,
        "valid_until": row.valid_until.isoformat() if row.valid_until else None,
        "reason": row.reason,
        "revoked": row.revoked,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "revoked_by": row.revoked_by,
    }


def _audit(db: Session, actor_id: int, action: str, row: UserMarking, extra=None):
    details = {
        "grant_id": row.id,
        "target_user_id": row.user_id,
        "marking": row.marking,
        **(extra or {}),
    }
    company_id = _resolve_company_id(db, row.user_id, actor_id)
    if company_id is None:
        return

    log = AuditLog(
        company_id=company_id,
        user_id=actor_id,
        action=action,
        resource_type="user_markings",
        resource_id=row.id,
        new_values=json.dumps(details, default=str, ensure_ascii=False),
        success=True,
        severity="info",
    )
    db.add(log)
    db.flush()


def _resolve_company_id(db: Session, user_id: int, actor_id: int) -> int | None:
    for candidate_id in (user_id, actor_id):
        user = db.get(User, candidate_id)
        if user and user.companies:
            return user.companies[0].id
    return 1
