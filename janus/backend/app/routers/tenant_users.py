"""
Router de gestao de membros de um tenant (Fase 1 — multi-usuario real).

Endpoints sob /tenants/{company_id}/members:
  GET    — lista membros do tenant.
  POST   — convida/cria membro (define role_in_tenant).
  PATCH  — altera o papel de um membro.
  DELETE — remove o membro do tenant (preserva o usuario global).

Autorizacao: exige owner/admin DO tenant (role_in_tenant) ou platform_admin.
Toda operacao e escopada pelo company_id do path — sem vazamento entre tenants.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.core.logger import get_logger
from app.database import get_db
from app.models import User
from app.schemas.tenant import (
    TenantMemberCreate,
    TenantMemberCreateResponse,
    TenantMemberOut,
    TenantMemberUpdate,
)
from app.services import tenant_members as svc

logger = get_logger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenant Members"])


def _require_tenant_admin(company_id: int, db: Session, user: User) -> None:
    if not svc.is_tenant_admin(db, user, company_id):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores do tenant")


@router.get("/{company_id}/members", response_model=list[TenantMemberOut])
def list_tenant_members(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_tenant_admin(company_id, db, current_user)
    return svc.list_members(db, company_id)


@router.post(
    "/{company_id}/members",
    response_model=TenantMemberCreateResponse,
    status_code=201,
)
def add_tenant_member(
    company_id: int,
    payload: TenantMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_tenant_admin(company_id, db, current_user)
    try:
        member, created_user, temp_password = svc.add_member(
            db,
            company_id,
            email=payload.email,
            role_in_tenant=payload.role_in_tenant,
            full_name=payload.full_name,
            password=payload.password,
        )
    except svc.TenantMemberError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    logger.info(
        "Membro adicionado: company_id=%s email=%s role=%s por user_id=%s (novo=%s)",
        company_id,
        payload.email,
        payload.role_in_tenant,
        current_user.id,
        created_user,
    )
    return TenantMemberCreateResponse(
        member=TenantMemberOut(**member),
        created_user=created_user,
        temp_password=temp_password,
    )


@router.patch("/{company_id}/members/{user_id}", response_model=TenantMemberOut)
def update_tenant_member(
    company_id: int,
    user_id: int,
    payload: TenantMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_tenant_admin(company_id, db, current_user)
    try:
        member = svc.update_member_role(db, company_id, user_id, payload.role_in_tenant)
    except svc.TenantMemberError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    logger.info(
        "Papel atualizado: company_id=%s user_id=%s novo_role=%s por user_id=%s",
        company_id,
        user_id,
        payload.role_in_tenant,
        current_user.id,
    )
    return TenantMemberOut(**member)


@router.delete("/{company_id}/members/{user_id}")
def remove_tenant_member(
    company_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_tenant_admin(company_id, db, current_user)
    try:
        svc.remove_member(db, company_id, user_id)
    except svc.TenantMemberError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    logger.info(
        "Membro removido: company_id=%s user_id=%s por user_id=%s",
        company_id,
        user_id,
        current_user.id,
    )
    return {"status": "removed", "company_id": company_id, "user_id": user_id}
