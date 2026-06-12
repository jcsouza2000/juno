"""Adiciona companies.created_at ausente no PostgreSQL fresh install.

Revision ID: companies_created_at
Revises: data_versioning_fase_b
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "companies_created_at"
down_revision: str | None = "data_versioning_fase_b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("companies", "created_at"):
        op.add_column("companies", sa.Column("created_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    if _has_column("companies", "created_at"):
        op.drop_column("companies", "created_at")
