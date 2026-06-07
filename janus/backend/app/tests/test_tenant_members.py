"""
Testes do service de membros de tenant (Fase 1 — multi-usuario).

Cobre criacao/vinculo, papeis, protecao do ultimo owner, autorizacao e
isolamento entre tenants.
"""

from __future__ import annotations

import pytest

from app.auth import get_password_hash, get_user_company_ids
from app.models import Company, User, UserCompany
from app.services import tenant_members as svc
from app.services.tenant_members import TenantMemberError


def _make_company(db, name: str) -> int:
    company = Company(name=name, sector="industria")
    db.add(company)
    db.flush()
    return company.id


def _make_user(db, email: str, role: str = "user") -> User:
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=get_password_hash("senha-de-teste-123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def tenant_a(db_session):
    cid = _make_company(db_session, "Tenant A")
    db_session.commit()
    return db_session, cid


# ── add_member ───────────────────────────────────────────────────────────────


def test_add_member_cria_usuario_novo_com_senha_temporaria(tenant_a):
    db, cid = tenant_a
    member, created, temp = svc.add_member(
        db, cid, email="novo@empresa.com", role_in_tenant="member"
    )

    assert created is True
    assert temp is not None and len(temp) >= 12
    assert member["email"] == "novo@empresa.com"
    assert member["role_in_tenant"] == "member"
    # Primeiro vinculo do usuario vira primario.
    assert member["is_primary"] is True

    user = db.query(User).filter(User.email == "novo@empresa.com").first()
    assert user is not None
    assert cid in get_user_company_ids(user)


def test_add_member_vincula_usuario_existente_sem_senha_temp(tenant_a):
    db, cid = tenant_a
    _make_user(db, "ja@existe.com")
    db.commit()

    member, created, temp = svc.add_member(db, cid, email="ja@existe.com", role_in_tenant="admin")
    assert created is False
    assert temp is None
    assert member["role_in_tenant"] == "admin"


def test_add_member_duplicado_falha(tenant_a):
    db, cid = tenant_a
    svc.add_member(db, cid, email="dup@empresa.com")
    with pytest.raises(TenantMemberError) as exc:
        svc.add_member(db, cid, email="dup@empresa.com")
    assert exc.value.status_code == 409


def test_add_member_role_invalido_falha(tenant_a):
    db, cid = tenant_a
    with pytest.raises(TenantMemberError):
        svc.add_member(db, cid, email="x@empresa.com", role_in_tenant="superuser")


def test_email_normalizado_para_minusculas(tenant_a):
    db, cid = tenant_a
    member, _, _ = svc.add_member(db, cid, email="MAIUSC@Empresa.COM")
    assert member["email"] == "maiusc@empresa.com"


# ── update_member_role ───────────────────────────────────────────────────────


def test_update_member_role(tenant_a):
    db, cid = tenant_a
    member, _, _ = svc.add_member(db, cid, email="m@empresa.com", role_in_tenant="member")
    updated = svc.update_member_role(db, cid, member["user_id"], "viewer")
    assert updated["role_in_tenant"] == "viewer"


def test_nao_rebaixa_ultimo_owner(tenant_a):
    db, cid = tenant_a
    owner, _, _ = svc.add_member(db, cid, email="owner@empresa.com", role_in_tenant="owner")
    with pytest.raises(TenantMemberError):
        svc.update_member_role(db, cid, owner["user_id"], "member")


def test_rebaixa_owner_quando_ha_outro(tenant_a):
    db, cid = tenant_a
    o1, _, _ = svc.add_member(db, cid, email="o1@empresa.com", role_in_tenant="owner")
    svc.add_member(db, cid, email="o2@empresa.com", role_in_tenant="owner")
    updated = svc.update_member_role(db, cid, o1["user_id"], "admin")
    assert updated["role_in_tenant"] == "admin"


# ── remove_member ────────────────────────────────────────────────────────────


def test_remove_member(tenant_a):
    db, cid = tenant_a
    member, _, _ = svc.add_member(db, cid, email="rm@empresa.com", role_in_tenant="member")
    svc.remove_member(db, cid, member["user_id"])

    assert (
        db.query(UserCompany)
        .filter(UserCompany.user_id == member["user_id"], UserCompany.company_id == cid)
        .count()
        == 0
    )
    # Usuario global permanece.
    assert db.query(User).filter(User.id == member["user_id"]).count() == 1


def test_nao_remove_ultimo_owner(tenant_a):
    db, cid = tenant_a
    owner, _, _ = svc.add_member(db, cid, email="dono@empresa.com", role_in_tenant="owner")
    with pytest.raises(TenantMemberError):
        svc.remove_member(db, cid, owner["user_id"])


# ── Autorizacao e isolamento ─────────────────────────────────────────────────


def test_is_tenant_admin_por_papel(tenant_a):
    db, cid = tenant_a
    owner = _make_user(db, "adm@empresa.com")
    member = _make_user(db, "comum@empresa.com")
    db.add(UserCompany(user_id=owner.id, company_id=cid, role_in_tenant="owner"))
    db.add(UserCompany(user_id=member.id, company_id=cid, role_in_tenant="member"))
    db.commit()

    assert svc.is_tenant_admin(db, owner, cid) is True
    assert svc.is_tenant_admin(db, member, cid) is False


def test_platform_admin_e_sempre_admin(tenant_a):
    db, cid = tenant_a
    pa = _make_user(db, "plat@juno.com", role="platform_admin")
    db.commit()
    # Mesmo sem membership, platform_admin gere qualquer tenant.
    assert svc.is_tenant_admin(db, pa, cid) is True


def test_membros_isolados_por_tenant(db_session):
    db = db_session
    cid_a = _make_company(db, "A")
    cid_b = _make_company(db, "B")
    db.commit()

    svc.add_member(db, cid_a, email="a1@x.com")
    svc.add_member(db, cid_a, email="a2@x.com")
    svc.add_member(db, cid_b, email="b1@x.com")

    assert len(svc.list_members(db, cid_a)) == 2
    assert len(svc.list_members(db, cid_b)) == 1
    assert (
        svc.get_tenant_role(db, db.query(User).filter(User.email == "b1@x.com").first().id, cid_a)
        is None
    )
