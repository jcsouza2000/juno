"""Testes do router app/api/erp.py (CRUD de ERPConnection)."""

from app.auth import create_access_token, get_password_hash
from app.core.crypto import decrypt
from app.models import Company, ERPConnection, User


def _create_admin_with_company(db) -> tuple:
    company = Company(name="ACME Industries", sector="manufatura")
    db.add(company)
    db.commit()
    db.refresh(company)

    user = User(
        email="admin@acme.com",
        full_name="Admin ACME",
        hashed_password=get_password_hash("senha123"),
        role="admin",
        is_active=True,
    )
    user.companies.append(company)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, company


def _auth_headers(user) -> dict:
    token = create_access_token({"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


def test_list_available_connectors_requires_auth(client):
    r = client.get("/api/v1/erp/connectors/available")
    assert r.status_code == 401


def test_list_available_connectors_returns_list(client, db_session):
    user, _ = _create_admin_with_company(db_session)
    r = client.get("/api/v1/erp/connectors/available", headers=_auth_headers(user))
    assert r.status_code == 200
    body = r.json()
    assert "connectors" in body
    types = {c["type"] for c in body["connectors"]}
    assert "totvs_protheus" in types
    assert "sap_ecc" in types


def test_create_connection_encrypts_password(client, db_session):
    user, company = _create_admin_with_company(db_session)
    r = client.post(
        "/api/v1/erp/connections",
        headers=_auth_headers(user),
        json={
            "company_id": company.id,
            "erp_type": "totvs_protheus",
            "name": "Protheus PRD",
            "host": "10.0.0.1",
            "port": 8080,
            "username": "api",
            "password": "senha-super-secreta-do-erp",
            "auth_method": "basic",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["erp_type"] == "totvs_protheus"
    # Critico: senha nao deve vazar no response
    assert "password" not in body
    assert "password_encrypted" not in body

    # Mas no banco deve estar criptografada
    conn = db_session.query(ERPConnection).filter_by(id=body["id"]).first()
    assert conn.password_encrypted is not None
    assert conn.password_encrypted != "senha-super-secreta-do-erp"
    assert decrypt(conn.password_encrypted) == "senha-super-secreta-do-erp"


def test_non_admin_cannot_create_connection(client, db_session):
    company = Company(name="X", sector="y")
    db_session.add(company)
    db_session.commit()
    user = User(
        email="user@x.com",
        full_name="Regular",
        hashed_password=get_password_hash("senha123"),
        role="user",
        is_active=True,
    )
    user.companies.append(company)
    db_session.add(user)
    db_session.commit()

    r = client.post(
        "/api/v1/erp/connections",
        headers=_auth_headers(user),
        json={
            "company_id": company.id,
            "erp_type": "sap_ecc",
            "name": "X",
            "host": "h",
        },
    )
    assert r.status_code == 403


def test_list_connections_filtered_by_company(client, db_session):
    user, company = _create_admin_with_company(db_session)
    # Cria 3 connections na company do user
    for i in range(3):
        c = ERPConnection(
            company_id=company.id,
            erp_type="generic",
            name=f"Conn {i}",
            host="h",
        )
        db_session.add(c)
    db_session.commit()

    r = client.get(
        f"/api/v1/erp/companies/{company.id}/connections",
        headers=_auth_headers(user),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3


def test_update_connection_reencrypts_password(client, db_session):
    user, company = _create_admin_with_company(db_session)
    conn = ERPConnection(
        company_id=company.id,
        erp_type="generic",
        name="X",
        host="h",
        password_encrypted="senha-velha-criptografada-falsa",
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)

    r = client.put(
        f"/api/v1/erp/connections/{conn.id}",
        headers=_auth_headers(user),
        json={"password": "nova-senha-real"},
    )
    assert r.status_code == 200, r.text
    db_session.refresh(conn)
    assert conn.password_encrypted != "senha-velha-criptografada-falsa"
    assert decrypt(conn.password_encrypted) == "nova-senha-real"


def test_delete_connection(client, db_session):
    user, company = _create_admin_with_company(db_session)
    conn = ERPConnection(
        company_id=company.id,
        erp_type="generic",
        name="X",
        host="h",
    )
    db_session.add(conn)
    db_session.commit()
    conn_id = conn.id

    r = client.delete(
        f"/api/v1/erp/connections/{conn_id}",
        headers=_auth_headers(user),
    )
    assert r.status_code == 204
    assert db_session.query(ERPConnection).filter_by(id=conn_id).first() is None
