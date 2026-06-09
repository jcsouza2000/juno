"""Testes do service de retencao / fechamento mensal (Fase 5)."""

from __future__ import annotations

import pytest

from app.models import Company
from app.services import retention as svc
from app.services.retention import RetentionError


@pytest.fixture()
def company(db_session):
    c = Company(name="Retencao Co", sector="industria")
    db_session.add(c)
    db_session.commit()
    return db_session, c.id


def test_cria_fechamento_com_snapshot(company):
    db, cid = company
    out = svc.create_monthly_close(db, cid, 2026, 3, closed_by=7)

    assert out["year"] == 2026
    assert out["month"] == 3
    assert out["status"] == "closed"
    assert out["closed_by"] == 7
    # snapshot contem secoes esperadas (mesmo que vazias)
    assert "financial" in out["snapshot"]
    assert "score" in out["snapshot"]
    assert out["snapshot"]["company_id"] == cid


def test_fechamento_duplicado_falha_409(company):
    db, cid = company
    svc.create_monthly_close(db, cid, 2026, 3)
    with pytest.raises(RetentionError) as exc:
        svc.create_monthly_close(db, cid, 2026, 3)
    assert exc.value.status_code == 409


def test_periodo_invalido(company):
    db, cid = company
    with pytest.raises(RetentionError):
        svc.create_monthly_close(db, cid, 2026, 13)
    with pytest.raises(RetentionError):
        svc.create_monthly_close(db, cid, 1990, 5)


def test_lista_ordenada_sem_snapshot(company):
    db, cid = company
    svc.create_monthly_close(db, cid, 2026, 1)
    svc.create_monthly_close(db, cid, 2026, 3)
    svc.create_monthly_close(db, cid, 2025, 12)

    closes = svc.list_monthly_closes(db, cid)
    assert [(c["year"], c["month"]) for c in closes] == [(2026, 3), (2026, 1), (2025, 12)]
    # listagem e' enxuta (sem snapshot)
    assert all("snapshot" not in c for c in closes)


def test_get_retorna_snapshot(company):
    db, cid = company
    svc.create_monthly_close(db, cid, 2026, 2)
    got = svc.get_monthly_close(db, cid, 2026, 2)
    assert got["snapshot"] is not None


def test_get_inexistente_404(company):
    db, cid = company
    with pytest.raises(RetentionError) as exc:
        svc.get_monthly_close(db, cid, 2026, 9)
    assert exc.value.status_code == 404


def test_isolamento_entre_tenants(db_session):
    db = db_session
    a = Company(name="A", sector="x")
    b = Company(name="B", sector="y")
    db.add_all([a, b])
    db.commit()

    svc.create_monthly_close(db, a.id, 2026, 1)
    assert len(svc.list_monthly_closes(db, a.id)) == 1
    assert len(svc.list_monthly_closes(db, b.id)) == 0
