from sqlalchemy import func
from sqlalchemy.orm import Session

from .core.i18n import tr
from .models import Product, ProductionOrder, SalesOrder

OPEN_PRODUCTION_STATUSES = (
    "aberto",
    "aberta",
    "planned",
    "planejada",
    "em_andamento",
    "em andamento",
)


def generate_insights(company_id: int, db: Session, lang: str = "pt"):
    insights = []

    # 1. Negative Margin Risk — revenue vs standard_cost × units_sold
    margin_results = (
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

    for row in margin_results:
        receita = float(row.receita_liquida or 0)
        custo = float(row.qtd_vendas) * float(row.standard_cost or 0)
        margin = receita - custo
        if margin < 0:
            insights.append(
                {
                    "type": "margin_risk",
                    "message": tr(
                        "insight.margin.message", lang, name=row.name, margin=f"{margin:,.0f}"
                    ),
                    "impact": tr("impact.high", lang),
                    "action": tr("insight.margin.action", lang),
                }
            )

    # 2. Production Delays
    delay_count = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .filter(
            (
                (ProductionOrder.actual_date.isnot(None))
                & (ProductionOrder.actual_date > ProductionOrder.planned_date)
            )
            | (
                (ProductionOrder.actual_date.is_(None))
                & (ProductionOrder.planned_date < func.now())
                & func.lower(func.coalesce(ProductionOrder.status, "")).in_(
                    OPEN_PRODUCTION_STATUSES
                )
            )
        )
        .scalar()
    )

    if delay_count > 0:
        insights.append(
            {
                "type": "delay_risk",
                "message": tr("insight.delay.message", lang, count=delay_count),
                "impact": tr("impact.medium", lang),
                "action": tr("insight.delay.action", lang),
            }
        )

    # 3. Cost Overrun (Planned vs Actual)
    cost_overrun = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .filter(ProductionOrder.actual_cost > ProductionOrder.planned_cost * 1.1)
        .scalar()
    )

    if cost_overrun > 0:
        insights.append(
            {
                "type": "cost_risk",
                "message": tr("insight.cost.message", lang, count=cost_overrun),
                "impact": tr("impact.high", lang),
                "action": tr("insight.cost.action", lang),
            }
        )

    return insights


def calculate_juno_score(company_id: int, db: Session):
    score = 100

    # 1. Margin penalty — use standard_cost × units_sold vs revenue
    product_margins = (
        db.query(
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita"),
            func.count(SalesOrder.id).label("qtd"),
            Product.standard_cost,
        )
        .join(Product, Product.id == SalesOrder.product_id)
        .filter(SalesOrder.company_id == company_id)
        .group_by(Product.id, Product.standard_cost)
        .all()
    )

    if product_margins:
        total_receita = sum(float(r.receita or 0) for r in product_margins)
        total_custo = sum(float(r.qtd) * float(r.standard_cost or 0) for r in product_margins)
        avg_margin = (total_receita - total_custo) / total_receita if total_receita else 0.2
    else:
        avg_margin = 0.2

    if avg_margin < 0.15:
        score -= 20

    # 2. Delay penalty
    delays = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .filter(
            (
                (ProductionOrder.actual_date.isnot(None))
                & (ProductionOrder.actual_date > ProductionOrder.planned_date)
            )
            | (
                (ProductionOrder.actual_date.is_(None))
                & (ProductionOrder.planned_date < func.now())
                & func.lower(func.coalesce(ProductionOrder.status, "")).in_(
                    OPEN_PRODUCTION_STATUSES
                )
            )
        )
        .scalar()
    )
    if delays > 0:
        score -= min(delays * 5, 20)

    # 3. Efficiency penalty (Stubbed for now, using cost overrun as proxy)
    cost_overruns = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .filter(ProductionOrder.actual_cost > ProductionOrder.planned_cost)
        .scalar()
    )
    if cost_overruns > 2:
        score -= 15

    return max(score, 0)
