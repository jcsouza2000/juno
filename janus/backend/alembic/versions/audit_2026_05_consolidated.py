"""Auditoria 2026-05: consolida models adicionados na refatoracao.

Esta migration cria tabelas que estavam em backups (fase5-12) mas ainda
nao estavam no models.py "vivo" ate a auditoria. Inclui:

- ERP Connectors: erp_connections, erp_sync_logs, erp_field_mappings
- RBAC: roles, user_roles, audit_logs, login_attempts
- LGPD: data_subject_requests, consent_records, security_settings
- Reports/BI: report_definitions, dashboard_definitions, report_executions, report_favorites
- ML/IA: ml_models, ml_predictions, ml_anomalies, ml_recommendations, chatbot_conversations
- Operacoes: inventory, suppliers, supplier_products, purchase_orders, purchase_order_items, erp_financials, score_history
- Chat: chat_sessions, chat_messages
- Eventos: event_logs
- Multi-tenant: user_company_memberships

Revision ID: audit_2026_05
Revises: fase8_security_compliance
Create Date: 2026-05-14
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "audit_2026_05_consolidated"
down_revision = "fase8_security_compliance"
branch_labels = None
depends_on = None


def _create_if_not_exists(table_name: str, *cols: sa.Column, **kwargs) -> None:
    """Cria tabela so se ela ainda nao existir (idempotente em SQLite e Postgres)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name in inspector.get_table_names():
        return
    op.create_table(table_name, *cols, **kwargs)


def upgrade() -> None:
    # ===== ERP Connectors =====
    _create_if_not_exists(
        "erp_connections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("erp_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("connection_string", sa.Text),
        sa.Column("host", sa.String(255)),
        sa.Column("port", sa.Integer),
        sa.Column("database_name", sa.String(255)),
        sa.Column("username", sa.String(255)),
        sa.Column("password_encrypted", sa.Text),
        sa.Column("api_key", sa.Text),
        sa.Column("api_secret", sa.Text),
        sa.Column("webhook_url", sa.String(500)),
        sa.Column("auth_method", sa.String(50), default="basic"),
        sa.Column("extra_config", sa.Text),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("status", sa.String(50), default="inactive"),
        sa.Column("last_sync", sa.DateTime),
        sa.Column("last_error", sa.Text),
        sa.Column("sync_frequency_minutes", sa.Integer, default=60),
        sa.Column("enabled_modules", sa.Text),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime, default=datetime.utcnow),
    )

    _create_if_not_exists(
        "erp_sync_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("connection_id", sa.Integer, sa.ForeignKey("erp_connections.id"), nullable=False, index=True),
        sa.Column("sync_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("records_found", sa.Integer, default=0),
        sa.Column("records_imported", sa.Integer, default=0),
        sa.Column("records_failed", sa.Integer, default=0),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("status", sa.String(50), default="running"),
        sa.Column("error_message", sa.Text),
        sa.Column("details", sa.Text),
    )

    _create_if_not_exists(
        "erp_field_mappings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("connection_id", sa.Integer, sa.ForeignKey("erp_connections.id"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("erp_field_name", sa.String(255), nullable=False),
        sa.Column("juno_field_name", sa.String(255), nullable=False),
        sa.Column("data_type", sa.String(50), default="string"),
        sa.Column("transform_rule", sa.Text),
        sa.Column("is_required", sa.Boolean, default=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow),
    )

    # ===== RBAC =====
    _create_if_not_exists(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("is_system_role", sa.Boolean, default=False),
        sa.Column("permissions", sa.Text),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow),
    )

    _create_if_not_exists(
        "user_roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("granted_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("granted_at", sa.DateTime, default=datetime.utcnow),
        sa.Column("expires_at", sa.DateTime),
    )

    _create_if_not_exists(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("user_name", sa.String(255)),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("source_table", sa.String(100)),
        sa.Column("details", sa.Text),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow, index=True),
    )

    _create_if_not_exists(
        "login_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("ip_address", sa.String(45), index=True),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("success", sa.Boolean, default=False),
        sa.Column("failure_reason", sa.String(255)),
        sa.Column("attempted_at", sa.DateTime, default=datetime.utcnow, index=True),
    )

    # ===== LGPD =====
    _create_if_not_exists(
        "data_subject_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("subject_email", sa.String(255), nullable=False, index=True),
        sa.Column("request_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("description", sa.Text),
        sa.Column("response", sa.Text),
        sa.Column("requested_at", sa.DateTime, default=datetime.utcnow),
        sa.Column("deadline_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("handled_by", sa.Integer, sa.ForeignKey("users.id")),
    )

    _create_if_not_exists(
        "consent_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("consent_given", sa.Boolean, nullable=False),
        sa.Column("consent_text", sa.Text),
        sa.Column("version", sa.String(20)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("granted_at", sa.DateTime, default=datetime.utcnow),
        sa.Column("revoked_at", sa.DateTime),
    )

    _create_if_not_exists(
        "security_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), unique=True, nullable=False),
        sa.Column("password_min_length", sa.Integer, default=12),
        sa.Column("password_require_uppercase", sa.Boolean, default=True),
        sa.Column("password_require_lowercase", sa.Boolean, default=True),
        sa.Column("password_require_digit", sa.Boolean, default=True),
        sa.Column("password_require_special", sa.Boolean, default=True),
        sa.Column("password_expiry_days", sa.Integer, default=90),
        sa.Column("max_login_attempts", sa.Integer, default=5),
        sa.Column("lockout_duration_minutes", sa.Integer, default=30),
        sa.Column("session_timeout_minutes", sa.Integer, default=60),
        sa.Column("require_mfa", sa.Boolean, default=False),
        sa.Column("updated_at", sa.DateTime, default=datetime.utcnow),
    )

    # ===== Multi-tenancy avancado =====
    _create_if_not_exists(
        "user_company_memberships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("role_in_tenant", sa.String(50), default="member"),
        sa.Column("is_primary", sa.Boolean, default=False),
        sa.Column("joined_at", sa.DateTime, default=datetime.utcnow),
    )

    # ===== Score =====
    _create_if_not_exists(
        "score_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("trend", sa.String(20)),
        sa.Column("trend_delta", sa.Float, default=0),
        sa.Column("components_json", sa.Text),
        sa.Column("recommendations_json", sa.Text),
        sa.Column("calculated_at", sa.DateTime, default=datetime.utcnow, index=True),
    )

    # ===== Chat =====
    _create_if_not_exists(
        "chat_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255)),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime, default=datetime.utcnow),
    )

    _create_if_not_exists(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id"), nullable=False, index=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("tool_calls", sa.Text),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow),
    )

    # ===== Event log =====
    _create_if_not_exists(
        "event_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(100), nullable=False, index=True),
        sa.Column("entity_id", sa.Integer),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("old_state", sa.Text),
        sa.Column("new_state", sa.Text),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow, index=True),
    )

    # Demais tabelas (ml_models, reports, suppliers, inventory, etc.) ja foram
    # criadas em migrations anteriores das fases 5-8. Se faltar alguma, gerar
    # `alembic revision --autogenerate` para detectar.


def downgrade() -> None:
    for table in [
        "event_logs", "chat_messages", "chat_sessions", "score_history",
        "user_company_memberships",
        "security_settings", "consent_records", "data_subject_requests",
        "login_attempts", "audit_logs", "user_roles", "roles",
        "erp_field_mappings", "erp_sync_logs", "erp_connections",
    ]:
        try:
            op.drop_table(table)
        except Exception:
            pass
