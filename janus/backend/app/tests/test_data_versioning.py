"""
Testes de versionamento de depositos (Fase B).
"""

from __future__ import annotations

import pytest

from app.data_versioning import (
    activate_version,
    get_active_financial_batch_id,
    list_versions,
    register_erp_import_batch,
    register_financial_upload_batch,
)
from app.financials import get_statements, save_financial_statements
from app.models import Company, FinancialStatement, FinancialUploadBatch


def _company(db) -> int:
    c = Company(name="Versao Co", sector="industria")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.id


def _row(period: str = "2026-01", value: float = 100.0) -> dict:
    return {
        "statement_type": "DRE",
        "period": period,
        "line_item": "receita_bruta",
        "value": value,
    }


def test_financial_upload_incrementa_versao_e_mantem_historico(db_session):
    cid = _company(db_session)

    save_financial_statements(cid, [_row(value=100)], "v1.xlsx", db_session)
    save_financial_statements(cid, [_row(value=200)], "v2.xlsx", db_session)

    versions = list_versions(db_session, cid, "financial")
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[0]["is_active"] is True
    assert versions[1]["is_active"] is False
    assert db_session.query(FinancialStatement).filter_by(company_id=cid).count() == 2


def test_get_statements_retorna_somente_versao_ativa(db_session):
    cid = _company(db_session)

    save_financial_statements(cid, [_row(value=100)], "v1.xlsx", db_session)
    save_financial_statements(cid, [_row(value=250)], "v2.xlsx", db_session)

    stmts = get_statements(cid, db_session)
    dre = stmts["DRE"]["2026-01"]
    assert dre["receita_bruta"] == 250.0


def test_ativar_versao_anterior_troca_dados_visiveis(db_session):
    cid = _company(db_session)

    r1 = save_financial_statements(cid, [_row(value=100)], "v1.xlsx", db_session)
    save_financial_statements(cid, [_row(value=250)], "v2.xlsx", db_session)

    activate_version(db_session, cid, "financial", r1["batch_id"])

    assert get_active_financial_batch_id(db_session, cid) == r1["batch_id"]
    dre = get_statements(cid, db_session)["DRE"]["2026-01"]
    assert dre["receita_bruta"] == 100.0


def test_erp_register_incrementa_versao(db_session):
    cid = _company(db_session)

    register_erp_import_batch(
        db_session,
        cid,
        data_type="products",
        file_name="p1.csv",
        rows_received=10,
        rows_imported=10,
        rows_rejected=0,
        status="success",
    )
    register_erp_import_batch(
        db_session,
        cid,
        data_type="products",
        file_name="p2.csv",
        rows_received=20,
        rows_imported=20,
        rows_rejected=0,
        status="success",
    )
    db_session.commit()

    versions = list_versions(db_session, cid, "erp")
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[0]["is_active"] is True


def test_activate_endpoint(client, db_session):
    from app.auth import get_current_active_user, get_password_hash
    from app.main import app
    from app.models import User

    cid = _company(db_session)
    batch = register_financial_upload_batch(
        db_session, cid, file_name="legacy.xlsx", periods="2026-01", rows_imported=0
    )
    db_session.add(
        FinancialStatement(
            company_id=cid,
            upload_batch_id=batch.id,
            statement_type="DRE",
            period="2026-01",
            line_item="receita_bruta",
            value=50.0,
        )
    )
    db_session.commit()

    admin = User(
        email="admin_v@test.com",
        full_name="Admin V",
        hashed_password=get_password_hash("x"),
        role="platform_admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    def _admin_user():
        return admin

    app.dependency_overrides[get_current_active_user] = _admin_user
    try:
        res = client.post(f"/data/{cid}/versions/{batch.id}/activate?source=financial")
        assert res.status_code == 200
        assert res.json()["version_label"] == f"v{batch.version_number}"
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
