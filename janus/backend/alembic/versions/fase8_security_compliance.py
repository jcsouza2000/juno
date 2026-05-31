"""fase8_security_compliance

Revision ID: fase8_security_compliance
Revises: fase7_reports_bi
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'fase8_security_compliance'
down_revision = 'fase7_reports_bi'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # ROLES (Papeis de acesso)
    # ============================================================
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), default=False),
        sa.Column('permissions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_roles_id', 'roles', ['id'])
    op.create_index('ix_roles_company_id', 'roles', ['company_id'])

    # ============================================================
    # USER ROLES (Associacao usuario-papel)
    # ============================================================
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('granted_by', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role')
    )

    # ============================================================
    # AUDIT LOG (Log de auditoria completo — substituindo schema antigo)
    # ============================================================
    # Remover tabela antiga com schema limitado (sem dados)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP TABLE IF EXISTS audit_logs CASCADE')
    else:
        op.execute('DROP TABLE IF EXISTS audit_logs')
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('old_values', sa.Text(), nullable=True),
        sa.Column('new_values', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.Column('success', sa.Boolean(), default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), default='info'),
        sa.Column('compliance_tags', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_company_id', 'audit_logs', ['company_id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])

    # ============================================================
    # DATA SUBJECT REQUESTS (Requisicoes LGPD/GDPR)
    # ============================================================
    op.create_table(
        'data_subject_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), default='pending'),
        sa.Column('data_subject_email', sa.String(length=255), nullable=False),
        sa.Column('data_subject_name', sa.String(length=255), nullable=True),
        sa.Column('data_subject_type', sa.String(length=50), default='customer'),
        sa.Column('request_details', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('deadline_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by', sa.Integer(), nullable=True),
        sa.Column('response_data', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('legal_basis', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_data_subject_requests_id', 'data_subject_requests', ['id'])
    op.create_index('ix_data_subject_requests_status', 'data_subject_requests', ['status'])

    # ============================================================
    # CONSENT RECORDS (Registro de consentimentos LGPD)
    # ============================================================
    op.create_table(
        'consent_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('data_subject_email', sa.String(length=255), nullable=False),
        sa.Column('consent_type', sa.String(length=100), nullable=False),
        sa.Column('consent_given', sa.Boolean(), default=False),
        sa.Column('consent_version', sa.String(length=50), default='1.0'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('consent_text', sa.Text(), nullable=True),
        sa.Column('withdrawn_at', sa.DateTime(), nullable=True),
        sa.Column('withdrawn_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_consent_records_email', 'consent_records', ['data_subject_email'])

    # ============================================================
    # SECURITY SETTINGS (Configuracoes de seguranca por empresa)
    # ============================================================
    op.create_table(
        'security_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('password_policy', sa.Text(), nullable=True),
        sa.Column('mfa_required', sa.Boolean(), default=False),
        sa.Column('mfa_methods', sa.Text(), nullable=True),
        sa.Column('session_timeout_minutes', sa.Integer(), default=30),
        sa.Column('max_login_attempts', sa.Integer(), default=5),
        sa.Column('lockout_duration_minutes', sa.Integer(), default=30),
        sa.Column('require_password_change_days', sa.Integer(), default=90),
        sa.Column('allowed_ip_ranges', sa.Text(), nullable=True),
        sa.Column('data_retention_days', sa.Integer(), default=2555),
        sa.Column('audit_retention_days', sa.Integer(), default=2555),
        sa.Column('encryption_at_rest', sa.Boolean(), default=True),
        sa.Column('encryption_in_transit', sa.Boolean(), default=True),
        sa.Column('gdpr_enabled', sa.Boolean(), default=True),
        sa.Column('lgpd_enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ============================================================
    # LOGIN ATTEMPTS (Protecao contra brute force)
    # ============================================================
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('success', sa.Boolean(), default=False),
        sa.Column('failure_reason', sa.String(length=255), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_login_attempts_username', 'login_attempts', ['username'])
    op.create_index('ix_login_attempts_ip', 'login_attempts', ['ip_address'])
    op.create_index('ix_login_attempts_created', 'login_attempts', ['created_at'])


def downgrade() -> None:
    op.drop_table('login_attempts')
    op.drop_table('security_settings')
    op.drop_table('consent_records')
    op.drop_table('data_subject_requests')
    op.drop_table('audit_logs')
    op.drop_table('user_roles')
    op.drop_table('roles')
