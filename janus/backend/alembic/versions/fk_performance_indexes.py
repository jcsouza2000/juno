"""Indices de performance nas FKs de joins (sales/production/inventory).

As queries dos dashboards (cfo margin-by-product, insights, KPIs) fazem JOIN/
GROUP BY por product_id e filtram por company_id em tabelas grandes
(sales_orders ~100k+, production_orders ~70k+). Sem indice nessas colunas o
SQLite/Postgres faz varredura O(n*m) — observado 31s no cfo. Com os indices a
mesma chamada cai para ~0.3s.

Revision ID: fk_performance_indexes
Revises: companies_created_at
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fk_performance_indexes"
down_revision: str | None = "companies_created_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (nome_indice, tabela, coluna)
_INDEXES = [
    ("ix_sales_orders_product_id", "sales_orders", "product_id"),
    ("ix_sales_orders_company_id", "sales_orders", "company_id"),
    ("ix_sales_orders_customer_id", "sales_orders", "customer_id"),
    ("ix_production_orders_product_id", "production_orders", "product_id"),
    ("ix_production_orders_company_id", "production_orders", "company_id"),
    ("ix_inventory_product_id", "inventory", "product_id"),
]


def _existing_indexes(table: str) -> set[str]:
    bind = op.get_bind()
    return {ix["name"] for ix in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    for name, table, column in _INDEXES:
        if name not in _existing_indexes(table):
            op.create_index(name, table, [column])


def downgrade() -> None:
    for name, table, _column in _INDEXES:
        if name in _existing_indexes(table):
            op.drop_index(name, table_name=table)
