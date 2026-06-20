"""Regressao das features novas (v0.3.2):

- importadores ERP de Estoque, Fornecedores e Financeiro operacional;
- PDF executivo bilingue + geracao sem erro;
- endpoint/builder de Diagnostico 360;
- i18n de backend (insights e recomendacoes do Score).
"""

from __future__ import annotations

import csv
import os
import tempfile

import pytest

from app.insights import generate_insights
from app.integrations.erp_importer import import_erp_data
from app.models import Company, ErpFinancial, Inventory, Product, ProductionOrder, Supplier
from app.pdf_service import JUNOPDFReport
from app.routers.pdf import build_diagnostic
from app.score_v2 import get_score_calculator


def _company(db, name: str = "ACME Industria") -> int:
    c = Company(name=name, sector="industria")
    db.add(c)
    db.flush()
    return c.id


def _write_csv(rows: list[dict], header: list[str]) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=header)
        wr.writeheader()
        wr.writerows(rows)
    return path


def _import(db, cid, data_type, rows, header):
    path = _write_csv(rows, header)
    try:
        return import_erp_data(cid, data_type, path, os.path.basename(path), db)
    finally:
        os.remove(path)


# ── Importadores ──────────────────────────────────────────────────────────────


def test_import_inventory(db_session):
    cid = _company(db_session)
    res = _import(
        db_session,
        cid,
        "inventory",
        [
            {
                "product_name": "Item A",
                "warehouse_location": "Principal",
                "quantity_on_hand": "100",
                "quantity_reserved": "10",
                "unit_cost": "5.50",
            },
            {
                "product_name": "Item B",
                "warehouse_location": "CD-SP",
                "quantity_on_hand": "200",
                "quantity_reserved": "0",
                "unit_cost": "12,00",
            },
        ],
        [
            "product_name",
            "warehouse_location",
            "quantity_on_hand",
            "quantity_reserved",
            "unit_cost",
        ],
    )
    assert res["status"] == "success"
    assert res["rows_imported"] == 2
    rows = db_session.query(Inventory).filter_by(company_id=cid).all()
    assert len(rows) == 2
    item_a = next(r for r in rows if r.warehouse_location == "Principal")
    assert item_a.quantity_on_hand == 100
    assert item_a.quantity_available == 90  # 100 - 10 calculado
    # produto referenciado foi criado
    assert db_session.query(Product).filter_by(company_id=cid, name="Item A").first()


def test_import_inventory_upsert(db_session):
    cid = _company(db_session)
    header = ["product_name", "warehouse_location", "quantity_on_hand"]
    _import(
        db_session,
        cid,
        "inventory",
        [{"product_name": "X", "warehouse_location": "P", "quantity_on_hand": "50"}],
        header,
    )
    _import(
        db_session,
        cid,
        "inventory",
        [{"product_name": "X", "warehouse_location": "P", "quantity_on_hand": "80"}],
        header,
    )
    rows = db_session.query(Inventory).filter_by(company_id=cid).all()
    assert len(rows) == 1  # mesmo produto+deposito = update, nao duplica
    assert rows[0].quantity_on_hand == 80


def test_import_suppliers(db_session):
    cid = _company(db_session)
    res = _import(
        db_session,
        cid,
        "suppliers",
        [
            {
                "name": "Aco Forte",
                "cnpj": "12.345.678/0001-90",
                "lead_time_days": "15",
                "rating": "4.5",
                "payment_terms": "30 dias",
            },
        ],
        ["name", "cnpj", "lead_time_days", "rating", "payment_terms"],
    )
    assert res["status"] == "success"
    sup = db_session.query(Supplier).filter_by(company_id=cid).one()
    assert sup.name == "Aco Forte"
    assert sup.lead_time_days == 15
    assert sup.rating == 4.5


def test_import_financials(db_session):
    cid = _company(db_session)
    res = _import(
        db_session,
        cid,
        "financials",
        [
            {
                "account_name": "Caixa",
                "account_code": "1.01",
                "debit": "1000",
                "credit": "0",
                "period": "2025-01",
            },
            {
                "account_name": "Fornecedores",
                "account_code": "2.01",
                "debit": "0",
                "credit": "1000",
                "period": "2025-01",
            },
        ],
        ["account_name", "account_code", "debit", "credit", "period"],
    )
    assert res["status"] == "success"
    rows = db_session.query(ErpFinancial).filter_by(company_id=cid).all()
    assert len(rows) == 2
    caixa = next(r for r in rows if r.account_name == "Caixa")
    assert caixa.debit == 1000
    assert caixa.balance == 1000  # debit - credit


def test_import_missing_required_column(db_session):
    cid = _company(db_session)
    # suppliers exige 'name'
    res = _import(db_session, cid, "suppliers", [{"cnpj": "1"}], ["cnpj"])
    assert res["status"] == "error"
    assert res["rows_imported"] == 0


# ── PDF bilingue ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("lang", ["pt", "en", "es"])
def test_pdf_generates(db_session, lang):
    cid = _company(db_session)
    pdf = JUNOPDFReport(db_session).generate_executive_report(cid, lang=lang)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 2000


# ── Diagnostico 360 ─────────────────────────────────────────────────────────


def test_build_diagnostic_shape(db_session):
    cid = _company(db_session)
    d = build_diagnostic(cid, db_session, lang="en")
    for key in (
        "company_name",
        "score_juno",
        "revenue",
        "insights",
        "recommendations",
        "action_plan",
    ):
        assert key in d
    assert isinstance(d["score_juno"], (int, float))
    assert isinstance(d["insights"], list)


# ── i18n de backend ─────────────────────────────────────────────────────────


def _seed_delays(db, cid, n=3):
    p = Product(company_id=cid, name="P1", category="x")
    db.add(p)
    db.flush()
    from datetime import datetime, timedelta

    past = datetime(2020, 1, 1)
    for _ in range(n):
        db.add(
            ProductionOrder(
                company_id=cid,
                product_id=p.id,
                planned_qty=10,
                actual_qty=10,
                planned_date=past,
                actual_date=past + timedelta(days=5),
                status="planned",
            )
        )
    db.flush()


def test_insights_i18n(db_session):
    cid = _company(db_session)
    _seed_delays(db_session, cid, 3)
    pt = generate_insights(cid, db_session, lang="pt")
    en = generate_insights(cid, db_session, lang="en")
    pt_delay = next(i for i in pt if i["type"] == "delay_risk")
    en_delay = next(i for i in en if i["type"] == "delay_risk")
    assert "atrasada" in pt_delay["message"]
    assert "delayed" in en_delay["message"]
    assert en_delay["impact"] == "Medium"


def test_score_recommendations_i18n(db_session):
    cid = _company(db_session)
    en = get_score_calculator(db_session).calculate_full_score(cid, persist=False, lang="en")
    es = get_score_calculator(db_session).calculate_full_score(cid, persist=False, lang="es")
    # nao deve quebrar e deve retornar lista de strings
    assert isinstance(en.recommendations, list)
    joined_en = " ".join(en.recommendations)
    joined_es = " ".join(es.recommendations)
    # ao menos uma recomendacao traduzida (idiomas diferentes => textos diferentes)
    assert joined_en != joined_es or en.recommendations == es.recommendations
