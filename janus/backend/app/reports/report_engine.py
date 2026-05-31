"""
JUNO Report Engine
Engine de geração de relatórios com SQL dinâmico, filtros e agregações
"""

import json
import logging
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.models import (
    DashboardDefinition,
    ReportDefinition,
)

logger = logging.getLogger(__name__)


class ReportEngine:
    """
    Engine de execução de relatórios.

    Suporta:
    - SQL dinâmico com parâmetros
    - Filtros avançados (between, in, like, etc)
    - Agregações (sum, count, avg, min, max)
    - Ordenação e paginação
    - Exportação para múltiplos formatos
    """

    # Mapeamento de entidades para queries base
    ENTITY_QUERIES = {
        "products": """
            SELECT 
                p.id, p.name, p.sku, p.category, 
                p.stock_quantity, p.min_stock, p.sale_price,
                p.standard_cost, p.created_at
            FROM products p
            WHERE p.company_id = :company_id
        """,
        "customers": """
            SELECT 
                c.id, c.name, c.email, c.phone, c.segment,
                c.city, c.state, c.created_at
            FROM customers c
            WHERE c.company_id = :company_id
        """,
        "sales_orders": """
            SELECT 
                so.id, so.order_number, so.order_date,
                c.name as customer_name, so.total, so.status
            FROM sales_orders so
            LEFT JOIN customers c ON c.id = so.customer_id
            WHERE so.company_id = :company_id
        """,
        "sales_by_product": """
            SELECT 
                p.name as product_name,
                p.category,
                SUM(soi.quantity) as total_quantity,
                SUM(soi.subtotal) as total_revenue,
                COUNT(DISTINCT so.id) as order_count
            FROM sales_order_items soi
            JOIN products p ON p.id = soi.product_id
            JOIN sales_orders so ON so.id = soi.sales_order_id
            WHERE so.company_id = :company_id
            GROUP BY p.id, p.name, p.category
        """,
        "sales_by_period": """
            SELECT 
                DATE_TRUNC('month', so.order_date) as period,
                COUNT(*) as order_count,
                SUM(so.total) as total_revenue,
                AVG(so.total) as avg_order_value
            FROM sales_orders so
            WHERE so.company_id = :company_id
            GROUP BY DATE_TRUNC('month', so.order_date)
            ORDER BY period
        """,
        "inventory_status": """
            SELECT 
                p.name, p.sku, p.category,
                p.stock_quantity,
                p.min_stock,
                p.stock_quantity - p.min_stock as available_stock,
                CASE 
                    WHEN p.stock_quantity <= p.min_stock THEN 'CRITICAL'
                    WHEN p.stock_quantity <= p.min_stock * 1.5 THEN 'LOW'
                    ELSE 'OK'
                END as stock_status
            FROM products p
            WHERE p.company_id = :company_id
            ORDER BY available_stock ASC
        """,
        "financial_summary": """
            SELECT 
                DATE_TRUNC('month', so.order_date) as period,
                SUM(so.total) as revenue,
                SUM(so.total * 0.7) as estimated_cost,
                SUM(so.total) - SUM(so.total * 0.7) as estimated_profit
            FROM sales_orders so
            WHERE so.company_id = :company_id
            AND so.status = 'completed'
            GROUP BY DATE_TRUNC('month', so.order_date)
            ORDER BY period
        """,
    }

    def __init__(self, db: Session):
        self.db = db

    def execute_report(
        self,
        report_def: ReportDefinition,
        parameters: dict | None = None,
        page: int = 1,
        page_size: int = 1000,
    ) -> dict[str, Any]:
        """
        Executa um relatório e retorna dados + metadados.
        """
        logger.info(f"[REPORT] Executando relatório {report_def.id}: {report_def.name}")

        start_time = utcnow_naive()
        params = parameters or {}

        try:
            # Construir query
            query_sql = self._build_query(report_def, params)

            # Executar
            result = self.db.execute(
                text(query_sql), {"company_id": report_def.company_id, **params}
            )

            # Converter para DataFrame
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

            # Aplicar filtros pós-query (se houver)
            df = self._apply_post_filters(df, report_def.filter_config, params)

            # Aplicar ordenação
            df = self._apply_sorting(df, report_def.sort_config)

            # Calcular totais
            row_count = len(df)

            # Paginar
            if page_size > 0:
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                df_page = df.iloc[start_idx:end_idx]
            else:
                df_page = df

            execution_time = int((utcnow_naive() - start_time).total_seconds() * 1000)

            # Converter para dict
            data = df_page.to_dict("records")

            # Metadados das colunas
            columns_meta = self._extract_column_metadata(df, report_def.column_config)

            return {
                "success": True,
                "data": data,
                "columns": columns_meta,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_rows": row_count,
                    "total_pages": (row_count + page_size - 1) // page_size if page_size > 0 else 1,
                },
                "summary": self._calculate_summary(df, report_def.column_config),
                "execution_time_ms": execution_time,
            }

        except Exception as e:
            logger.error(f"[REPORT] Erro na execução: {str(e)}")
            return {"success": False, "error": str(e), "data": [], "columns": []}

    def _build_query(self, report_def: ReportDefinition, params: dict) -> str:
        """Constrói a query SQL base."""
        if report_def.data_source == "sql":
            # Query customizada
            query_config = json.loads(report_def.query_config or "{}")
            return query_config.get("sql", "SELECT 1")

        elif report_def.data_source in self.ENTITY_QUERIES:
            # Query pré-definida da entidade
            base_query = self.ENTITY_QUERIES[report_def.data_source]

            # Aplicar filtros de data se fornecidos
            if "date_from" in params and "date_to" in params:
                base_query += " AND order_date BETWEEN :date_from AND :date_to"

            return base_query

        else:
            raise ValueError(f"Data source não suportado: {report_def.data_source}")

    def _apply_post_filters(
        self, df: pd.DataFrame, filter_config: str | None, params: dict
    ) -> pd.DataFrame:
        """Aplica filtros adicionais no DataFrame."""
        if not filter_config or df.empty:
            return df

        filters = json.loads(filter_config)

        for f in filters:
            field = f.get("field")
            op = f.get("operator", "eq")
            value = params.get(f.get("param_name", field))

            if value is None or field not in df.columns:
                continue

            if op == "eq":
                df = df[df[field] == value]
            elif op == "ne":
                df = df[df[field] != value]
            elif op == "gt":
                df = df[df[field] > value]
            elif op == "gte":
                df = df[df[field] >= value]
            elif op == "lt":
                df = df[df[field] < value]
            elif op == "lte":
                df = df[df[field] <= value]
            elif op == "in":
                df = df[df[field].isin(value if isinstance(value, list) else [value])]
            elif op == "like" and isinstance(value, str):
                df = df[df[field].astype(str).str.contains(value, case=False, na=False)]
            elif op == "between" and isinstance(value, (list, tuple)) and len(value) == 2:
                df = df[(df[field] >= value[0]) & (df[field] <= value[1])]

        return df

    def _apply_sorting(self, df: pd.DataFrame, sort_config: str | None) -> pd.DataFrame:
        """Aplica ordenação no DataFrame."""
        if not sort_config or df.empty:
            return df

        sorts = json.loads(sort_config)
        sort_fields = []
        ascending = []

        for s in sorts:
            field = s.get("field")
            if field in df.columns:
                sort_fields.append(field)
                ascending.append(s.get("direction", "asc") == "asc")

        if sort_fields:
            return df.sort_values(by=sort_fields, ascending=ascending)

        return df

    def _extract_column_metadata(self, df: pd.DataFrame, column_config: str | None) -> list[dict]:
        """Extrai metadados das colunas."""
        if column_config:
            return json.loads(column_config)

        # Inferir do DataFrame
        metadata = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            col_type = "string"
            if "int" in dtype:
                col_type = "int"
            elif "float" in dtype:
                col_type = "float"
            elif "datetime" in dtype or "date" in dtype:
                col_type = "date"
            elif "bool" in dtype:
                col_type = "bool"

            metadata.append(
                {
                    "field": col,
                    "label": col.replace("_", " ").title(),
                    "type": col_type,
                    "sortable": True,
                    "filterable": True,
                }
            )

        return metadata

    def _calculate_summary(self, df: pd.DataFrame, column_config: str | None) -> dict[str, Any]:
        """Calcula totais e resumos."""
        if df.empty:
            return {}

        summary = {}

        # Detectar colunas numéricas
        numeric_cols = df.select_dtypes(include=["number"]).columns

        for col in numeric_cols:
            summary[col] = {
                "sum": float(df[col].sum()) if not df[col].empty else 0,
                "avg": float(df[col].mean()) if not df[col].empty else 0,
                "min": float(df[col].min()) if not df[col].empty else 0,
                "max": float(df[col].max()) if not df[col].empty else 0,
                "count": int(df[col].count()),
            }

        return summary

    def get_available_entities(self) -> dict[str, str]:
        """Retorna entidades disponíveis para relatórios."""
        return {
            "products": "Produtos",
            "customers": "Clientes",
            "sales_orders": "Pedidos de Venda",
            "sales_by_product": "Vendas por Produto",
            "sales_by_period": "Vendas por Período",
            "inventory_status": "Status de Estoque",
            "financial_summary": "Resumo Financeiro",
        }

    def get_report_preview_data(self, report_def: ReportDefinition, limit: int = 5) -> list[dict]:
        """Retorna dados de preview para o builder."""
        result = self.execute_report(report_def, page_size=limit)
        return result.get("data", [])


class DashboardEngine:
    """
    Engine de dashboards com widgets configuráveis.
    """

    def __init__(self, db: Session):
        self.db = db
        self.report_engine = ReportEngine(db)

    def render_dashboard(self, dashboard_def: DashboardDefinition) -> dict[str, Any]:
        """
        Renderiza um dashboard completo com todos os widgets.
        """
        logger.info(f"[DASHBOARD] Renderizando dashboard {dashboard_def.id}")

        widgets = json.loads(dashboard_def.widget_configs or "[]")
        rendered_widgets = []

        for widget in widgets:
            try:
                widget_data = self._render_widget(widget)
                rendered_widgets.append(
                    {
                        "id": widget.get("id"),
                        "type": widget.get("type"),
                        "title": widget.get("title"),
                        "position": widget.get("position"),
                        "data": widget_data,
                    }
                )
            except Exception as e:
                logger.error(f"[DASHBOARD] Erro no widget {widget.get('id')}: {str(e)}")
                rendered_widgets.append({"id": widget.get("id"), "error": str(e)})

        return {
            "id": dashboard_def.id,
            "name": dashboard_def.name,
            "widgets": rendered_widgets,
            "layout": json.loads(dashboard_def.layout_config or '{"columns": 12}'),
        }

    def _render_widget(self, widget_config: dict) -> dict[str, Any]:
        """Renderiza um widget individual."""
        widget_type = widget_config.get("type")
        report_id = widget_config.get("report_id")

        if report_id:
            report_def = (
                self.db.query(ReportDefinition).filter(ReportDefinition.id == report_id).first()
            )

            if not report_def:
                return {"error": "Relatório não encontrado"}

            result = self.report_engine.execute_report(
                report_def, page_size=widget_config.get("limit", 100)
            )
            chart_config = json.loads(report_def.chart_config or "{}")

            if widget_type == "table":
                return {
                    "type": "table",
                    "columns": result.get("columns", []),
                    "data": result.get("data", []),
                    "summary": result.get("summary", {}),
                }

            elif widget_type == "chart":
                return {
                    "type": "chart",
                    "chart_type": chart_config.get("type", "bar"),
                    "data": result.get("data", []),
                    "x_field": chart_config.get("x"),
                    "y_field": chart_config.get("y"),
                    "series_field": chart_config.get("series"),
                }

            elif widget_type == "kpi":
                # Retornar apenas o primeiro valor como KPI
                data = result.get("data", [])
                return {
                    "type": "kpi",
                    "value": data[0].get(chart_config.get("value_field")) if data else 0,
                    "label": chart_config.get("label", "Valor"),
                    "trend": chart_config.get("trend", "neutral"),
                }

            elif widget_type == "pivot":
                return {
                    "type": "pivot",
                    "data": result.get("data", []),
                    "rows": chart_config.get("rows", []),
                    "columns": chart_config.get("columns", []),
                    "values": chart_config.get("values", []),
                }

        return {"error": "Configuração de widget inválida"}
