"""Add financial upload batch tracking.

Revision ID: financial_upload_batches
Revises: foundry_snapshots
Create Date: 2026-05-24
"""
import sqlalchemy as sa
from alembic import op


revision = "financial_upload_batches"
down_revision = "foundry_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "financial_upload_batches" in inspector.get_table_names():
        return

    op.create_table(
        "financial_upload_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("periods", sa.Text(), nullable=True),
        sa.Column("rows_imported", sa.Integer(), default=0),
        sa.Column("status", sa.String(length=50), default="success"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_upload_batches_company_id",
        "financial_upload_batches",
        ["company_id"],
    )
    op.create_index("ix_financial_upload_batches_id", "financial_upload_batches", ["id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "financial_upload_batches" not in inspector.get_table_names():
        return

    op.drop_index("ix_financial_upload_batches_id", table_name="financial_upload_batches")
    op.drop_index("ix_financial_upload_batches_company_id", table_name="financial_upload_batches")
    op.drop_table("financial_upload_batches")
