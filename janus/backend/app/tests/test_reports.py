"""
Testes unitários para módulo de Relatórios/BI
"""

from unittest.mock import Mock

import pandas as pd

from app.reports.export_engine import ExportEngine
from app.reports.report_engine import ReportEngine
from app.reports.templates import get_template, list_templates


class TestReportEngine:
    def test_get_available_entities(self):
        mock_db = Mock()
        engine = ReportEngine(mock_db)
        entities = engine.get_available_entities()
        assert "sales_by_period" in entities
        assert "inventory_status" in entities

    def test_extract_column_metadata(self):
        mock_db = Mock()
        engine = ReportEngine(mock_db)

        df = pd.DataFrame(
            {
                "name": ["A", "B"],
                "price": [10.5, 20.0],
                "quantity": [100, 200],
                "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            }
        )

        meta = engine._extract_column_metadata(df, None)
        assert len(meta) == 4
        assert meta[0]["type"] == "string"
        assert meta[1]["type"] == "float"
        assert meta[2]["type"] == "int"
        assert meta[3]["type"] == "date"

    def test_calculate_summary(self):
        mock_db = Mock()
        engine = ReportEngine(mock_db)

        df = pd.DataFrame({"revenue": [100, 200, 300], "cost": [50, 100, 150]})

        summary = engine._calculate_summary(df, None)
        assert "revenue" in summary
        assert summary["revenue"]["sum"] == 600
        assert summary["revenue"]["avg"] == 200


class TestExportEngine:
    def test_export_csv(self):
        engine = ExportEngine()
        data = [{"name": "Produto A", "price": 100.50}, {"name": "Produto B", "price": 200.00}]
        columns = [{"field": "name", "label": "Nome"}, {"field": "price", "label": "Preço"}]

        result = engine.export(data, columns, "csv", "Teste")
        assert result["format"] == "csv"
        assert result["mime_type"] == "text/csv"
        assert result["file_size"] > 0

    def test_export_json(self):
        engine = ExportEngine()
        data = [{"name": "Produto A", "price": 100.50}]
        columns = [{"field": "name", "label": "Nome"}]

        result = engine.export(data, columns, "json", "Teste")
        assert result["format"] == "json"
        assert result["mime_type"] == "application/json"


class TestTemplates:
    def test_get_template(self):
        template = get_template("sales_summary")
        assert template is not None
        assert template["name"] == "Resumo de Vendas"

    def test_list_templates(self):
        templates = list_templates("sales")
        assert len(templates) > 0
        for t in templates.values():
            assert t["template_category"] == "sales"
