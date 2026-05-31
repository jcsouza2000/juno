"""
markings_api.py - endpoints REST para gestao de grants de markings.

Rotas (admin-only, exceto /me):
  GET    /api/v1/markings                  - lista markings declaradas no _markings.yaml
  GET    /api/v1/markings/me               - grants do usuario logado
  GET    /api/v1/markings/grants           - lista grants (filtros user_id, marking)
  POST   /api/v1/markings/grants           - cria grant
  DELETE /api/v1/markings/grants/{id}      - revoga grant
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.services.marking_grants import (
    MarkingGrantError,
    grant_marking,
    list_active_for_user,
    list_grants,
    revoke_marking,
)

from .registry import registry as _global_registry

router = APIRouter(prefix="/api/v1/markings", tags=["markings"])


# =============================================================================
# Schemas
# =============================================================================


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int
    marking: str
    reason: str | None = None
    valid_until: datetime | None = None


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = None


# =============================================================================
# Helpers
# =============================================================================


def _require_admin(user) -> None:
    role = getattr(user, "role", None)
    if role != "admin" and role != "data_steward":
        raise HTTPException(403, "Apenas admin ou data_steward podem gerenciar markings")


# =============================================================================
# Rotas
# =============================================================================


@router.get("", summary="Lista markings declaradas no _markings.yaml")
def list_markings_definitions() -> dict[str, Any]:
    """Retorna catalogo de markings disponiveis com metadados (enforcement, etc.)."""
    out: dict[str, Any] = {}
    for _ms_name, ms in _global_registry._marking_sets.items():  # noqa: SLF001
        for name, mdef in ms.spec.markings.items():
            enforcement = getattr(mdef.enforcement, "value", mdef.enforcement)
            out[name] = {
                "description": mdef.description,
                "enforcement": enforcement,
                "requires_role": mdef.requires_role,
                "requires_marking_grant": mdef.requires_marking_grant,
            }
    return {"markings": out}


@router.get("/me", summary="Markings concedidos ao usuario logado")
def my_markings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    user_id = getattr(user, "id", None)
    if user_id is None:
        raise HTTPException(401, "User invalido")
    return {
        "user_id": user_id,
        "role": getattr(user, "role", "user"),
        "active_markings": list_active_for_user(db, user_id),
    }


@router.get("/grants", summary="Lista grants (admin-only)")
def list_all_grants(
    user_id: int | None = Query(None),
    marking: str | None = Query(None),
    include_revoked: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    _require_admin(user)
    return list_grants(
        db,
        user_id=user_id,
        marking=marking,
        include_revoked=include_revoked,
        limit=limit,
    )


@router.post("/grants", summary="Concede marking a um usuario", status_code=201)
def post_grant(
    payload: GrantRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    _require_admin(user)

    # Marking deve estar declarado
    all_markings: list[str] = []
    for ms in _global_registry._marking_sets.values():  # noqa: SLF001
        all_markings.extend(ms.spec.markings.keys())
    if payload.marking not in all_markings:
        raise HTTPException(
            400, f"Marking '{payload.marking}' nao esta declarada em nenhum MarkingSet"
        )

    try:
        result = grant_marking(
            db,
            user_id=payload.user_id,
            marking=payload.marking,
            granted_by=user.id,
            reason=payload.reason,
            valid_until=payload.valid_until,
        )
    except MarkingGrantError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.delete("/grants/{grant_id}", summary="Revoga um grant")
def delete_grant(
    grant_id: int,
    payload: RevokeRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    _require_admin(user)
    try:
        result = revoke_marking(
            db,
            grant_id=grant_id,
            revoked_by=user.id,
            reason=payload.reason if payload else None,
        )
    except MarkingGrantError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result
