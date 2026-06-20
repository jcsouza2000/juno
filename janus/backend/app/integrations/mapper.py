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
    "inventory": {
        # Portuguese
        "produto": "product_name",
        "descricao": "product_name",
        "nome_produto": "product_name",
        "id_produto": "product_name",
        "deposito": "warehouse_location",
        "armazem": "warehouse_location",
        "local": "warehouse_location",
        "localizacao": "warehouse_location",
        "saldo": "quantity_on_hand",
        "quantidade": "quantity_on_hand",
        "qtd_estoque": "quantity_on_hand",
        "estoque": "quantity_on_hand",
        "saldo_disponivel": "quantity_available",
        "disponivel": "quantity_available",
        "reservado": "quantity_reserved",
        "qtd_reservada": "quantity_reserved",
        "custo_unitario": "unit_cost",
        "custo": "unit_cost",
        "estoque_minimo": "min_stock_level",
        "estoque_maximo": "max_stock_level",
        "data_movimento": "last_movement_date",
        "ultima_movimentacao": "last_movement_date",
        # English
        "product_name": "product_name",
        "product": "product_name",
        "warehouse": "warehouse_location",
        "warehouse_location": "warehouse_location",
        "location": "warehouse_location",
        "quantity_on_hand": "quantity_on_hand",
        "on_hand": "quantity_on_hand",
        "quantity": "quantity_on_hand",
        "available": "quantity_available",
        "quantity_available": "quantity_available",
        "reserved": "quantity_reserved",
        "quantity_reserved": "quantity_reserved",
        "unit_cost": "unit_cost",
        "cost": "unit_cost",
        "min_stock": "min_stock_level",
        "max_stock": "max_stock_level",
        "last_movement_date": "last_movement_date",
    },
    "suppliers": {
        # Portuguese
        "codigo_fornecedor": "external_code",
        "cod_fornecedor": "external_code",
        "fornecedor": "name",
        "nome_fornecedor": "name",
        "razao_social": "name",
        "cnpj": "cnpj",
        "contato": "contact_name",
        "nome_contato": "contact_name",
        "email": "email",
        "e_mail": "email",
        "telefone": "phone",
        "fone": "phone",
        "endereco": "address",
        "condicao_pagamento": "payment_terms",
        "prazo_pagamento": "payment_terms",
        "prazo_entrega": "lead_time_days",
        "lead_time": "lead_time_days",
        "avaliacao": "rating",
        "nota": "rating",
        "situacao": "status",
        # English
        "supplier_code": "external_code",
        "supplier": "name",
        "supplier_name": "name",
        "name": "name",
        "tax_id": "cnpj",
        "contact": "contact_name",
        "contact_name": "contact_name",
        "phone": "phone",
        "address": "address",
        "payment_terms": "payment_terms",
        "lead_time_days": "lead_time_days",
        "rating": "rating",
        "status": "status",
    },
    "financials": {
        # Portuguese
        "tipo_documento": "document_type",
        "tipo_lancamento": "document_type",
        "documento": "document_number",
        "num_documento": "document_number",
        "numero_documento": "document_number",
        "codigo_conta": "account_code",
        "conta": "account_name",
        "nome_conta": "account_name",
        "descricao": "account_name",
        "historico": "account_name",
        "debito": "debit",
        "credito": "credit",
        "saldo": "balance",
        "valor": "balance",
        "periodo": "period",
        "competencia": "period",
        "data_lancamento": "posting_date",
        "data": "posting_date",
        # English
        "document_type": "document_type",
        "entry_type": "document_type",
        "document": "document_number",
        "document_number": "document_number",
        "account_code": "account_code",
        "account": "account_name",
        "account_name": "account_name",
        "description": "account_name",
        "debit": "debit",
        "credit": "credit",
        "balance": "balance",
        "amount": "balance",
        "period": "period",
        "posting_date": "posting_date",
        "date": "posting_date",
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
