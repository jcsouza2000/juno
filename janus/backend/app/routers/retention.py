"""
Router de retencao / fechamento mensal (Fase 5).

Endpoints sob /retention/{company_id}:
  POST /monthly-close            — cria o fechamento imutavel de (year, month).
  GET  /monthly-close            — lista fechamentos do tenant.
  GET  /monthly-close/{year}/{month} — recupera um fechamento com snapshot.

Autorizacao: leitura exige acesso ao tenant; criacao exige admin do tenant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.core.logger import get_logger
from app.database import get_db
from app.models import User
from app.services import retention as svc
from app.services.tenant_members import is_tenant_admin

logger = get_logger(__name__)

router = APIRouter(prefix="/retention", tags=["Retention"])


class MonthlyCloseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    year: int
    month: int


@router.post("/{company_id}/monthly-close", status_code=201, summary="Fechamento mensal imutavel")
def create_monthly_close(
    company_id: int,
    payload: MonthlyCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not is_tenant_admin(db, current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores do tenant")
    try:
        result = svc.create_monthly_close(
            db, company_id, payload.year, payload.month, closed_by=current_user.id
        )
    except svc.RetentionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    logger.info(
        "Fechamento mensal: company_id=%s periodo=%s-%02d por user_id=%s",
        company_id,
        payload.year,
        payload.month,
        current_user.id,
    )
    return result


@router.get("/{company_id}/monthly-close", summary="Lista fechamentos do tenant")
def list_monthly_closes(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return svc.list_monthly_closes(db, company_id)


@router.get("/{company_id}/monthly-close/{year}/{month}", summary="Recupera um fechamento")
def get_monthly_close(
    company_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    try:
        return svc.get_monthly_close(db, company_id, year, month)
    except svc.RetentionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
