"""Create monthly_closes table (Fase 5 — retencao / fechamento mensal).

Revision ID: monthly_closes_table
Revises: pilot_import_schema_sync
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "monthly_closes_table"
down_revision: str | None = "pilot_import_schema_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("monthly_closes"):
        return
    op.create_table(
        "monthly_closes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="closed"),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("company_id", "year", "month", name="uq_monthly_close"),
    )


def downgrade() -> None:
    if _has_table("monthly_closes"):
        op.drop_table("monthly_closes")
