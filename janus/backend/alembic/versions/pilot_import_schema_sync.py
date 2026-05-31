"""Sync pilot import columns with current ORM models.

Revision ID: pilot_import_schema_sync
Revises: customer_lgpd_fields
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "pilot_import_schema_sync"
down_revision: str | None = "customer_lgpd_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    product_columns = [
        ("stock_quantity", sa.Column("stock_quantity", sa.Integer(), nullable=True, server_default="0")),
        ("min_stock", sa.Column("min_stock", sa.Integer(), nullable=True, server_default="0")),
        ("created_at", sa.Column("created_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in product_columns:
        if not _has_column("products", name):
            op.add_column("products", column)

    sales_columns = [
        ("total", sa.Column("total", sa.Float(), nullable=True, server_default="0")),
        ("created_at", sa.Column("created_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in sales_columns:
        if not _has_column("sales_orders", name):
            op.add_column("sales_orders", column)

    if not _has_column("production_orders", "created_at"):
        op.add_column("production_orders", sa.Column("created_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for name in ["created_at", "total"]:
        if _has_column("sales_orders", name):
            op.drop_column("sales_orders", name)

    if _has_column("production_orders", "created_at"):
        op.drop_column("production_orders", "created_at")

    for name in ["created_at", "min_stock", "stock_quantity"]:
        if _has_column("products", name):
            op.drop_column("products", name)
