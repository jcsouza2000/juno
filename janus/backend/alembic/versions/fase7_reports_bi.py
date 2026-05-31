"""fase7_reports_bi

Revision ID: fase7_reports_bi
Revises: fase6_ml_models
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'fase7_reports_bi'
down_revision = 'fase6_ml_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # REPORT DEFINITIONS (Definições de relatórios)
    # ============================================================
    op.create_table(
        'report_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(length=50), nullable=False),  # table, chart, pivot, dashboard
        sa.Column('data_source', sa.String(length=100), nullable=False),  # sql, entity, api, ml_prediction
        sa.Column('query_config', sa.Text(), nullable=True),  # JSON: {"sql": "...", "params": []}
        sa.Column('filter_config', sa.Text(), nullable=True),  # JSON: [{"field": "date", "operator": "between"}]
        sa.Column('column_config', sa.Text(), nullable=True),  # JSON: [{"field": "name", "label": "Nome", "type": "string"}]
        sa.Column('chart_config', sa.Text(), nullable=True),  # JSON: {"type": "bar", "x": "month", "y": "revenue"}
        sa.Column('sort_config', sa.Text(), nullable=True),  # JSON: [{"field": "date", "direction": "desc"}]
        sa.Column('group_by_config', sa.Text(), nullable=True),  # JSON: ["category", "region"]
        sa.Column('is_template', sa.Boolean(), default=False),
        sa.Column('template_category', sa.String(length=100), nullable=True),  # sales, inventory, financial, operational
        sa.Column('is_scheduled', sa.Boolean(), default=False),
        sa.Column('schedule_cron', sa.String(length=100), nullable=True),  # "0 8 * * 1" = toda segunda 8h
        sa.Column('schedule_recipients', sa.Text(), nullable=True),  # JSON: ["email1", "email2"]
        sa.Column('schedule_format', sa.String(length=20), default='pdf'),  # pdf, excel, csv
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), default='active'),  # active, draft, archived
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('last_executed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_count', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_report_definitions_id', 'report_definitions', ['id'])
    op.create_index('ix_report_definitions_company_id', 'report_definitions', ['company_id'])
    op.create_index('ix_report_definitions_type', 'report_definitions', ['report_type'])
    
    # ============================================================
    # DASHBOARD DEFINITIONS (Dashboards)
    # ============================================================
    op.create_table(
        'dashboard_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('layout_config', sa.Text(), nullable=True),  # JSON: {"columns": 12, "widgets": [...]}
        sa.Column('widget_configs', sa.Text(), nullable=True),  # JSON: [{"id": "w1", "type": "chart", "report_id": 1, "position": {"x": 0, "y": 0, "w": 6, "h": 4}}]
        sa.Column('refresh_interval_seconds', sa.Integer(), default=300),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), default='active'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dashboard_definitions_id', 'dashboard_definitions', ['id'])
    
    # ============================================================
    # REPORT EXECUTIONS (Execuções de relatórios)
    # ============================================================
    op.create_table(
        'report_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('executed_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), default='running'),  # running, completed, failed
        sa.Column('parameters', sa.Text(), nullable=True),  # JSON: {"date_from": "2026-01-01", "date_to": "2026-01-31"}
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_format', sa.String(length=20), nullable=True),  # pdf, excel, csv, json
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['report_definitions.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_report_executions_id', 'report_executions', ['id'])
    op.create_index('ix_report_executions_report_id', 'report_executions', ['report_id'])
    
    # ============================================================
    # REPORT FAVORITES (Favoritos do usuário)
    # ============================================================
    op.create_table(
        'report_favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=True),
        sa.Column('dashboard_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['report_id'], ['report_definitions.id']),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboard_definitions.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('report_favorites')
    op.drop_table('report_executions')
    op.drop_table('dashboard_definitions')
    op.drop_table('report_definitions')
