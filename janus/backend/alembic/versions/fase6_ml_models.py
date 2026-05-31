"""fase6_ml_models

Revision ID: fase6_ml_models
Revises: fase5_erp_connectors
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'fase6_ml_models'
down_revision = 'fase5_erp_connectors'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # ML MODELS (Modelos treinados)
    # ============================================================
    op.create_table(
        'ml_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('model_type', sa.String(length=50), nullable=False),  # demand_forecast, anomaly_detection, recommendation, nlp
        sa.Column('entity_type', sa.String(length=50), nullable=False),  # products, customers, sales, inventory
        sa.Column('algorithm', sa.String(length=100), nullable=False),  # prophet, arima, isolation_forest, bert, etc
        sa.Column('hyperparameters', sa.Text(), nullable=True),  # JSON
        sa.Column('metrics', sa.Text(), nullable=True),  # JSON: {"mae": 0.5, "rmse": 0.8}
        sa.Column('model_path', sa.String(length=500), nullable=True),  # caminho do arquivo .pkl/.pt
        sa.Column('feature_columns', sa.Text(), nullable=True),  # JSON array
        sa.Column('target_column', sa.String(length=255), nullable=True),
        sa.Column('training_data_size', sa.Integer(), default=0),
        sa.Column('last_trained_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), default='draft'),  # draft, training, active, deprecated
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('is_auto_ml', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_models_id', 'ml_models', ['id'])
    op.create_index('ix_ml_models_company_id', 'ml_models', ['company_id'])
    op.create_index('ix_ml_models_model_type', 'ml_models', ['model_type'])
    
    # ============================================================
    # ML PREDICTIONS (Predições geradas)
    # ============================================================
    op.create_table(
        'ml_predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),  # ID do produto/cliente/etc
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('prediction_date', sa.DateTime(), nullable=False),
        sa.Column('predicted_value', sa.Float(), nullable=False),
        sa.Column('confidence_lower', sa.Float(), nullable=True),
        sa.Column('confidence_upper', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),  # 0.0 a 1.0
        sa.Column('actual_value', sa.Float(), nullable=True),  # preenchido posteriormente
        sa.Column('error_rate', sa.Float(), nullable=True),
        sa.Column('features_used', sa.Text(), nullable=True),  # JSON
        sa.Column('status', sa.String(length=50), default='pending'),  # pending, confirmed, failed
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_predictions_id', 'ml_predictions', ['id'])
    op.create_index('ix_ml_predictions_model_id', 'ml_predictions', ['model_id'])
    op.create_index('ix_ml_predictions_entity', 'ml_predictions', ['entity_type', 'entity_id'])
    
    # ============================================================
    # ML ANOMALIES (Anomalias detectadas)
    # ============================================================
    op.create_table(
        'ml_anomalies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('anomaly_type', sa.String(length=100), nullable=False),  # price_spike, demand_drop, stockout_risk
        sa.Column('severity', sa.String(length=20), default='medium'),  # low, medium, high, critical
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('metric_name', sa.String(length=255), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('expected_range_min', sa.Float(), nullable=True),
        sa.Column('expected_range_max', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_acknowledged', sa.Boolean(), default=False),
        sa.Column('acknowledged_by', sa.Integer(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_anomalies_id', 'ml_anomalies', ['id'])
    op.create_index('ix_ml_anomalies_company_id', 'ml_anomalies', ['company_id'])
    
    # ============================================================
    # CHATBOT CONVERSATIONS (Histórico do chatbot)
    # ============================================================
    op.create_table(
        'chatbot_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('intent', sa.String(length=100), nullable=True),  # sales_forecast, inventory_check, anomaly_list
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),  # JSON
        sa.Column('is_user_message', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chatbot_conversations_session', 'chatbot_conversations', ['session_id'])
    
    # ============================================================
    # RECOMMENDATIONS (Recomendações geradas)
    # ============================================================
    op.create_table(
        'ml_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('recommendation_type', sa.String(length=50), nullable=False),  # pricing, purchase, supplier, cross_sell
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('current_value', sa.Float(), nullable=True),
        sa.Column('recommended_value', sa.Float(), nullable=True),
        sa.Column('expected_impact', sa.Float(), nullable=True),  # % de melhoria esperada
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('is_applied', sa.Boolean(), default=False),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('applied_by', sa.Integer(), nullable=True),
        sa.Column('result_value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_recommendations_id', 'ml_recommendations', ['id'])


def downgrade() -> None:
    op.drop_table('ml_recommendations')
    op.drop_table('chatbot_conversations')
    op.drop_table('ml_anomalies')
    op.drop_table('ml_predictions')
    op.drop_table('ml_models')
