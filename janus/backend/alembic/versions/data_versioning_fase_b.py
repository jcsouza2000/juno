"""Fase B — versionamento de depositos (financial + erp batches, batch_id em statements).

Revision ID: data_versioning_fase_b
Revises: daily_snapshots_table
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "data_versioning_fase_b"
down_revision: str | None = "daily_snapshots_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("financial_upload_batches", "version_number"):
        op.add_column(
            "financial_upload_batches",
            sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
        )
    if not _has_column("financial_upload_batches", "is_active"):
        op.add_column(
            "financial_upload_batches",
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        )

    if not _has_column("erp_import_batches", "version_number"):
        op.add_column(
            "erp_import_batches",
            sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
        )
    if not _has_column("erp_import_batches", "is_active"):
        op.add_column(
            "erp_import_batches",
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        )

    if not _has_column("financial_statements", "upload_batch_id"):
        with op.batch_alter_table("financial_statements") as batch_op:
            batch_op.add_column(sa.Column("upload_batch_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_financial_statements_upload_batch",
                "financial_upload_batches",
                ["upload_batch_id"],
                ["id"],
            )
        op.create_index(
            "ix_financial_statements_upload_batch_id",
            "financial_statements",
            ["upload_batch_id"],
        )

    bind = op.get_bind()
    for table in ("financial_upload_batches", "erp_import_batches"):
        bind.execute(sa.text(f"UPDATE {table} SET is_active = false"))
        bind.execute(
            sa.text(
                f"""
                UPDATE {table} SET is_active = true
                WHERE id IN (
                    SELECT MAX(id) FROM {table} GROUP BY company_id
                )
                """
            )
        )


def downgrade() -> None:
    if _has_column("financial_statements", "upload_batch_id"):
        op.drop_index("ix_financial_statements_upload_batch_id", table_name="financial_statements")
        with op.batch_alter_table("financial_statements") as batch_op:
            batch_op.drop_constraint("fk_financial_statements_upload_batch", type_="foreignkey")
            batch_op.drop_column("upload_batch_id")
    if _has_column("erp_import_batches", "is_active"):
        op.drop_column("erp_import_batches", "is_active")
    if _has_column("erp_import_batches", "version_number"):
        op.drop_column("erp_import_batches", "version_number")
    if _has_column("financial_upload_batches", "is_active"):
        op.drop_column("financial_upload_batches", "is_active")
    if _has_column("financial_upload_batches", "version_number"):
        op.drop_column("financial_upload_batches", "version_number")
