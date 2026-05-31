"""Golden tests for the lightweight KPI blindage foundation."""

import pytest

from app.auth import create_access_token, get_password_hash
from app.dashboards import get_ceo_kpis, get_cfo_margin_by_product, get_coo_delayed_orders
from app.financials import get_financial_summary
from app.kpi_catalog import build_persona_dashboard
from app.score_v2 import get_score_calculator
from app.tests.golden_fixtures import GOLDEN_EXPECTED, seed_golden_company
from app.models import User


def _auth_headers(user: User) -> dict:
    token = create_access_token({"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


def _create_tenant_user(db_session, company) -> User:
    user = User(
        email="golden@tenant.com",
        full_name="Golden User",
        hashed_password=get_password_hash("senha123"),
        role="admin",
        is_active=True,
    )
    user.companies.append(company)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_golden_financial_summary_formulas(db_session):
    company = seed_golden_company(db_session)

    summary = get_financial_summary(company.id, db_session)

    assert summary["available"] is True
    assert summary["dre"]["receita_bruta"] == GOLDEN_EXPECTED["receita_bruta"]
    assert summary["dre"]["receita_liquida"] == GOLDEN_EXPECTED["receita_liquida"]
    assert summary["dre"]["lucro_bruto"] == GOLDEN_EXPECTED["lucro_bruto_dre"]
    assert summary["dre"]["margem_bruta_pct"] == pytest.approx(
        GOLDEN_EXPECTED["margem_media_pct"], abs=0.01
    )
    assert summary["balanco"]["liquidez_corrente"] == GOLDEN_EXPECTED["liquidez_corrente"]
    assert summary["balanco"]["endividamento_pct"] == GOLDEN_EXPECTED["endividamento_pct"]


def test_golden_dashboard_uses_net_revenue_margin_and_delay(db_session):
    company = seed_golden_company(db_session)

    ceo = get_ceo_kpis(db_session, company.id)
    margins = get_cfo_margin_by_product(db_session, company.id)
    delays = get_coo_delayed_orders(db_session, company.id)

    assert ceo["receita_total"] == GOLDEN_EXPECTED["receita_liquida"]
    assert ceo["receita_liquida"] == GOLDEN_EXPECTED["receita_liquida"]
    assert sum(item["margem"] for item in margins) == GOLDEN_EXPECTED["margem_produtos_total"]
    assert len(delays) == GOLDEN_EXPECTED["ordens_atrasadas"]
    assert any(item["actual_date"] is None for item in delays)


def test_golden_score_juno_v2_is_canonical(db_session):
    company = seed_golden_company(db_session)

    score = get_score_calculator(db_session).calculate_full_score(company.id, persist=False)
    ceo = get_ceo_kpis(db_session, company.id)
    ceo_dashboard = build_persona_dashboard(db_session, company.id, "ceo")
    ceo_score_kpi = next(
        kpi for section in ceo_dashboard["sections"] for kpi in section["kpis"] if kpi["id"] == "juno_score"
    )

    assert score.overall_score == pytest.approx(GOLDEN_EXPECTED["score_juno"], abs=0.05)
    assert ceo["score_juno"] == score.overall_score
    assert ceo_score_kpi["value"] == score.overall_score


def test_metric_api_contracts_accept_golden_payloads(client, db_session):
    company = seed_golden_company(db_session)
    user = _create_tenant_user(db_session, company)
    headers = _auth_headers(user)

    ceo = client.get(f"/dashboard/ceo/{company.id}", headers=headers)
    coo = client.get(f"/dashboard/coo/{company.id}", headers=headers)
    score = client.get(f"/score/{company.id}", headers=headers)

    assert ceo.status_code == 200
    assert set(ceo.json()) == {"receita_total", "receita_liquida", "score_juno"}
    assert coo.status_code == 200
    assert len(coo.json()) == GOLDEN_EXPECTED["ordens_atrasadas"]
    assert score.status_code == 200
    assert score.json()["overall_score"] == pytest.approx(
        GOLDEN_EXPECTED["score_juno"], abs=0.05
    )
