"""Add customer fields used by LGPD workflows.

Revision ID: customer_lgpd_fields
Revises: financial_upload_batches
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "customer_lgpd_fields"
down_revision: str | None = "financial_upload_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    columns = [
        ("email", sa.Column("email", sa.String(length=255), nullable=True)),
        ("phone", sa.Column("phone", sa.String(length=50), nullable=True)),
        ("address", sa.Column("address", sa.String(length=500), nullable=True)),
        ("document", sa.Column("document", sa.String(length=50), nullable=True)),
        ("is_active", sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true())),
        ("created_at", sa.Column("created_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in columns:
        if not _has_column("customers", name):
            op.add_column("customers", column)


def downgrade() -> None:
    for name in ["created_at", "is_active", "document", "address", "phone", "email"]:
        if _has_column("customers", name):
            op.drop_column("customers", name)
