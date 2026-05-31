"""
JUNO ML/IA API Routes
Endpoints para modelos, predições, anomalias, chatbot e recomendações
"""

import json
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_user, get_primary_company_id
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.ml.chatbot_engine import ChatbotEngine
from app.ml.prediction_engine import AutoMLPipeline, PredictionEngine
from app.models import Company, MLAnomaly, MLModel, MLPrediction, MLRecommendation

router = APIRouter(prefix="/api/v1/ai", tags=["AI / Machine Learning"])


def _company_id(user) -> int:
    return get_primary_company_id(user)


# ============================================================
# SCHEMAS
# ============================================================
# Nota: usamos `protected_namespaces=()` nos schemas que tem campos `model_*`
# (model_type, model_id) porque Pydantic v2 reserva o prefixo `model_` para
# uso interno (model_config, model_dump, etc.) e emite warning sem isso.


class ModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str
    model_type: str  # demand_forecast, sales_forecast, anomaly_detection, recommendation
    entity_type: str  # products, customers, sales, inventory
    algorithm: str  # prophet, random_forest, isolation_forest
    target_column: str
    feature_columns: list[str]
    hyperparameters: dict[str, Any] | None = None


class PredictionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int
    periods: int = 30
    entity_id: int | None = None


class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None


class AnomalyAcknowledge(BaseModel):
    resolution_notes: str | None = None


class RecommendationApply(BaseModel):
    applied_by: int


# ============================================================
# ROTAS — MODELOS
# ============================================================


@router.get("/models")
def list_models(
    company_id: int,
    model_type: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista modelos de ML."""
    if not check_company_access(user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    query = db.query(MLModel).filter(MLModel.company_id == company_id)
    if model_type:
        query = query.filter(MLModel.model_type == model_type)

    models = query.order_by(MLModel.created_at.desc()).all()

    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "model_type": m.model_type,
                "entity_type": m.entity_type,
                "algorithm": m.algorithm,
                "status": m.status,
                "accuracy": m.accuracy,
                "last_trained_at": m.last_trained_at.isoformat() if m.last_trained_at else None,
                "training_data_size": m.training_data_size,
                "metrics": json.loads(m.metrics) if m.metrics else None,
            }
            for m in models
        ]
    }


@router.post("/models")
def create_model(
    data: ModelCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Cria e treina novo modelo (async)."""
    company = db.query(Company).filter(Company.id == _company_id(user)).first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    # Em produção, buscar dados reais do banco
    # Aqui simulamos com dados de exemplo
    def train_task():
        engine = PredictionEngine(db)
        # Dados de exemplo - substituir por consulta real
        sample_data = pd.DataFrame(
            {
                "ds": pd.date_range(start="2025-01-01", periods=365, freq="D"),
                "y": [100 + i * 0.5 + (i % 7) * 10 for i in range(365)],
                "feature1": range(365),
                "feature2": [i % 30 for i in range(365)],
            }
        )

        try:
            model = engine.train_model(
                company_id=company.id,
                model_type=data.model_type,
                entity_type=data.entity_type,
                algorithm=data.algorithm,
                training_data=sample_data,
                target_column=data.target_column,
                feature_columns=data.feature_columns,
                hyperparameters=data.hyperparameters,
                model_name=data.name,
            )
            return {"success": True, "model_id": model.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    background_tasks.add_task(train_task)

    return {
        "message": "Treinamento iniciado em background",
        "status": "training",
        "algorithm": data.algorithm,
    }


@router.post("/models/auto-ml")
def auto_ml_train(
    model_type: str,
    entity_type: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Treina modelo com Auto-ML."""

    def auto_train_task():
        pipeline = AutoMLPipeline(db)
        # Dados de exemplo
        sample_data = pd.DataFrame(
            {
                "ds": pd.date_range(start="2025-01-01", periods=365, freq="D"),
                "y": [100 + i * 0.5 for i in range(365)],
                "feature1": range(365),
            }
        )

        model = pipeline.auto_train(
            company_id=_company_id(user),
            model_type=model_type,
            entity_type=entity_type,
            data=sample_data,
            target_column="y",
        )
        return model.id if model else None

    background_tasks.add_task(auto_train_task)

    return {"message": "Auto-ML iniciado", "status": "training"}


@router.get("/models/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Obtém detalhes do modelo."""
    model = (
        db.query(MLModel)
        .filter(MLModel.id == model_id, MLModel.company_id == _company_id(user))
        .first()
    )

    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")

    engine = PredictionEngine(db)
    performance = engine.get_model_performance(model_id)

    return {
        "id": model.id,
        "name": model.name,
        "model_type": model.model_type,
        "algorithm": model.algorithm,
        "status": model.status,
        "metrics": json.loads(model.metrics) if model.metrics else {},
        "performance": performance,
        "feature_columns": json.loads(model.feature_columns) if model.feature_columns else [],
        "target_column": model.target_column,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


@router.delete("/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Remove modelo."""
    model = (
        db.query(MLModel)
        .filter(MLModel.id == model_id, MLModel.company_id == _company_id(user))
        .first()
    )

    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")

    db.delete(model)
    db.commit()
    return {"message": "Modelo removido"}


# ============================================================
# ROTAS — PREDIÇÕES
# ============================================================


@router.post("/predict")
def create_prediction(
    request: PredictionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Gera predições."""

    def predict_task():
        engine = PredictionEngine(db)
        predictions = engine.predict(
            model_id=request.model_id, periods=request.periods, entity_id=request.entity_id
        )
        return len(predictions)

    background_tasks.add_task(predict_task)

    return {
        "message": f"Predição iniciada para {request.periods} períodos",
        "model_id": request.model_id,
    }


@router.get("/predictions")
def list_predictions(
    model_id: int | None = None,
    entity_type: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista predições."""
    query = db.query(MLPrediction).filter(MLPrediction.company_id == _company_id(user))
    if model_id:
        query = query.filter(MLPrediction.model_id == model_id)
    if entity_type:
        query = query.filter(MLPrediction.entity_type == entity_type)

    predictions = query.order_by(MLPrediction.prediction_date.desc()).limit(limit).all()

    return {
        "predictions": [
            {
                "id": p.id,
                "model_id": p.model_id,
                "entity_type": p.entity_type,
                "entity_id": p.entity_id,
                "prediction_date": p.prediction_date.isoformat() if p.prediction_date else None,
                "predicted_value": p.predicted_value,
                "confidence_lower": p.confidence_lower,
                "confidence_upper": p.confidence_upper,
                "confidence_score": p.confidence_score,
                "actual_value": p.actual_value,
                "status": p.status,
            }
            for p in predictions
        ]
    }


# ============================================================
# ROTAS — ANOMALIAS
# ============================================================


@router.get("/anomalies")
def list_anomalies(
    severity: str | None = None,
    acknowledged: bool | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista anomalias detectadas."""
    query = db.query(MLAnomaly).filter(MLAnomaly.company_id == _company_id(user))

    if severity:
        query = query.filter(MLAnomaly.severity == severity)
    if acknowledged is not None:
        query = query.filter(MLAnomaly.is_acknowledged == acknowledged)

    anomalies = query.order_by(MLAnomaly.detected_at.desc()).limit(limit).all()

    return {
        "anomalies": [
            {
                "id": a.id,
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "metric_name": a.metric_name,
                "metric_value": a.metric_value,
                "expected_range": (
                    [a.expected_range_min, a.expected_range_max] if a.expected_range_min else None
                ),
                "description": a.description,
                "is_acknowledged": a.is_acknowledged,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
            }
            for a in anomalies
        ],
        "summary": {
            "total": len(anomalies),
            "critical": sum(1 for a in anomalies if a.severity == "critical"),
            "high": sum(1 for a in anomalies if a.severity == "high"),
            "pending": sum(1 for a in anomalies if not a.is_acknowledged),
        },
    }


@router.post("/anomalies/{anomaly_id}/acknowledge")
def acknowledge_anomaly(
    anomaly_id: int,
    data: AnomalyAcknowledge,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Reconhece anomalia."""
    anomaly = (
        db.query(MLAnomaly)
        .filter(MLAnomaly.id == anomaly_id, MLAnomaly.company_id == _company_id(user))
        .first()
    )

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomalia não encontrada")

    anomaly.is_acknowledged = True
    anomaly.acknowledged_by = user.id
    anomaly.acknowledged_at = utcnow_naive()
    anomaly.resolution_notes = data.resolution_notes

    db.commit()
    return {"message": "Anomalia reconhecida"}


# ============================================================
# ROTAS — CHATBOT
# ============================================================


@router.post("/chat")
def chat_message(data: ChatMessage, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Envia mensagem para o chatbot."""
    session_id = data.session_id or f"session_{user.id}_{utcnow_naive().timestamp()}"

    engine = ChatbotEngine(db)
    response = engine.process_message(
        company_id=_company_id(user), user_id=user.id, session_id=session_id, message=data.message
    )

    return response


@router.get("/chat/history/{session_id}")
def chat_history(
    session_id: str, limit: int = 50, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Histórico de conversa."""
    engine = ChatbotEngine(db)
    history = engine.get_conversation_history(session_id, limit)
    return {"history": history, "session_id": session_id}


# ============================================================
# ROTAS — RECOMENDAÇÕES
# ============================================================


@router.get("/recommendations")
def list_recommendations(
    recommendation_type: str | None = None,
    applied: bool | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista recomendações."""
    query = db.query(MLRecommendation).filter(MLRecommendation.company_id == _company_id(user))

    if recommendation_type:
        query = query.filter(MLRecommendation.recommendation_type == recommendation_type)
    if applied is not None:
        query = query.filter(MLRecommendation.is_applied == applied)

    recommendations = query.order_by(MLRecommendation.confidence_score.desc()).limit(limit).all()

    return {
        "recommendations": [
            {
                "id": r.id,
                "type": r.recommendation_type,
                "title": r.title,
                "description": r.description,
                "current_value": r.current_value,
                "recommended_value": r.recommended_value,
                "expected_impact": r.expected_impact,
                "confidence_score": r.confidence_score,
                "is_applied": r.is_applied,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recommendations
        ]
    }


@router.post("/recommendations/{rec_id}/apply")
def apply_recommendation(
    rec_id: int,
    data: RecommendationApply,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Aplica recomendação."""
    rec = (
        db.query(MLRecommendation)
        .filter(MLRecommendation.id == rec_id, MLRecommendation.company_id == _company_id(user))
        .first()
    )

    if not rec:
        raise HTTPException(status_code=404, detail="Recomendação não encontrada")

    rec.is_applied = True
    rec.applied_at = utcnow_naive()
    rec.applied_by = data.applied_by

    db.commit()
    return {"message": "Recomendação aplicada"}


# ============================================================
# ROTAS — DASHBOARD
# ============================================================


@router.get("/dashboard")
def ai_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Dashboard consolidado de IA."""
    company_id = _company_id(user)

    # Estatísticas
    models_count = (
        db.query(MLModel)
        .filter(MLModel.company_id == company_id, MLModel.status == "active")
        .count()
    )

    predictions_count = db.query(MLPrediction).filter(MLPrediction.company_id == company_id).count()

    anomalies_pending = (
        db.query(MLAnomaly)
        .filter(MLAnomaly.company_id == company_id, MLAnomaly.is_acknowledged == False)
        .count()
    )

    recommendations_pending = (
        db.query(MLRecommendation)
        .filter(MLRecommendation.company_id == company_id, MLRecommendation.is_applied == False)
        .count()
    )

    # Últimas predições
    latest_predictions = (
        db.query(MLPrediction)
        .filter(MLPrediction.company_id == company_id)
        .order_by(MLPrediction.created_at.desc())
        .limit(7)
        .all()
    )

    return {
        "stats": {
            "active_models": models_count,
            "total_predictions": predictions_count,
            "pending_anomalies": anomalies_pending,
            "pending_recommendations": recommendations_pending,
        },
        "latest_predictions": [
            {
                "date": p.prediction_date.strftime("%d/%m") if p.prediction_date else None,
                "value": p.predicted_value,
                "entity_type": p.entity_type,
            }
            for p in latest_predictions
        ],
    }
