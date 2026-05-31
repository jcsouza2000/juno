"""Foundry.3: snapshots + time-travel.

Revision ID: foundry_snapshots
Revises: ontology_sem8
Create Date: 2026-05-22
"""
import sqlalchemy as sa
from alembic import op

revision = "foundry_snapshots"
down_revision = "ontology_sem8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("object_type", sa.String(length=100), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("row_count", sa.Integer(), default=0),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_dataset_snapshots_name", "dataset_snapshots", ["name"])
    op.create_index("ix_dataset_snapshots_object_type", "dataset_snapshots", ["object_type"])
    op.create_index("ix_dataset_snapshots_company", "dataset_snapshots", ["company_id"])


def downgrade():
    op.drop_index("ix_dataset_snapshots_company", table_name="dataset_snapshots")
    op.drop_index("ix_dataset_snapshots_object_type", table_name="dataset_snapshots")
    op.drop_index("ix_dataset_snapshots_name", table_name="dataset_snapshots")
    op.drop_table("dataset_snapshots")
