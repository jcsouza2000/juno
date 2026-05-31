import re

import pandas as pd

# ── ERP → Juno canonical field mapping ──────────────────────────────────────
# Supports Portuguese and English column names from any ERP export.
ERP_MAPPINGS: dict[str, dict[str, str]] = {
    "products": {
        # Portuguese
        "codigo": "external_code",
        "cod_produto": "external_code",
        "produto": "name",
        "descricao": "name",
        "desc_produto": "name",
        "nome_produto": "name",
        "categoria": "category",
        "grupo": "category",
        "grupo_produto": "category",
        "custo_padrao": "standard_cost",
        "custo_standard": "standard_cost",
        "custo": "standard_cost",
        "custo_unitario": "standard_cost",
        "preco_venda": "sale_price",
        "preco": "sale_price",
        "valor_venda": "sale_price",
        # English
        "code": "external_code",
        "product_code": "external_code",
        "name": "name",
        "description": "name",
        "category": "category",
        "group": "category",
        "standard_cost": "standard_cost",
        "cost": "standard_cost",
        "sale_price": "sale_price",
        "price": "sale_price",
    },
    "customers": {
        # Portuguese
        "codigo_cliente": "external_code",
        "cod_cliente": "external_code",
        "cliente": "name",
        "nome_cliente": "name",
        "razao_social": "name",
        "segmento": "segment",
        "setor": "segment",
        "tipo_cliente": "segment",
        # English
        "customer_code": "external_code",
        "customer": "name",
        "customer_name": "name",
        "company_name": "name",
        "segment": "segment",
        "sector": "segment",
    },
    "sales_orders": {
        # Portuguese
        "pedido": "external_order_id",
        "num_pedido": "external_order_id",
        "numero_pedido": "external_order_id",
        "cliente": "customer_name",
        "nome_cliente": "customer_name",
        "id_cliente": "customer_name",
        "produto": "product_name",
        "descricao": "product_name",
        "nome_produto": "product_name",
        "id_produto": "product_name",
        "receita": "revenue",
        "faturamento": "revenue",
        "valor_total": "revenue",
        "valor": "revenue",
        "total": "revenue",
        "desconto": "discount",
        "desc": "discount",
        "data_pedido": "order_date",
        "data_emissao": "order_date",
        "data": "order_date",
        # English
        "order_id": "external_order_id",
        "order_number": "external_order_id",
        "customer_name": "customer_name",
        "product_name": "product_name",
        "product": "product_name",
        "revenue": "revenue",
        "discount": "discount",
        "order_date": "order_date",
        "date": "order_date",
    },
    "production_orders": {
        # Portuguese
        "op": "external_order_id",
        "num_op": "external_order_id",
        "ordem_producao": "external_order_id",
        "produto": "product_name",
        "descricao": "product_name",
        "nome_produto": "product_name",
        "id_produto": "product_name",
        "qtd_planejada": "planned_qty",
        "quantidade_planejada": "planned_qty",
        "qty_planejada": "planned_qty",
        "qtd_real": "actual_qty",
        "quantidade_real": "actual_qty",
        "quantidade_produzida": "actual_qty",
        "qty_real": "actual_qty",
        "custo_planejado": "planned_cost",
        "custo_previsto": "planned_cost",
        "custo_real": "actual_cost",
        "custo_realizado": "actual_cost",
        "data_planejada": "planned_date",
        "data_prevista": "planned_date",
        "data_inicio": "planned_date",
        "data_real": "actual_date",
        "data_conclusao": "actual_date",
        "data_fim": "actual_date",
        "status": "status",
        "situacao": "status",
        # English
        "order_id": "external_order_id",
        "product_name": "product_name",
        "product": "product_name",
        "planned_qty": "planned_qty",
        "actual_qty": "actual_qty",
        "planned_cost": "planned_cost",
        "actual_cost": "actual_cost",
        "planned_date": "planned_date",
        "actual_date": "actual_date",
    },
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip and slugify column names."""

    def _slug(col: str) -> str:
        c = str(col).strip().lower()
        c = re.sub(r"[áàãâä]", "a", c)
        c = re.sub(r"[éèêë]", "e", c)
        c = re.sub(r"[íìîï]", "i", c)
        c = re.sub(r"[óòõôö]", "o", c)
        c = re.sub(r"[úùûü]", "u", c)
        c = re.sub(r"[ç]", "c", c)
        c = re.sub(r"[^a-z0-9]+", "_", c)
        c = c.strip("_")
        return c

    df.columns = [_slug(col) for col in df.columns]
    return df


def apply_mapping(df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """Rename ERP columns to Juno canonical names. First match wins."""
    mapping = ERP_MAPPINGS.get(data_type, {})
    rename: dict[str, str] = {}
    already_targeted: set[str] = set()

    for col in df.columns:
        if col in mapping:
            target = mapping[col]
            if target not in already_targeted:
                rename[col] = target
                already_targeted.add(target)

    return df.rename(columns=rename)
