"""
Testes unitários para módulo ML/IA
"""

from unittest.mock import Mock

import pandas as pd

from app.ml.chatbot_engine import ChatbotEngine
from app.ml.prediction_engine import PredictionEngine


class TestPredictionEngine:
    def test_train_prophet(self):
        mock_db = Mock()
        engine = PredictionEngine(mock_db)

        data = pd.DataFrame(
            {
                "ds": pd.date_range("2025-01-01", periods=30, freq="D"),
                "y": range(30),
                "feature1": range(30),
            }
        )

        model, metrics = engine._train_prophet(data, "y", None)
        assert model is not None
        assert "mae" in metrics

    def test_train_random_forest(self):
        mock_db = Mock()
        engine = PredictionEngine(mock_db)

        X = pd.DataFrame({"f1": range(100), "f2": range(100)})
        y = pd.Series(range(100))

        model, metrics = engine._train_random_forest(X, y, None)
        assert model is not None
        assert "mae" in metrics
        assert "feature_importance" in metrics

    def test_classify_intent_keyword(self):
        mock_db = Mock()
        engine = ChatbotEngine(mock_db)

        intent, confidence = engine._classify_intent("qual a previsão de vendas?")
        assert intent == "sales_forecast"
        assert confidence > 0

    def test_extract_entities_dates(self):
        mock_db = Mock()
        engine = ChatbotEngine(mock_db)

        entities = engine._extract_entities("previsão para 15/05/2026")
        assert len(entities["dates"]) > 0

    def test_extract_entities_numbers(self):
        mock_db = Mock()
        engine = ChatbotEngine(mock_db)

        entities = engine._extract_entities("produto com 100 unidades")
        assert len(entities["numbers"]) > 0
