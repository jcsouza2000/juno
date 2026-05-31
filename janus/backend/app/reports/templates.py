"""
JUNO Report Templates
Templates pré-configurados para relatórios comuns
"""

import json

REPORT_TEMPLATES = {
    "sales_summary": {
        "name": "Resumo de Vendas",
        "description": "Visão geral das vendas por período com totais e tendências",
        "report_type": "table",
        "data_source": "sales_by_period",
        "column_config": json.dumps(
            [
                {"field": "period", "label": "Período", "type": "date", "format": "MMM/yyyy"},
                {"field": "order_count", "label": "Qtd. Pedidos", "type": "int"},
                {
                    "field": "total_revenue",
                    "label": "Receita Total",
                    "type": "float",
                    "format": "currency",
                },
                {
                    "field": "avg_order_value",
                    "label": "Ticket Médio",
                    "type": "float",
                    "format": "currency",
                },
            ]
        ),
        "chart_config": json.dumps(
            {"type": "line", "x": "period", "y": "total_revenue", "secondary_y": "order_count"}
        ),
        "sort_config": json.dumps([{"field": "period", "direction": "desc"}]),
        "template_category": "sales",
    },
    "top_products": {
        "name": "Top Produtos",
        "description": "Produtos mais vendidos por quantidade e receita",
        "report_type": "table",
        "data_source": "sales_by_product",
        "column_config": json.dumps(
            [
                {"field": "product_name", "label": "Produto", "type": "string"},
                {"field": "category", "label": "Categoria", "type": "string"},
                {"field": "total_quantity", "label": "Qtd. Vendida", "type": "int"},
                {
                    "field": "total_revenue",
                    "label": "Receita",
                    "type": "float",
                    "format": "currency",
                },
                {"field": "order_count", "label": "Pedidos", "type": "int"},
            ]
        ),
        "chart_config": json.dumps(
            {"type": "bar", "x": "product_name", "y": "total_revenue", "limit": 10}
        ),
        "sort_config": json.dumps([{"field": "total_revenue", "direction": "desc"}]),
        "template_category": "sales",
    },
    "inventory_alert": {
        "name": "Alerta de Estoque",
        "description": "Produtos com estoque baixo ou crítico",
        "report_type": "table",
        "data_source": "inventory_status",
        "column_config": json.dumps(
            [
                {"field": "name", "label": "Produto", "type": "string"},
                {"field": "sku", "label": "SKU", "type": "string"},
                {"field": "category", "label": "Categoria", "type": "string"},
                {"field": "stock_quantity", "label": "Estoque Atual", "type": "int"},
                {"field": "min_stock", "label": "Estoque Mínimo", "type": "int"},
                {"field": "available_stock", "label": "Disponível", "type": "int"},
                {"field": "stock_status", "label": "Status", "type": "string"},
            ]
        ),
        "filter_config": json.dumps(
            [{"field": "stock_status", "operator": "in", "param_name": "status_filter"}]
        ),
        "chart_config": json.dumps({"type": "pie", "x": "stock_status", "y": "count"}),
        "sort_config": json.dumps([{"field": "available_stock", "direction": "asc"}]),
        "template_category": "inventory",
    },
    "customer_analysis": {
        "name": "Análise de Clientes",
        "description": "Segmentação e análise de clientes",
        "report_type": "table",
        "data_source": "customers",
        "column_config": json.dumps(
            [
                {"field": "name", "label": "Cliente", "type": "string"},
                {"field": "segment", "label": "Segmento", "type": "string"},
                {"field": "city", "label": "Cidade", "type": "string"},
                {"field": "state", "label": "Estado", "type": "string"},
            ]
        ),
        "group_by_config": json.dumps(["segment", "state"]),
        "template_category": "sales",
    },
    "financial_performance": {
        "name": "Performance Financeira",
        "description": "Receita, custos e lucro estimado por período",
        "report_type": "table",
        "data_source": "financial_summary",
        "column_config": json.dumps(
            [
                {"field": "period", "label": "Período", "type": "date", "format": "MMM/yyyy"},
                {"field": "revenue", "label": "Receita", "type": "float", "format": "currency"},
                {
                    "field": "estimated_cost",
                    "label": "Custo Estimado",
                    "type": "float",
                    "format": "currency",
                },
                {
                    "field": "estimated_profit",
                    "label": "Lucro Estimado",
                    "type": "float",
                    "format": "currency",
                },
            ]
        ),
        "chart_config": json.dumps(
            {"type": "area", "x": "period", "y": "revenue", "secondary_y": "estimated_profit"}
        ),
        "template_category": "financial",
    },
    "kpi_dashboard": {
        "name": "KPIs do Negócio",
        "description": "Dashboard com indicadores-chave em tempo real",
        "report_type": "dashboard",
        "data_source": "financial_summary",
        "template_category": "operational",
    },
}


def get_template(template_key: str) -> dict:
    """Retorna configuração de um template."""
    return REPORT_TEMPLATES.get(template_key, {})


def list_templates(category: str | None = None) -> dict[str, dict]:
    """Lista templates disponíveis, opcionalmente filtrados por categoria."""
    if category:
        return {k: v for k, v in REPORT_TEMPLATES.items() if v.get("template_category") == category}
    return REPORT_TEMPLATES


def create_from_template(template_key: str, company_id: int, user_id: int) -> dict:
    """Cria configuração de relatório a partir de template."""
    template = get_template(template_key)
    if not template:
        raise ValueError(f"Template não encontrado: {template_key}")

    return {"company_id": company_id, "created_by": user_id, "is_template": False, **template}
