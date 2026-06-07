"""
Service de gestao de membros de tenant (Fase 1 — multi-usuario real).

Mantem as DUAS estruturas de vinculo em sincronia: a tabela de associacao
`user_companies` (usada por User.companies) e o model `UserCompany`
(`user_company_memberships`, que carrega role_in_tenant/is_primary).

Nao importa fastapi: erros viram `TenantMemberError` (com status_code), que o
router converte em HTTPException. Assim o service e testavel sem subir o app.
"""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.auth import get_password_hash, is_platform_admin
from app.core.datetime_utils import utcnow_naive
from app.models import Company, User, UserCompany
from app.schemas.tenant import VALID_TENANT_ROLES


class TenantMemberError(Exception):
    """Erro de regra de negocio na gestao de membros."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ── Autorizacao ──────────────────────────────────────────────────────────────


def get_tenant_role(db: Session, user_id: int, company_id: int) -> str | None:
    """Papel do usuario NO tenant (owner/admin/member/viewer) ou None."""
    membership = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
        .first()
    )
    return membership.role_in_tenant if membership else None


def is_tenant_admin(db: Session, user: User, company_id: int) -> bool:
    """True se o usuario pode gerir membros do tenant."""
    if is_platform_admin(user):
        return True
    return get_tenant_role(db, user.id, company_id) in {"owner", "admin"}


def _count_owners(db: Session, company_id: int) -> int:
    return (
        db.query(UserCompany)
        .filter(UserCompany.company_id == company_id, UserCompany.role_in_tenant == "owner")
        .count()
    )


def _has_primary(db: Session, user_id: int) -> bool:
    return (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.is_primary.is_(True))
        .first()
        is not None
    )


# ── Serializacao ─────────────────────────────────────────────────────────────


def _member_dict(membership: UserCompany, user: User) -> dict:
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role_in_tenant": membership.role_in_tenant,
        "is_primary": bool(membership.is_primary),
        "global_role": user.role,
        "is_active": bool(user.is_active),
        "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
    }


# ── Operacoes ────────────────────────────────────────────────────────────────


def list_members(db: Session, company_id: int) -> list[dict]:
    """Lista membros do tenant (baseado em UserCompany)."""
    rows = (
        db.query(UserCompany, User)
        .join(User, User.id == UserCompany.user_id)
        .filter(UserCompany.company_id == company_id)
        .order_by(UserCompany.joined_at.asc())
        .all()
    )
    return [_member_dict(m, u) for m, u in rows]


def add_member(
    db: Session,
    company_id: int,
    email: str,
    role_in_tenant: str = "member",
    full_name: str | None = None,
    password: str | None = None,
) -> tuple[dict, bool, str | None]:
    """
    Vincula um usuario ao tenant. Cria o usuario se o email ainda nao existir.

    Retorna (member_dict, created_user, temp_password). temp_password so' e'
    preenchido quando criamos um usuario novo sem senha explicita.
    """
    if role_in_tenant not in VALID_TENANT_ROLES:
        raise TenantMemberError(
            f"Papel invalido: {role_in_tenant!r}. Use um de {VALID_TENANT_ROLES}."
        )

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise TenantMemberError("Empresa nao encontrada.", status_code=404)

    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    created_user = False
    temp_password: str | None = None

    if user is None:
        # Cria usuario novo com papel GLOBAL padrao "user". O poder no tenant
        # vem de role_in_tenant, nao do papel global.
        if not password:
            temp_password = secrets.token_urlsafe(12)
            password = temp_password
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
        created_user = True
    else:
        existing = (
            db.query(UserCompany)
            .filter(UserCompany.user_id == user.id, UserCompany.company_id == company_id)
            .first()
        )
        if existing is not None:
            raise TenantMemberError("Usuario ja e membro deste tenant.", status_code=409)
        if full_name and not user.full_name:
            user.full_name = full_name

    # Sincroniza a tabela de associacao secundaria.
    if company not in (user.companies or []):
        user.companies.append(company)

    membership = UserCompany(
        user_id=user.id,
        company_id=company_id,
        role_in_tenant=role_in_tenant,
        is_primary=not _has_primary(db, user.id),
        joined_at=utcnow_naive(),
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    db.refresh(user)

    return _member_dict(membership, user), created_user, temp_password


def update_member_role(db: Session, company_id: int, user_id: int, role_in_tenant: str) -> dict:
    """Altera o papel de um membro. Protege o ultimo owner do tenant."""
    if role_in_tenant not in VALID_TENANT_ROLES:
        raise TenantMemberError(
            f"Papel invalido: {role_in_tenant!r}. Use um de {VALID_TENANT_ROLES}."
        )

    membership = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
        .first()
    )
    if membership is None:
        raise TenantMemberError("Membro nao encontrado no tenant.", status_code=404)

    # Rebaixar o unico owner deixaria o tenant sem dono.
    if (
        membership.role_in_tenant == "owner"
        and role_in_tenant != "owner"
        and _count_owners(db, company_id) <= 1
    ):
        raise TenantMemberError("Nao e' possivel rebaixar o ultimo owner do tenant.")

    membership.role_in_tenant = role_in_tenant
    db.commit()
    db.refresh(membership)

    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None  # membership garante o user
    return _member_dict(membership, user)


def remove_member(db: Session, company_id: int, user_id: int) -> None:
    """Remove o vinculo do usuario com o tenant (nao apaga o usuario global)."""
    membership = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
        .first()
    )
    if membership is None:
        raise TenantMemberError("Membro nao encontrado no tenant.", status_code=404)

    if membership.role_in_tenant == "owner" and _count_owners(db, company_id) <= 1:
        raise TenantMemberError("Nao e' possivel remover o ultimo owner do tenant.")

    db.delete(membership)

    # Remove tambem da tabela de associacao secundaria.
    user = db.query(User).filter(User.id == user_id).first()
    company = db.query(Company).filter(Company.id == company_id).first()
    if user is not None and company is not None and company in (user.companies or []):
        user.companies.remove(company)

    db.commit()
