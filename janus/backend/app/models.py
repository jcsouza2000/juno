"""
Models SQLAlchemy do JUNO Backend.

Organizado por dominio:
  1. Multi-tenancy: Company, User, user_companies
  2. Catalogo: Product, Customer, Supplier, SupplierProduct
  3. Operacoes: SalesOrder, ProductionOrder, Inventory, PurchaseOrder, PurchaseOrderItem
  4. Financeiro: FinancialStatement, ErpFinancial
  5. Importacao: ERPImportBatch (alias ErpImportBatch)
  6. ERP Connectors: ERPConnection, ERPSyncLog, ERPFieldMapping
  7. Seguranca/RBAC: Role, UserRole, AuditLog
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship

from app.core.datetime_utils import utcnow_naive
from app.database import Base

# =====================================================================
# 1. Multi-tenancy
# =====================================================================

user_companies = Table(
    "user_companies",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("company_id", Integer, ForeignKey("companies.id")),
)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(255))
    revenue_year = Column(Float, default=0)
    created_at = Column(DateTime, default=utcnow_naive)

    users: Mapped[list[User]] = relationship(
        "User", secondary=user_companies, back_populates="companies"
    )
    tenant_memberships: Mapped[list[UserCompany]] = relationship(
        "UserCompany", back_populates="company"
    )
    products: Mapped[list[Product]] = relationship("Product", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)

    companies: Mapped[list[Company]] = relationship(
        "Company", secondary=user_companies, back_populates="users"
    )
    tenant_memberships: Mapped[list[UserCompany]] = relationship(
        "UserCompany", back_populates="user"
    )


# =====================================================================
# 2. Catalogo
# =====================================================================


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(255))
    standard_cost = Column(Float, default=0)
    sale_price = Column(Float, default=0)
    stock_quantity = Column(Integer, default=0)
    min_stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow_naive)

    company: Mapped[Company] = relationship("Company", back_populates="products")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    segment = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(String(500))
    document = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    cnpj = Column(String(20))
    contact_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(String(500))
    payment_terms = Column(String(100))
    lead_time_days = Column(Integer, default=0)
    rating = Column(Float, default=0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=utcnow_naive)


class SupplierProduct(Base):
    __tablename__ = "supplier_products"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    supplier_sku = Column(String(100))
    unit_cost = Column(Float, default=0)
    min_order_qty = Column(Integer, default=1)
    last_purchase_date = Column(DateTime)
    created_at = Column(DateTime, default=utcnow_naive)


# =====================================================================
# 3. Operacoes
# =====================================================================


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    revenue = Column(Float, default=0)
    discount = Column(Float, default=0)
    total = Column(Float, default=0)
    order_date = Column(DateTime)
    created_at = Column(DateTime, default=utcnow_naive)


class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    planned_qty = Column(Integer, default=0)
    actual_qty = Column(Integer, default=0)
    planned_cost = Column(Float, default=0)
    actual_cost = Column(Float, default=0)
    planned_date = Column(DateTime)
    actual_date = Column(DateTime)
    status = Column(String(50), default="planned")
    created_at = Column(DateTime, default=utcnow_naive)


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    warehouse_location = Column(String(100))
    quantity_on_hand = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    quantity_available = Column(Integer, default=0)
    unit_cost = Column(Float, default=0)
    last_movement_date = Column(DateTime)
    min_stock_level = Column(Integer, default=0)
    max_stock_level = Column(Integer, default=0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=utcnow_naive)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    order_number = Column(String(100))
    status = Column(String(50), default="draft")
    total_amount = Column(Float, default=0)
    order_date = Column(DateTime)
    expected_date = Column(DateTime)
    received_date = Column(DateTime)
    created_at = Column(DateTime, default=utcnow_naive)


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=0)
    unit_cost = Column(Float, default=0)
    total_cost = Column(Float, default=0)
    received_qty = Column(Integer, default=0)


# =====================================================================
# 4. Financeiro
# =====================================================================


class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    upload_batch_id = Column(
        Integer, ForeignKey("financial_upload_batches.id"), nullable=True, index=True
    )
    statement_type = Column(String(50), nullable=False)
    period = Column(String(50))
    line_item = Column(String(255), nullable=False)
    value = Column(Float, default=0)
    created_at = Column(DateTime, default=utcnow_naive)


class FinancialUploadBatch(Base):
    __tablename__ = "financial_upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    file_name = Column(String(255))
    periods = Column(Text)
    rows_imported = Column(Integer, default=0)
    status = Column(String(50), default="success")
    version_number = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)


class ErpFinancial(Base):
    __tablename__ = "erp_financials"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    document_type = Column(String(50), nullable=False)
    document_number = Column(String(100))
    account_code = Column(String(50))
    account_name = Column(String(255))
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    balance = Column(Float, default=0)
    period = Column(String(50))
    posting_date = Column(DateTime)
    created_at = Column(DateTime, default=utcnow_naive)


# =====================================================================
# 5. Importacao
# =====================================================================


class ERPImportBatch(Base):
    __tablename__ = "erp_import_batches"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    data_type = Column(String(50), nullable=False)
    file_name = Column(String(255))
    rows_received = Column(Integer, default=0)
    rows_imported = Column(Integer, default=0)
    rows_rejected = Column(Integer, default=0)
    status = Column(String(50), default="processing")
    error_message = Column(Text)
    version_number = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)


# Alias para compatibilidade com codigo legado (connector_importer.py).
ErpImportBatch = ERPImportBatch


# =====================================================================
# 6. ERP Connectors
# =====================================================================


class ERPConnection(Base):
    __tablename__ = "erp_connections"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    erp_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)

    connection_string = Column(Text)
    host = Column(String(255))
    port = Column(Integer)
    database_name = Column(String(255))
    username = Column(String(255))
    password_encrypted = Column(Text)
    api_key = Column(Text)
    api_secret = Column(Text)
    webhook_url = Column(String(500))
    auth_method = Column(String(50), default="basic")
    extra_config = Column(Text)

    is_active = Column(Boolean, default=True)
    status = Column(String(50), default="inactive")
    last_sync = Column(DateTime)
    last_error = Column(Text)
    sync_frequency_minutes = Column(Integer, default=60)
    enabled_modules = Column(Text)

    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    company: Mapped[Company] = relationship("Company")
    sync_logs: Mapped[list[ERPSyncLog]] = relationship(
        "ERPSyncLog", back_populates="connection", cascade="all, delete-orphan"
    )
    field_mappings: Mapped[list[ERPFieldMapping]] = relationship(
        "ERPFieldMapping", back_populates="connection", cascade="all, delete-orphan"
    )


class ERPSyncLog(Base):
    __tablename__ = "erp_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("erp_connections.id"), nullable=False, index=True)
    sync_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)

    records_found = Column(Integer, default=0)
    records_imported = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)

    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_seconds = Column(Float)

    status = Column(String(50), default="running")
    error_message = Column(Text)
    details = Column(Text)

    connection: Mapped[ERPConnection] = relationship("ERPConnection", back_populates="sync_logs")


class ERPFieldMapping(Base):
    __tablename__ = "erp_field_mappings"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("erp_connections.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    erp_field_name = Column(String(255), nullable=False)
    juno_field_name = Column(String(255), nullable=False)
    data_type = Column(String(50), default="string")
    transform_rule = Column(Text)
    is_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)

    connection: Mapped[ERPConnection] = relationship(
        "ERPConnection", back_populates="field_mappings"
    )


# =====================================================================
# 7. Seguranca / RBAC / Auditoria
# =====================================================================


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    is_system_role = Column(Boolean, default=False)
    permissions = Column(Text)
    created_at = Column(DateTime, default=utcnow_naive)


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    granted_by = Column(Integer, ForeignKey("users.id"))
    granted_at = Column(DateTime, default=utcnow_naive)
    expires_at = Column(DateTime)

    role: Mapped[Role] = relationship("Role")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(Integer)
    old_values = Column(Text)
    new_values = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    session_id = Column(String(255))
    request_id = Column(String(255))
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    severity = Column(String(20), default="info")
    compliance_tags = Column(Text)
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    @property
    def source_table(self) -> str | None:
        return self.resource_type

    @source_table.setter
    def source_table(self, value: str | None) -> None:
        self.resource_type = value

    @property
    def details(self) -> str | None:
        return self.new_values

    @details.setter
    def details(self, value: str | None) -> None:
        self.new_values = value

    @property
    def user_name(self) -> str | None:
        return f"user:{self.user_id}" if self.user_id is not None else None

    @user_name.setter
    def user_name(self, value: str | None) -> None:
        # Compatibilidade com chamadas legadas; o schema persistente usa user_id.
        return None


# =====================================================================
# 8. Multi-tenancy avancado (UserCompany como model)
# =====================================================================


class UserCompany(Base):
    """Associacao usuario-empresa com metadados (papel no tenant, data)."""

    __tablename__ = "user_company_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    role_in_tenant = Column(String(50), default="member")
    is_primary = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=utcnow_naive)

    user: Mapped[User] = relationship("User", back_populates="tenant_memberships")
    company: Mapped[Company] = relationship("Company", back_populates="tenant_memberships")


# =====================================================================
# 9. Scoring
# =====================================================================


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    score_date = Column(DateTime, nullable=False, default=utcnow_naive)
    overall_score = Column(Float, nullable=False)
    margin_score = Column(Float, default=0)
    liquidity_score = Column(Float, default=0)
    debt_score = Column(Float, default=0)
    production_score = Column(Float, default=0)
    data_quality_score = Column(Float, default=0)
    details = Column(Text)
    created_at = Column(DateTime, default=utcnow_naive)


class MonthlyClose(Base):
    """Fechamento mensal imutavel (Fase 5 — retencao).

    Congela um snapshot de KPIs/demonstracoes do tenant para um (ano, mes).
    Unico por (company_id, year, month). Apos criado, e' tratado como imutavel.
    """

    __tablename__ = "monthly_closes"
    __table_args__ = (UniqueConstraint("company_id", "year", "month", name="uq_monthly_close"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    snapshot = Column(Text, nullable=False)  # JSON: financeiro + score + meta
    status = Column(String(20), default="closed")
    closed_at = Column(DateTime, default=utcnow_naive)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class DailySnapshot(Base):
    """Snapshot diario automatico (Fase 5 — retencao).

    Um registro por (company_id, snapshot_date). Idempotente: reexecutar o job
    no mesmo dia nao duplica — atualiza o snapshot existente.
    """

    __tablename__ = "daily_snapshots"
    __table_args__ = (UniqueConstraint("company_id", "snapshot_date", name="uq_daily_snapshot"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    snapshot = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


# =====================================================================
# 10. Chat com IA
# =====================================================================


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    title = Column(String(255))
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system, tool
    content = Column(Text)
    tool_calls = Column(Text)
    created_at = Column(DateTime, default=utcnow_naive)

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")


# =====================================================================
# 11. Reports & BI
# =====================================================================


class ReportDefinition(Base):
    __tablename__ = "report_definitions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    report_type = Column(String(50), nullable=False)
    data_source = Column(String(100), nullable=False)
    query_config = Column(Text)
    filter_config = Column(Text)
    column_config = Column(Text)
    chart_config = Column(Text)
    sort_config = Column(Text)
    group_by_config = Column(Text)
    is_template = Column(Boolean, default=False)
    template_category = Column(String(100))
    is_scheduled = Column(Boolean, default=False)
    schedule_cron = Column(String(100))
    schedule_recipients = Column(Text)
    schedule_format = Column(String(20), default="pdf")
    created_by = Column(Integer, nullable=False)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    last_executed_at = Column(DateTime)
    execution_count = Column(Integer, default=0)

    executions: Mapped[list[ReportExecution]] = relationship(
        "ReportExecution", back_populates="report", cascade="all, delete-orphan"
    )


class DashboardDefinition(Base):
    __tablename__ = "dashboard_definitions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    layout_config = Column(Text)
    widget_configs = Column(Text)
    refresh_interval_seconds = Column(Integer, default=300)
    is_default = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    created_by = Column(Integer, nullable=False)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class ReportExecution(Base):
    __tablename__ = "report_executions"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("report_definitions.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    executed_by = Column(Integer, nullable=False)
    status = Column(String(50), default="running")
    parameters = Column(Text)
    row_count = Column(Integer)
    file_path = Column(String(500))
    file_format = Column(String(20))
    file_size_bytes = Column(Integer)
    execution_time_ms = Column(Integer)
    error_message = Column(Text)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)

    report: Mapped[ReportDefinition] = relationship("ReportDefinition", back_populates="executions")


class ReportFavorite(Base):
    __tablename__ = "report_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("report_definitions.id"))
    dashboard_id = Column(Integer, ForeignKey("dashboard_definitions.id"))
    created_at = Column(DateTime, default=utcnow_naive)


# =====================================================================
# 12. Machine Learning / IA
# =====================================================================


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    model_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    algorithm = Column(String(100), nullable=False)
    hyperparameters = Column(Text)
    metrics = Column(Text)
    model_path = Column(String(500))
    feature_columns = Column(Text)
    target_column = Column(String(255))
    training_data_size = Column(Integer, default=0)
    last_trained_at = Column(DateTime)
    status = Column(String(50), default="draft")
    accuracy = Column(Float)
    is_auto_ml = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    predictions: Mapped[list[MLPrediction]] = relationship(
        "MLPrediction", back_populates="model", cascade="all, delete-orphan"
    )


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    entity_id = Column(Integer)
    entity_type = Column(String(50), nullable=False)
    prediction_date = Column(DateTime, nullable=False)
    predicted_value = Column(Float, nullable=False)
    confidence_lower = Column(Float)
    confidence_upper = Column(Float)
    confidence_score = Column(Float)
    actual_value = Column(Float)
    error_rate = Column(Float)
    features_used = Column(Text)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=utcnow_naive)

    model: Mapped[MLModel] = relationship("MLModel", back_populates="predictions")


class MLAnomaly(Base):
    __tablename__ = "ml_anomalies"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"))
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    anomaly_type = Column(String(100), nullable=False)
    severity = Column(String(20), default="medium")
    detected_at = Column(DateTime, nullable=False)
    metric_name = Column(String(255), nullable=False)
    metric_value = Column(Float, nullable=False)
    expected_range_min = Column(Float)
    expected_range_max = Column(Float)
    description = Column(Text)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer)
    acknowledged_at = Column(DateTime)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=utcnow_naive)


class MLRecommendation(Base):
    __tablename__ = "ml_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"))
    recommendation_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    current_value = Column(Float)
    recommended_value = Column(Float)
    expected_impact = Column(Float)
    confidence_score = Column(Float)
    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime)
    applied_by = Column(Integer)
    result_value = Column(Float)
    created_at = Column(DateTime, default=utcnow_naive)


class ChatbotConversation(Base):
    __tablename__ = "chatbot_conversations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)
    response = Column(Text)
    intent = Column(String(100))
    confidence = Column(Float)
    context = Column(Text)
    is_user_message = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)


# =====================================================================
# 13. LGPD / GDPR
# =====================================================================


class DataSubjectRequest(Base):
    """Pedido do titular de dados (acesso, retificacao, exclusao, etc.)."""

    __tablename__ = "data_subject_requests"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    request_type = Column(String(50), nullable=False)
    status = Column(String(50), default="pending")  # pending, in_progress, completed, rejected
    data_subject_email = Column(String(255), nullable=False, index=True)
    data_subject_name = Column(String(255))
    data_subject_type = Column(String(50), default="customer")
    request_details = Column(Text)
    requested_at = Column(DateTime, default=utcnow_naive)
    deadline_at = Column(DateTime)
    completed_at = Column(DateTime)
    completed_by = Column(Integer)
    response_data = Column(Text)
    rejection_reason = Column(Text)
    legal_basis = Column(String(100))
    created_at = Column(DateTime, default=utcnow_naive)


class ConsentRecord(Base):
    """Registro de consentimento LGPD por finalidade."""

    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    data_subject_email = Column(String(255), nullable=False, index=True)
    consent_type = Column(String(100), nullable=False)
    consent_given = Column(Boolean, default=False)
    consent_version = Column(String(50), default="1.0")
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    consent_text = Column(Text)
    withdrawn_at = Column(DateTime)
    withdrawn_by = Column(Integer)
    created_at = Column(DateTime, default=utcnow_naive)


class SecuritySettings(Base):
    """Configuracoes de seguranca por empresa."""

    __tablename__ = "security_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, nullable=False)
    password_policy = Column(Text)
    mfa_required = Column(Boolean, default=False)
    mfa_methods = Column(Text)
    session_timeout_minutes = Column(Integer, default=30)
    max_login_attempts = Column(Integer, default=5)
    lockout_duration_minutes = Column(Integer, default=30)
    require_password_change_days = Column(Integer, default=90)
    allowed_ip_ranges = Column(Text)
    data_retention_days = Column(Integer, default=2555)
    audit_retention_days = Column(Integer, default=2555)
    encryption_at_rest = Column(Boolean, default=True)
    encryption_in_transit = Column(Boolean, default=True)
    gdpr_enabled = Column(Boolean, default=True)
    lgpd_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


# =====================================================================
# 14. Event Log (Event Sourcing leve)
# =====================================================================


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer)
    event_type = Column(String(100), nullable=False, index=True)
    old_state = Column(Text)
    new_state = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow_naive, index=True)


class LoginAttempt(Base):
    """Tentativas de login (para deteccao de brute force)."""

    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    success = Column(Boolean, default=False)
    failure_reason = Column(String(255))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=utcnow_naive, index=True)


# =====================================================================
# 15. Markings (Ontology Sem8) - grants explicitos de markings a usuarios
# =====================================================================


class UserMarking(Base):
    """
    Grant de marking sensivel a um usuario.

    Markings com `requires_marking_grant: true` (ex: ConfidencialComercial)
    exigem que o user tenha row aqui ativa para ver/operar dados marcados.

    Concede granularidade adicional ao role: o user pode ser 'analista',
    mas so' ve ConfidencialComercial se o data steward gravar essa linha.
    """

    __tablename__ = "user_markings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    marking = Column(String(100), nullable=False, index=True)
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime, default=utcnow_naive, nullable=False)
    valid_until = Column(DateTime, nullable=True, index=True)
    reason = Column(String(500))
    revoked = Column(Boolean, default=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id"), nullable=True)


# =====================================================================
# 16. Snapshots (Foundry.3) — time-travel de Object Types
# =====================================================================


class DatasetSnapshot(Base):
    """
    Snapshot pontual do estado de um ou mais Object Types.
    Permite consultas time-travel: 'como era Produto 10 em 2026-03-15?'
    """

    __tablename__ = "dataset_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(500))
    object_type = Column(String(100), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    row_count = Column(Integer, default=0)
    # Payload completo (JSON com lista de objetos serializados)
    payload = Column(Text, nullable=False)


class SnapshotIndex(Base):
    """Index rapido para fetch by (snapshot_id, object_type, object_id) — opcional, em dev nao usamos."""

    __tablename__ = "snapshot_index"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("dataset_snapshots.id"), nullable=False, index=True)
    object_id = Column(Integer, nullable=False, index=True)
