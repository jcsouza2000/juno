"""Ontology Sem8: tabela user_markings para grants de markings sensiveis.

Revision ID: ontology_sem8
Revises: audit_2026_05
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers
revision = "ontology_sem8"
down_revision = "audit_2026_05_consolidated"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_markings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("marking", sa.String(length=100), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("revoked", sa.Boolean(), default=False, nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"]),
    )
    op.create_index("ix_user_markings_user_id", "user_markings", ["user_id"])
    op.create_index("ix_user_markings_marking", "user_markings", ["marking"])
    op.create_index("ix_user_markings_revoked", "user_markings", ["revoked"])
    op.create_index("ix_user_markings_valid_until", "user_markings", ["valid_until"])
    # Indice util para lookup rapido de grants ativos
    op.create_index(
        "ix_user_markings_user_marking_active",
        "user_markings",
        ["user_id", "marking", "revoked"],
    )


def downgrade():
    op.drop_index("ix_user_markings_user_marking_active", table_name="user_markings")
    op.drop_index("ix_user_markings_valid_until", table_name="user_markings")
    op.drop_index("ix_user_markings_revoked", table_name="user_markings")
    op.drop_index("ix_user_markings_marking", table_name="user_markings")
    op.drop_index("ix_user_markings_user_id", table_name="user_markings")
    op.drop_table("user_markings")
