"""Testes de validação do Settings — garantem que prod falha sem variáveis."""

import pytest

from app.config import Settings


def test_secret_key_required_in_production(monkeypatch):
    monkeypatch.setenv("JUNO_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    with pytest.raises(Exception):  # ValidationError
        Settings()


def test_database_url_required_in_production(monkeypatch):
    monkeypatch.setenv("JUNO_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(Exception):  # ValidationError
        Settings()


def test_dev_defaults_are_sane(monkeypatch):
    monkeypatch.setenv("JUNO_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "")
    s = Settings()
    assert s.is_development
    assert not s.is_production
    assert len(s.SECRET_KEY) >= 32  # gerada aleatoriamente
    assert s.DATABASE_URL.startswith("sqlite:")  # sem credenciais hardcoded


def test_dev_auth_bypass_forbidden_in_production(monkeypatch):
    monkeypatch.setenv("JUNO_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("ENCRYPTION_KEY", "N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM=")
    monkeypatch.setenv("JUNO_DEV_AUTH_BYPASS", "true")
    with pytest.raises(Exception):
        Settings()


def test_sqlite_forbidden_in_production(monkeypatch):
    monkeypatch.setenv("JUNO_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./bad.db")
    monkeypatch.setenv("ENCRYPTION_KEY", "N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM=")
    monkeypatch.setenv("JUNO_DEV_AUTH_BYPASS", "false")
    with pytest.raises(Exception):
        Settings()


def test_cors_origins_parses_csv(monkeypatch):
    monkeypatch.setenv("JUNO_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.com,https://b.com, https://c.com ")
    s = Settings()
    assert s.cors_origins == ["https://a.com", "https://b.com", "https://c.com"]
