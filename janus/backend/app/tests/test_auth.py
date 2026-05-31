"""Testes do fluxo de autenticacao."""

from app.auth import get_password_hash
from app.models import User


def _create_user(
    db, email: str = "test@example.com", password: str = "senha123", role: str = "user"
):
    user = User(
        email=email,
        full_name="Test User",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_success(client, db_session):
    _create_user(db_session)
    response = client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "senha123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["user"]["email"] == "test@example.com"
    # Critico: nao deve vazar hashed_password
    assert "hashed_password" not in body["user"]


def test_login_wrong_password(client, db_session):
    _create_user(db_session)
    response = client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "senha_errada"},
    )
    assert response.status_code == 401


def test_login_unknown_email(client, db_session):
    response = client.post(
        "/auth/login",
        data={"username": "naoexiste@example.com", "password": "qualquer"},
    )
    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
