"""
Router de gestao de dados do tenant — "Meus dados" + purge controlado.

Endpoints (Fase 0+3 do roadmap):
  GET  /data/{company_id}/inventory  — inventario do que esta depositado.
  POST /data/{company_id}/purge      — exclusao controlada por escopo, com
                                       token de dupla confirmacao.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user, require_admin
from app.core.logger import get_logger
from app.data_management import (
    VALID_SCOPES,
    get_company_data_inventory,
    purge_company_data,
)
from app.database import get_db
from app.models import User

logger = get_logger(__name__)

router = APIRouter(prefix="/data", tags=["Data Management"])


class PurgeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scope: Literal["financial", "erp", "all"] = "all"
    confirmation: str


@router.get("/{company_id}/inventory", summary="Inventario de dados do tenant")
def data_inventory(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lista o que esta depositado para o tenant (contagens, periodos, uploads)."""
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return get_company_data_inventory(db, company_id)


@router.post("/{company_id}/purge", summary="Exclusao controlada de dados do tenant")
def purge_data(
    company_id: int,
    payload: PurgeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Apaga dados de negocio do tenant (financeiro/ERP/tudo), mantendo usuarios,
    vinculos, conexoes ERP e auditoria.

    Exige token de confirmacao igual a ``PURGE-{company_id}`` — uma trava
    deliberada para evitar exclusao acidental.
    """
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    if payload.scope not in VALID_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Escopo invalido. Use um de: {', '.join(VALID_SCOPES)}.",
        )

    expected = f"PURGE-{company_id}"
    if payload.confirmation != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Token de confirmacao invalido. Envie exatamente '{expected}'.",
        )

    deleted = purge_company_data(db, company_id, payload.scope)
    total = sum(deleted.values())

    logger.warning(
        "PURGE executado: company_id=%s scope=%s user_id=%s total_linhas=%s detalhe=%s",
        company_id,
        payload.scope,
        current_user.id,
        total,
        deleted,
    )

    return {
        "status": "purged",
        "company_id": company_id,
        "scope": payload.scope,
        "total_rows_deleted": total,
        "deleted": deleted,
    }
