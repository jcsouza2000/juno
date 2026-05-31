"""Testes do helper de paginacao."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.pagination import PaginationParams, paginate
from app.database import get_db
from app.models import Company


@pytest.fixture()
def populated_db(db_session):
    """Cria 25 companies para testar paginacao."""
    for i in range(25):
        db_session.add(Company(name=f"Company {i:02d}", sector="test"))
    db_session.commit()
    return db_session


def test_pagination_returns_envelope(populated_db):
    query = populated_db.query(Company)
    params = PaginationParams()
    params.skip = 0
    params.limit = 10
    result = paginate(query, params)

    assert set(result.keys()) == {"items", "total", "skip", "limit"}
    assert result["total"] == 25
    assert len(result["items"]) == 10
    assert result["skip"] == 0
    assert result["limit"] == 10


def test_pagination_respects_skip(populated_db):
    query = populated_db.query(Company)
    params = PaginationParams()
    params.skip = 20
    params.limit = 10
    result = paginate(query, params)
    assert len(result["items"]) == 5  # restam 5
    assert result["total"] == 25


def test_pagination_constants():
    """PaginationParams e desenhado para uso via Depends() em endpoints
    FastAPI. Defaults sao Query(...) que FastAPI converte para int.
    Aqui validamos apenas as constantes."""
    from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT

    assert DEFAULT_LIMIT == 20
    assert MAX_LIMIT == 100
    assert DEFAULT_LIMIT <= MAX_LIMIT


def test_pagination_via_http_query_string(db_session):
    """Integracao: usar PaginationParams em um endpoint."""
    # Setup: cria 5 companies
    for i in range(5):
        db_session.add(Company(name=f"C{i}", sector="x"))
    db_session.commit()

    sub_app = FastAPI()

    @sub_app.get("/list")
    def _list(
        pagination: PaginationParams = Depends(),
        db: Session = Depends(get_db),
    ):
        return paginate(db.query(Company), pagination)

    sub_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(sub_app) as c:
        r = c.get("/list?skip=2&limit=2")
        assert r.status_code == 200
        body = r.json()
        # Pydantic encoder vai serializar Company; aqui só conferimos contagens.
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["skip"] == 2
        assert body["limit"] == 2
