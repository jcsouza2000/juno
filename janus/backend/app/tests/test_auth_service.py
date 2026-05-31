"""Testes do AuthService (camada de servicos)."""

from app.auth import get_password_hash
from app.models import User
from app.services.auth_service import AuthService


def _create_user(db, **overrides):
    defaults = dict(
        email="svc@example.com",
        full_name="Service Test",
        hashed_password=get_password_hash("senha123"),
        role="user",
        is_active=True,
    )
    defaults.update(overrides)
    u = User(**defaults)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_authenticate_success(db_session):
    _create_user(db_session)
    service = AuthService(db_session)
    user = service.authenticate("svc@example.com", "senha123")
    assert user is not None
    assert user.email == "svc@example.com"


def test_authenticate_wrong_password(db_session):
    _create_user(db_session)
    service = AuthService(db_session)
    assert service.authenticate("svc@example.com", "errada") is None


def test_authenticate_unknown_email(db_session):
    service = AuthService(db_session)
    assert service.authenticate("naoexiste@example.com", "qualquer") is None


def test_authenticate_inactive_user(db_session):
    _create_user(db_session, is_active=False)
    service = AuthService(db_session)
    assert service.authenticate("svc@example.com", "senha123") is None


def test_get_user_by_email(db_session):
    _create_user(db_session)
    service = AuthService(db_session)
    u = service.get_user_by_email("svc@example.com")
    assert u is not None
    assert u.id is not None
