from sqlalchemy import func
from sqlalchemy.orm import Session

from app.financials import get_dre_flow_totals
from app.score_v2 import get_score_calculator

from .models import Product, ProductionOrder, SalesOrder

OPEN_PRODUCTION_STATUSES = ("aberto", "aberta", "planned", "planejada", "em_andamento", "em andamento")


def get_ceo_kpis(db: Session, company_id: int):
    results = (
        db.query(
            func.sum(SalesOrder.revenue).label("receita_total"),
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita_liquida"),
        )
        .filter(SalesOrder.company_id == company_id)
        .first()
    )

    receita_total = results.receita_total if results else 0
    receita_liquida = results.receita_liquida if results else 0

    dre_totals = get_dre_flow_totals(company_id, db)
    if dre_totals:
        receita_total = dre_totals["receita_liquida"]
        receita_liquida = dre_totals["receita_liquida"]

    try:
        score_juno = get_score_calculator(db).calculate_full_score(company_id, persist=False).overall_score
    except Exception:
        score_juno = 50.0

    return {
        "receita_total": float(receita_total or 0),
        "receita_liquida": float(receita_liquida or 0),
        "score_juno": score_juno,
    }


def get_cfo_margin_by_product(db: Session, company_id: int):
    # Margin = actual revenue - (units_sold × standard_cost)
    # Avoids production-batch vs sales mismatch by using the product's standard cost as unit cost
    results = (
        db.query(
            Product.name,
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita_liquida"),
            func.count(SalesOrder.id).label("qtd_vendas"),
            Product.standard_cost,
        )
        .join(SalesOrder, SalesOrder.product_id == Product.id)
        .filter(Product.company_id == company_id)
        .group_by(Product.id, Product.name, Product.standard_cost)
        .all()
    )

    data = []
    for row in results:
        receita = float(row.receita_liquida or 0)
        custo = float(row.qtd_vendas) * float(row.standard_cost or 0)
        data.append(
            {
                "product": row.name,
                "receita_liquida": receita,
                "custo_real": custo,
                "margem": receita - custo,
            }
        )

    return sorted(data, key=lambda x: x["margem"])


def get_coo_delayed_orders(db: Session, company_id: int):
    results = (
        db.query(
            ProductionOrder.id,
            Product.name,
            ProductionOrder.planned_date,
            ProductionOrder.actual_date,
            ProductionOrder.status,
        )
        .join(Product, Product.id == ProductionOrder.product_id)
        .filter(ProductionOrder.company_id == company_id)
        .filter(
            ((ProductionOrder.actual_date.isnot(None)) & (ProductionOrder.actual_date > ProductionOrder.planned_date))
            | (
                (ProductionOrder.actual_date.is_(None))
                & (ProductionOrder.planned_date < func.now())
                & func.lower(func.coalesce(ProductionOrder.status, "")).in_(
                    OPEN_PRODUCTION_STATUSES
                )
            )
        )
        .all()
    )

    return [
        {
            "order_id": r.id,
            "product": r.name,
            "planned_date": r.planned_date.isoformat() if r.planned_date else None,
            "actual_date": r.actual_date.isoformat() if r.actual_date else None,
            "status": r.status,
        }
        for r in results
    ]
