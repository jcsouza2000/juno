"""Golden datasets for canonical KPI tests.

Keep this fixture intentionally small. It is not a demo dataset; it is the
minimum accounting and operations sample used to prove formulas stay stable.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.models import Company, Customer, FinancialStatement, Product, ProductionOrder, SalesOrder


GOLDEN_EXPECTED = {
    "receita_bruta": 1500.0,
    "receita_liquida": 1400.0,
    "lucro_bruto_dre": 960.0,
    "margem_produtos_total": 1220.0,
    "margem_media_pct": 68.57,
    "ordens_atrasadas": 2,
    "liquidez_corrente": 2.0,
    "endividamento_pct": 40.0,
    "score_juno": 54.29,
}


def seed_golden_company(db: Session) -> Company:
    """Create one deterministic company with enough data for critical KPIs."""
    now = utcnow_naive()
    company = Company(name="Golden KPI Co", sector="industria geral")
    db.add(company)
    db.flush()

    product_a = Product(
        company_id=company.id,
        name="Produto A",
        standard_cost=60,
        sale_price=100,
        stock_quantity=10,
        min_stock=2,
    )
    product_b = Product(
        company_id=company.id,
        name="Produto B",
        standard_cost=120,
        sale_price=100,
        stock_quantity=5,
        min_stock=1,
    )
    customer_a = Customer(company_id=company.id, name="Cliente A")
    customer_b = Customer(company_id=company.id, name="Cliente B")
    db.add_all([product_a, product_b, customer_a, customer_b])
    db.flush()

    db.add_all(
        [
            SalesOrder(
                company_id=company.id,
                product_id=product_a.id,
                customer_id=customer_a.id,
                revenue=1000,
                discount=100,
                total=900,
                order_date=now,
            ),
            SalesOrder(
                company_id=company.id,
                product_id=product_b.id,
                customer_id=customer_b.id,
                revenue=500,
                discount=0,
                total=500,
                order_date=now,
            ),
            ProductionOrder(
                company_id=company.id,
                product_id=product_a.id,
                planned_qty=10,
                actual_qty=10,
                planned_cost=100,
                actual_cost=100,
                planned_date=now - timedelta(days=5),
                actual_date=now - timedelta(days=5),
                status="done",
            ),
            ProductionOrder(
                company_id=company.id,
                product_id=product_a.id,
                planned_qty=10,
                actual_qty=10,
                planned_cost=100,
                actual_cost=120,
                planned_date=now - timedelta(days=5),
                actual_date=now - timedelta(days=2),
                status="done",
            ),
            ProductionOrder(
                company_id=company.id,
                product_id=product_b.id,
                planned_qty=5,
                actual_qty=0,
                planned_cost=80,
                actual_cost=0,
                planned_date=now - timedelta(days=1),
                actual_date=None,
                status="planned",
            ),
        ]
    )

    financial_rows = [
        ("DRE", "2026-01", "receita_bruta", 1500),
        ("DRE", "2026-01", "receita_liquida", 1400),
        ("DRE", "2026-01", "lucro_bruto", 960),
        ("DRE", "2026-01", "ebitda", 300),
        ("DRE", "2026-01", "lucro_liquido", 210),
        ("BALANCO", "2026-01", "ativo_circulante", 200),
        ("BALANCO", "2026-01", "passivo_circulante", 100),
        ("BALANCO", "2026-01", "passivo_nao_circulante", 100),
        ("BALANCO", "2026-01", "patrimonio_liquido", 300),
        ("DFC", "2026-01", "caixa_operacional", 250),
        ("DFC", "2026-01", "caixa_investimento", -50),
        ("DFC", "2026-01", "caixa_financiamento", 0),
        ("DFC", "2026-01", "variacao_caixa", 200),
        ("DFC", "2026-01", "caixa_final", 500),
    ]
    db.add_all(
        [
            FinancialStatement(
                company_id=company.id,
                statement_type=statement_type,
                period=period,
                line_item=line_item,
                value=value,
            )
            for statement_type, period, line_item, value in financial_rows
        ]
    )
    db.commit()
    db.refresh(company)
    return company
