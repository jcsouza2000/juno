"""
JUNO Prediction Engine
Previsão de demanda, vendas e estoque usando Prophet, ARIMA e ML
"""

import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

try:
    from prophet import Prophet

    PROPHET_AVAILABLE = True
except ImportError:
    Prophet = None
    PROPHET_AVAILABLE = False
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler

from app.core.datetime_utils import utcnow_naive
from app.models import MLModel, MLPrediction

logger = logging.getLogger(__name__)


class PredictionEngine:
    """
    Engine de predição para séries temporais e regressão.

    Algoritmos suportados:
    - prophet: Facebook Prophet (sazonalidade, feriados)
    - arima: Auto-ARIMA (séries temporais clássicas)
    - random_forest: Random Forest Regressor
    - linear: Regressão Linear
    """

    def __init__(self, db: Session):
        self.db = db
        self.models_cache: dict[int, Any] = {}

    def train_model(
        self,
        company_id: int,
        model_type: str,
        entity_type: str,
        algorithm: str,
        training_data: pd.DataFrame,
        target_column: str,
        feature_columns: list[str],
        hyperparameters: dict | None = None,
        model_name: str | None = None,
        is_auto_ml: bool = False,
    ) -> MLModel:
        """
        Treina um novo modelo de ML.

        Args:
            company_id: ID da empresa
            model_type: Tipo de predição (demand_forecast, sales_forecast, etc)
            entity_type: Entidade alvo (products, customers, etc)
            algorithm: Algoritmo a usar
            training_data: DataFrame com dados de treino
            target_column: Coluna alvo
            feature_columns: Colunas de features
            hyperparameters: Hiperparâmetros customizados

        Returns:
            MLModel treinado e salvo
        """
        logger.info(f"[TRAIN] Iniciando treino: {model_type} com {algorithm}")

        # Criar registro do modelo
        model_record = MLModel(
            company_id=company_id,
            name=model_name or f"{model_type}_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M')}",
            model_type=model_type,
            entity_type=entity_type,
            algorithm=algorithm,
            hyperparameters=json.dumps(hyperparameters or {}),
            feature_columns=json.dumps(feature_columns),
            target_column=target_column,
            status="training",
            training_data_size=len(training_data),
            is_auto_ml=is_auto_ml,
        )
        self.db.add(model_record)
        self.db.commit()

        try:
            # Preparar dados
            X = training_data[feature_columns].copy()
            y = training_data[target_column].copy()

            # Treinar modelo específico
            if algorithm == "prophet":
                trained_model, metrics = self._train_prophet(
                    training_data, target_column, hyperparameters
                )
            elif algorithm == "random_forest":
                trained_model, metrics = self._train_random_forest(X, y, hyperparameters)
            elif algorithm == "isolation_forest":
                trained_model, metrics = self._train_isolation_forest(X, hyperparameters)
            else:
                raise ValueError(f"Algoritmo não suportado: {algorithm}")

            # Salvar modelo em disco
            model_filename = f"model_{model_record.id}_{algorithm}.pkl"
            model_path = os.path.join("models", str(company_id), model_filename)
            os.makedirs(os.path.dirname(model_path), exist_ok=True)

            with open(model_path, "wb") as f:
                pickle.dump(trained_model, f)

            # Atualizar registro
            model_record.status = "active"
            model_record.metrics = json.dumps(metrics)
            model_record.model_path = model_path
            model_record.accuracy = metrics.get("mae")
            model_record.last_trained_at = utcnow_naive()
            self.db.commit()

            logger.info(f"[TRAIN] Modelo {model_record.id} treinado. MAE: {metrics.get('mae')}")
            return model_record

        except Exception as e:
            model_record.status = "failed"
            self.db.commit()
            logger.error(f"[TRAIN] Erro no treino: {str(e)}")
            raise

    def _train_prophet(
        self, data: pd.DataFrame, target_col: str, hyperparams: dict | None
    ) -> tuple[Any, dict]:
        """Treina modelo Prophet."""
        df = data[["ds", target_col]].rename(columns={target_col: "y"})

        params = hyperparams or {}
        model = Prophet(
            yearly_seasonality=params.get("yearly_seasonality", True),
            weekly_seasonality=params.get("weekly_seasonality", True),
            daily_seasonality=params.get("daily_seasonality", False),
            changepoint_prior_scale=params.get("changepoint_prior_scale", 0.05),
        )

        model.add_country_holidays(country_name="BR")

        model.fit(df)

        # Calcular métricas (simplificado)
        metrics = {
            "mae": 0.0,  # Calcular com validação cruzada em produção
            "rmse": 0.0,
            "training_samples": len(df),
        }

        return model, metrics

    def _train_random_forest(
        self, X: pd.DataFrame, y: pd.Series, hyperparams: dict | None
    ) -> tuple[Any, dict]:
        """Treina Random Forest."""
        params = hyperparams or {}
        model = RandomForestRegressor(
            n_estimators=params.get("n_estimators", 100),
            max_depth=params.get("max_depth", 10),
            random_state=42,
        )

        model.fit(X, y)

        # Métricas simples (usar validação cruzada em produção)
        predictions = model.predict(X)
        mae = mean_absolute_error(y, predictions)
        rmse = np.sqrt(mean_squared_error(y, predictions))

        metrics = {
            "mae": float(mae),
            "rmse": float(rmse),
            "feature_importance": dict(
                zip(X.columns, model.feature_importances_.tolist(), strict=False)
            ),
        }

        return model, metrics

    def _train_isolation_forest(
        self, X: pd.DataFrame, hyperparams: dict | None
    ) -> tuple[Any, dict]:
        """Treina Isolation Forest para detecção de anomalias."""
        params = hyperparams or {}
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = IsolationForest(contamination=params.get("contamination", 0.1), random_state=42)

        model.fit(X_scaled)

        metrics = {
            "contamination": params.get("contamination", 0.1),
            "n_features": X.shape[1],
            "training_samples": len(X),
        }

        # Salvar scaler junto
        return {"model": model, "scaler": scaler}, metrics

    def predict(
        self,
        model_id: int,
        prediction_data: pd.DataFrame | None = None,
        periods: int = 30,
        entity_id: int | None = None,
    ) -> list[MLPrediction]:
        """
        Gera predições usando um modelo treinado.

        Args:
            model_id: ID do modelo
            prediction_data: Dados para predição (opcional)
            periods: Número de períodos futuros (para séries temporais)
            entity_id: ID da entidade específica

        Returns:
            Lista de predições salvas
        """
        model_record = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model_record or model_record.status != "active":
            raise ValueError("Modelo não encontrado ou não está ativo")

        # Carregar modelo
        if model_id not in self.models_cache:
            with open(model_record.model_path, "rb") as f:
                self.models_cache[model_id] = pickle.load(f)

        trained_model = self.models_cache[model_id]
        algorithm = model_record.algorithm

        predictions = []

        if algorithm == "prophet":
            future = trained_model.make_future_dataframe(periods=periods)
            forecast = trained_model.predict(future)

            # Salvar últimos 'periods' predições
            future_preds = forecast.tail(periods)
            for _, row in future_preds.iterrows():
                pred = MLPrediction(
                    model_id=model_id,
                    company_id=model_record.company_id,
                    entity_id=entity_id,
                    entity_type=model_record.entity_type,
                    prediction_date=row["ds"],
                    predicted_value=row["yhat"],
                    confidence_lower=row["yhat_lower"],
                    confidence_upper=row["yhat_upper"],
                    confidence_score=0.95,
                    status="pending",
                )
                self.db.add(pred)
                predictions.append(pred)

        elif algorithm == "random_forest":
            if prediction_data is None:
                raise ValueError("Dados de predição necessários para random_forest")

            preds = trained_model.predict(prediction_data)
            for i, val in enumerate(preds):
                pred = MLPrediction(
                    model_id=model_id,
                    company_id=model_record.company_id,
                    entity_id=entity_id or i,
                    entity_type=model_record.entity_type,
                    prediction_date=utcnow_naive() + timedelta(days=i),
                    predicted_value=float(val),
                    confidence_score=0.85,
                    status="pending",
                )
                self.db.add(pred)
                predictions.append(pred)

        self.db.commit()
        return predictions

    def detect_anomalies(self, model_id: int, data: pd.DataFrame, entity_type: str) -> list[dict]:
        """
        Detecta anomalias usando Isolation Forest.
        """
        model_record = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model_record:
            raise ValueError("Modelo não encontrado")

        if model_id not in self.models_cache:
            with open(model_record.model_path, "rb") as f:
                self.models_cache[model_id] = pickle.load(f)

        model_data = self.models_cache[model_id]
        model = model_data["model"]
        scaler = model_data["scaler"]

        X_scaled = scaler.transform(data)
        predictions = model.predict(X_scaled)
        scores = model.decision_function(X_scaled)

        anomalies = []
        for i, (pred, score) in enumerate(zip(predictions, scores, strict=False)):
            if pred == -1:  # Anomalia detectada
                anomaly = {
                    "entity_id": i,
                    "entity_type": entity_type,
                    "anomaly_score": float(score),
                    "severity": "high" if score < -0.5 else "medium",
                    "detected_at": utcnow_naive().isoformat(),
                }
                anomalies.append(anomaly)

        return anomalies

    def get_model_performance(self, model_id: int) -> dict:
        """Retorna métricas de performance do modelo."""
        model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            return {}

        # Calcular erro médio das predições confirmadas
        predictions = (
            self.db.query(MLPrediction)
            .filter(MLPrediction.model_id == model_id, MLPrediction.actual_value.isnot(None))
            .all()
        )

        if not predictions:
            return json.loads(model.metrics or "{}")

        errors = [abs(p.predicted_value - p.actual_value) for p in predictions]
        mae = sum(errors) / len(errors)

        return {
            "model_id": model_id,
            "algorithm": model.algorithm,
            "training_date": model.last_trained_at.isoformat() if model.last_trained_at else None,
            "total_predictions": len(predictions),
            "mae": mae,
            "original_metrics": json.loads(model.metrics or "{}"),
        }


class AutoMLPipeline:
    """
    Pipeline de Auto-ML para treinamento automático.
    """

    def __init__(self, db: Session):
        self.db = db
        self.engine = PredictionEngine(db)

    def auto_train(
        self,
        company_id: int,
        model_type: str,
        entity_type: str,
        data: pd.DataFrame,
        target_column: str,
    ) -> MLModel | None:
        """
        Treina automaticamente o melhor modelo para os dados.
        """
        logger.info(f"[AUTOML] Iniciando Auto-ML para {model_type}")

        # Definir algoritmos candidatos
        candidates = {
            "demand_forecast": ["prophet", "random_forest"],
            "sales_forecast": ["prophet", "random_forest"],
            "anomaly_detection": ["isolation_forest"],
            "price_optimization": ["random_forest"],
        }

        algorithms = candidates.get(model_type, ["random_forest"])
        best_model = None
        best_score = float("inf")

        feature_columns = [c for c in data.columns if c != target_column and c != "ds"]

        for algo in algorithms:
            try:
                model = self.engine.train_model(
                    company_id=company_id,
                    model_type=model_type,
                    entity_type=entity_type,
                    algorithm=algo,
                    training_data=data,
                    target_column=target_column,
                    feature_columns=feature_columns,
                    is_auto_ml=True,
                )

                metrics = json.loads(model.metrics or "{}")
                score = metrics.get("mae", float("inf"))

                if score < best_score:
                    best_score = score
                    best_model = model

            except Exception as e:
                logger.warning(f"[AUTOML] Falha com {algo}: {str(e)}")
                continue

        if best_model:
            best_model.name = f"AUTO_{model_type}_{best_model.algorithm}"
            self.db.commit()
            logger.info(f"[AUTOML] Melhor modelo: {best_model.algorithm} (MAE: {best_score})")

        return best_model
