from sqlalchemy.orm import Session

from . import dashboards, data_quality, insights
from .models import Company
from .score_v2 import get_score_calculator


def get_demo_summary(company_id: int, db: Session) -> dict:
    """Single endpoint that returns every piece of data the demo UI needs."""
    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.name if company else f"Empresa {company_id}"
    company_sector = company.sector if company else ""

    # ── Dashboard layer ───────────────────────────────────────────────────────
    ceo = dashboards.get_ceo_kpis(db, company_id)
    score = get_score_calculator(db).calculate_full_score(company_id, persist=False).overall_score
    margins = dashboards.get_cfo_margin_by_product(db, company_id)
    delays = dashboards.get_coo_delayed_orders(db, company_id)

    # ── Insights layer ────────────────────────────────────────────────────────
    op_insights = insights.generate_insights(company_id, db)
    dq_insights = data_quality.generate_data_quality_insights(company_id, db)
    all_insights = op_insights + dq_insights

    # ── Data Trust layer ──────────────────────────────────────────────────────
    trust = data_quality.calculate_trust_score(company_id, db)
    dq_issues = data_quality.detect_data_issues(company_id, db)
    validation = data_quality.validate_data(company_id, db)

    # ── Derived KPIs ──────────────────────────────────────────────────────────
    neg_margin_products = sum(1 for m in margins if m["margem"] < 0)
    estimated_loss = sum(abs(m["margem"]) for m in margins if m["margem"] < 0)
    high_impact = sum(1 for i in op_insights if i["impact"] == "Alto")

    return {
        "company": {
            "id": company_id,
            "name": company_name,
            "sector": company_sector,
        },
        "kpis": {
            "receita_total": ceo["receita_total"],
            "receita_liquida": ceo["receita_liquida"],
            "score_juno": score,
            "total_delayed": len(delays),
            "neg_margin_products": neg_margin_products,
            "estimated_loss": estimated_loss,
            "high_impact_insights": high_impact,
        },
        "margin_by_product": margins,
        "delayed_orders": delays,
        "insights": all_insights,
        "trust": {
            "score": trust["score"],
            "label": trust["label"],
            "deductions": trust["deductions"],
        },
        "data_issues": dq_issues,
        "validation": validation,
    }
