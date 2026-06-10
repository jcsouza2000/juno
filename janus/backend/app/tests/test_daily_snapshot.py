"""Testes do snapshot diario (Fase 5)."""

from __future__ import annotations

from datetime import date

import pytest

from app.models import Company
from app.services import retention as svc


@pytest.fixture()
def company(db_session):
    c = Company(name="Snapshot Co", sector="industria")
    db_session.add(c)
    db_session.commit()
    return db_session, c.id


def test_create_daily_snapshot_idempotent(company):
    db, cid = company
    first = svc.create_daily_snapshot(db, cid, snapshot_date=date(2026, 5, 29))
    second = svc.create_daily_snapshot(db, cid, snapshot_date=date(2026, 5, 29))
    assert first["id"] == second["id"]
    assert first["snapshot_date"] == "2026-05-29"
    assert second["snapshot"]["company_id"] == cid


def test_list_daily_snapshots(company):
    db, cid = company
    svc.create_daily_snapshot(db, cid, snapshot_date=date(2026, 5, 28))
    svc.create_daily_snapshot(db, cid, snapshot_date=date(2026, 5, 29))
    rows = svc.list_daily_snapshots(db, cid)
    assert len(rows) == 2
    assert rows[0]["snapshot_date"] == "2026-05-29"


def test_run_daily_snapshots_all_tenants(company):
    db, _cid = company
    result = svc.run_daily_snapshots_all_tenants(db)
    assert result["tenants"] >= 1
    assert result["created"] + result["updated"] >= 1
