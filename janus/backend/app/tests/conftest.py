"""
Fixtures base para os testes JUNO.

IMPORTANTE: estas envs sao FIXADAS no nivel do conftest e SOBRESCREVEM o
.env do dev/prod. Garante que testes NUNCA usam as chaves reais do
ambiente. Use chaves dedicadas de teste -- nao rotacione com base nestes.
"""

import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

_tmp_dir = tempfile.mkdtemp(prefix="juno-test-")
_test_db_path = Path(_tmp_dir) / "test.db"

os.environ["JUNO_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-min-32-chars"
os.environ["JUNO_DEV_AUTH_BYPASS"] = "false"
# Fernet key de teste -- gerada uma vez para os testes desta sessao.
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["ALLOWED_ORIGINS"] = "http://testserver"
os.environ["JUNO_DISABLE_TEMPLATES"] = "1"

# Testes antigos (fases 5-12) que precisam mlflow/pandas pesado.
collect_ignore_glob = [
    "test_ml.py",
    "test_reports.py",
    "test_security.py",
]

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine, get_db
from app.main import app


@pytest.fixture()
def db_session():
    """Session do banco de teste. Limpa rows entre tests."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """TestClient FastAPI com DB de teste injetado via dependency override."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
