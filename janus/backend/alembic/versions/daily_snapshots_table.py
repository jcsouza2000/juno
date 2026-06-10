"""Create daily_snapshots table (Fase 5 — snapshot diario).

Revision ID: daily_snapshots_table
Revises: monthly_closes_table
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "daily_snapshots_table"
down_revision: str | None = "monthly_closes_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("daily_snapshots"):
        return
    op.create_table(
        "daily_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False, index=True),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", "snapshot_date", name="uq_daily_snapshot"),
    )


def downgrade() -> None:
    if _has_table("daily_snapshots"):
        op.drop_table("daily_snapshots")
