"""
JUNO Tenant Router — Gestão multi-tenant
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_active_user, require_admin
from app.database import get_db
from app.models import User
from app.multi_tenant import get_tenant_service

router = APIRouter(prefix="/tenants", tags=["Multi-Tenancy"])


@router.get("/my")
def get_my_tenants(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    Retorna todos os tenants (empresas) que o usuário pode acessar.
    """
    service = get_tenant_service(db)
    return {"user_id": current_user.id, "tenants": service.get_user_tenants(current_user.id)}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_tenant(
    name: str,
    sector: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Cria novo tenant (apenas admin).
    """
    service = get_tenant_service(db)
    company = service.create_tenant(name=name, sector=sector, admin_user_id=current_user.id)

    return {
        "id": company.id,
        "name": company.name,
        "sector": company.sector,
        "message": "Tenant criado com sucesso",
    }


@router.get("/{company_id}/stats")
def get_tenant_stats(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Estatísticas de uso do tenant.
    """
    service = get_tenant_service(db)

    if not service.validate_tenant_access(current_user.id, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    stats = service.get_tenant_stats(company_id)

    return {"company_id": company_id, "stats": stats}


@router.post("/{company_id}/users/{user_id}")
def add_user_to_tenant(
    company_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Adiciona usuário a um tenant (apenas admin).
    """
    from app.models import UserCompany

    # Verificar se já existe
    existing = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Usuário já está no tenant")

    association = UserCompany(user_id=user_id, company_id=company_id)
    db.add(association)
    db.commit()

    return {"message": "Usuário adicionado ao tenant", "company_id": company_id, "user_id": user_id}


@router.delete("/{company_id}/users/{user_id}")
def remove_user_from_tenant(
    company_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Remove usuário de um tenant (apenas admin).
    """
    from app.models import UserCompany

    association = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
        .first()
    )

    if not association:
        raise HTTPException(status_code=404, detail="Associação não encontrada")

    db.delete(association)
    db.commit()

    return {"message": "Usuário removido do tenant"}
