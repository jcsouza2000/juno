"""fase5_erp_connectors

Revision ID: fase5_erp_connectors
Revises: fase3_erp_total
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'fase5_erp_connectors'
down_revision = 'fase3_erp_total'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # ERP CONNECTIONS (Configurações de conexão)
    # ============================================================
    op.create_table(
        'erp_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('erp_type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('connection_string', sa.Text(), nullable=True),
        sa.Column('host', sa.String(length=255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('database_name', sa.String(length=255), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password_encrypted', sa.Text(), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('api_secret', sa.Text(), nullable=True),
        sa.Column('webhook_url', sa.String(length=500), nullable=True),
        sa.Column('auth_method', sa.String(length=50), default='basic'),
        sa.Column('status', sa.String(length=50), default='inactive'),
        sa.Column('last_sync', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('sync_frequency_minutes', sa.Integer(), default=60),
        sa.Column('enabled_modules', sa.Text(), nullable=True),  # JSON
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_erp_connections_id', 'erp_connections', ['id'])
    op.create_index('ix_erp_connections_company_id', 'erp_connections', ['company_id'])
    
    # ============================================================
    # ERP SYNC LOGS (Log de sincronização)
    # ============================================================
    op.create_table(
        'erp_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connection_id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('records_found', sa.Integer(), default=0),
        sa.Column('records_imported', sa.Integer(), default=0),
        sa.Column('records_failed', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['erp_connections.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_erp_sync_logs_id', 'erp_sync_logs', ['id'])
    op.create_index('ix_erp_sync_logs_connection_id', 'erp_sync_logs', ['connection_id'])
    
    # ============================================================
    # ERP FIELD MAPPINGS (Mapeamento de campos)
    # ============================================================
    op.create_table(
        'erp_field_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connection_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('erp_field_name', sa.String(length=255), nullable=False),
        sa.Column('juno_field_name', sa.String(length=255), nullable=False),
        sa.Column('data_type', sa.String(length=50), default='string'),
        sa.Column('transform_rule', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['connection_id'], ['erp_connections.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('erp_field_mappings')
    op.drop_table('erp_sync_logs')
    op.drop_table('erp_connections')
