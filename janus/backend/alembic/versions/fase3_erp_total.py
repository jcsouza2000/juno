"""fase3_erp_total_and_score_v2

Revision ID: fase3_erp_total
Revises: fase2_chat_audit
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'fase3_erp_total'
down_revision = 'fase2_chat_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # INVENTORY (Estoque)
    # ============================================================
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('warehouse_location', sa.String(length=100), nullable=True),
        sa.Column('quantity_on_hand', sa.Integer(), default=0),
        sa.Column('quantity_reserved', sa.Integer(), default=0),
        sa.Column('quantity_available', sa.Integer(), default=0),
        sa.Column('unit_cost', sa.Float(), default=0),
        sa.Column('last_movement_date', sa.DateTime(), nullable=True),
        sa.Column('min_stock_level', sa.Integer(), default=0),
        sa.Column('max_stock_level', sa.Integer(), default=0),
        sa.Column('status', sa.String(length=50), default='active'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inventory_id', 'inventory', ['id'])
    op.create_index('ix_inventory_company_id', 'inventory', ['company_id'])
    op.create_index('ix_inventory_product_id', 'inventory', ['product_id'])
    
    # ============================================================
    # SUPPLIERS (Fornecedores)
    # ============================================================
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('cnpj', sa.String(length=20), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('payment_terms', sa.String(length=100), nullable=True),
        sa.Column('lead_time_days', sa.Integer(), default=0),
        sa.Column('rating', sa.Float(), default=0),
        sa.Column('status', sa.String(length=50), default='active'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_suppliers_id', 'suppliers', ['id'])
    op.create_index('ix_suppliers_company_id', 'suppliers', ['company_id'])
    
    # ============================================================
    # SUPPLIER PRODUCTS (Produtos por Fornecedor)
    # ============================================================
    op.create_table(
        'supplier_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('supplier_sku', sa.String(length=100), nullable=True),
        sa.Column('unit_cost', sa.Float(), default=0),
        sa.Column('min_order_qty', sa.Integer(), default=1),
        sa.Column('last_purchase_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ============================================================
    # PURCHASE ORDERS (Ordens de Compra)
    # ============================================================
    op.create_table(
        'purchase_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), default='draft'),
        sa.Column('total_amount', sa.Float(), default=0),
        sa.Column('order_date', sa.DateTime(), nullable=True),
        sa.Column('expected_date', sa.DateTime(), nullable=True),
        sa.Column('received_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ============================================================
    # PURCHASE ORDER ITEMS
    # ============================================================
    op.create_table(
        'purchase_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), default=0),
        sa.Column('unit_cost', sa.Float(), default=0),
        sa.Column('total_cost', sa.Float(), default=0),
        sa.Column('received_qty', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ============================================================
    # ERP FINANCIALS (Dados Financeiros do ERP)
    # ============================================================
    op.create_table(
        'erp_financials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('document_number', sa.String(length=100), nullable=True),
        sa.Column('account_code', sa.String(length=50), nullable=True),
        sa.Column('account_name', sa.String(length=255), nullable=True),
        sa.Column('debit', sa.Float(), default=0),
        sa.Column('credit', sa.Float(), default=0),
        sa.Column('balance', sa.Float(), default=0),
        sa.Column('period', sa.String(length=50), nullable=True),
        sa.Column('posting_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_erp_financials_id', 'erp_financials', ['id'])
    op.create_index('ix_erp_financials_company_id', 'erp_financials', ['company_id'])
    
    # ============================================================
    # SCORE HISTORY (Histórico do Score JUNO)
    # ============================================================
    op.create_table(
        'score_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('score_date', sa.DateTime(), nullable=False),
        sa.Column('overall_score', sa.Float(), default=0),
        sa.Column('margin_score', sa.Float(), default=0),
        sa.Column('liquidity_score', sa.Float(), default=0),
        sa.Column('debt_score', sa.Float(), default=0),
        sa.Column('production_score', sa.Float(), default=0),
        sa.Column('data_quality_score', sa.Float(), default=0),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_score_history_id', 'score_history', ['id'])
    op.create_index('ix_score_history_company_id', 'score_history', ['company_id'])


def downgrade() -> None:
    op.drop_table('score_history')
    op.drop_table('erp_financials')
    op.drop_table('purchase_order_items')
    op.drop_table('purchase_orders')
    op.drop_table('supplier_products')
    op.drop_table('suppliers')
    op.drop_table('inventory')
