"""Testes de confianca: tenant isolation, RBAC e headers de auditoria."""

from app.auth import create_access_token, get_password_hash
from app.models import Company, User, UserCompany


def _auth_headers(user) -> dict:
    token = create_access_token({"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


def _create_user(db, email: str, role: str, company: Company | None = None) -> User:
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=get_password_hash("senha123"),
        role=role,
        is_active=True,
    )
    if company:
        user.companies.append(company)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_request_id_and_security_headers_present(client):
    response = client.get("/health", headers={"X-Request-ID": "trust-test-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trust-test-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_tenant_admin_cannot_access_other_company_erp(client, db_session):
    allowed = Company(name="Allowed", sector="industry")
    forbidden = Company(name="Forbidden", sector="industry")
    db_session.add_all([allowed, forbidden])
    db_session.commit()

    admin = _create_user(db_session, "admin@allowed.com", "admin", allowed)

    response = client.get(
        f"/api/v1/erp/companies/{forbidden.id}/connections",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 403


def test_membership_table_only_user_appears_in_me_companies(client, db_session):
    company = Company(name="Membership Only", sector="services")
    db_session.add(company)
    db_session.commit()

    user = _create_user(db_session, "member@tenant.com", "user")
    db_session.add(
        UserCompany(user_id=user.id, company_id=company.id, role_in_tenant="member", is_primary=True)
    )
    db_session.commit()

    response = client.get("/auth/me", headers=_auth_headers(user))

    assert response.status_code == 200
    companies = response.json()["companies"]
    assert companies == [{"id": company.id, "name": company.name}]


def test_regular_user_cannot_read_security_settings(client, db_session):
    company = Company(name="Regular Tenant", sector="services")
    db_session.add(company)
    db_session.commit()

    user = _create_user(db_session, "user@tenant.com", "user", company)

    response = client.get("/api/v1/security/settings", headers=_auth_headers(user))

    assert response.status_code == 403


def test_tenant_admin_can_read_trust_posture(client, db_session):
    company = Company(name="Admin Tenant", sector="services")
    db_session.add(company)
    db_session.commit()

    admin = _create_user(db_session, "admin@tenant.com", "admin", company)

    response = client.get("/api/v1/security/trust/posture", headers=_auth_headers(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["company_id"] == company.id
    assert body["trust_level"] == "controlled"
    assert any(control["id"] == "tenant_isolation" for control in body["controls"])
