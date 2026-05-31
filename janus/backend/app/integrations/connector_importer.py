"""
JUNO Connector Importer — Persiste dados vindos de conectores ERP ao vivo.

Diferente de `erp_importer.py` (que importa a partir de arquivos CSV/Excel
enviados pelo usuário), este módulo é chamado por
`app.connectors.base.ERPConnectorBase` depois que um conector já buscou e
transformou os dados via API/banco do ERP.

Suporta: products, customers, sales_orders, production_orders, inventory,
suppliers, financials.

NOTA: depende de models adicionais (Inventory, Supplier, PurchaseOrder etc.)
que precisam estar declarados em `app/models.py`. Sem isso, o import quebra.
"""

import csv
import io
import json
from datetime import datetime
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.audit_logger import AuditLogger
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.models import (
    Customer,
    ErpFinancial,
    ErpImportBatch,
    Inventory,
    Product,
    ProductionOrder,
    SalesOrder,
    Supplier,
)


class ERPImporterV2:
    """
    Importador genérico de dados ERP.
    Suporta múltiplos formatos e normaliza colunas automaticamente.
    """

    ALLOWED_TYPES = [
        "products",
        "customers",
        "sales_orders",
        "production_orders",
        "inventory",
        "suppliers",
        "financials",
    ]

    COLUMN_MAPPINGS = {
        "products": {
            "name": ["name", "nome", "product_name", "descricao", "descrição"],
            "category": ["category", "categoria", "tipo", "type"],
            "standard_cost": ["standard_cost", "custo_padrao", "custo_padrão", "cost"],
            "sale_price": ["sale_price", "preco_venda", "preço_venda", "price"],
        },
        "customers": {
            "name": ["name", "nome", "customer_name", "razao_social", "razão_social"],
            "segment": ["segment", "segmento", "setor", "industry"],
        },
        "sales_orders": {
            "customer_id": ["customer_id", "cliente_id", "customer", "cliente"],
            "product_id": ["product_id", "produto_id", "product", "produto"],
            "revenue": ["revenue", "receita", "valor", "amount", "total"],
            "discount": ["discount", "desconto", "rebate"],
            "order_date": ["order_date", "data_pedido", "date", "data"],
        },
        "production_orders": {
            "product_id": ["product_id", "produto_id", "product", "produto"],
            "planned_qty": ["planned_qty", "qtd_planejada", "quantidade_planejada"],
            "actual_qty": ["actual_qty", "qtd_real", "quantidade_real"],
            "planned_cost": ["planned_cost", "custo_planejado"],
            "actual_cost": ["actual_cost", "custo_real"],
            "planned_date": ["planned_date", "data_planejada"],
            "actual_date": ["actual_date", "data_real"],
            "status": ["status", "situacao", "situação", "state"],
        },
        "inventory": {
            "product_id": ["product_id", "produto_id", "product", "produto"],
            "warehouse_location": [
                "warehouse_location",
                "local",
                "deposito",
                "depósito",
                "armazem",
            ],
            "quantity_on_hand": ["quantity_on_hand", "qtd_estoque", "estoque", "stock"],
            "quantity_reserved": ["quantity_reserved", "qtd_reservada", "reservado"],
            "unit_cost": ["unit_cost", "custo_unitario", "custo_unitário"],
        },
        "suppliers": {
            "name": ["name", "nome", "supplier_name", "fornecedor", "razao_social"],
            "cnpj": ["cnpj", "cpf", "document"],
            "contact_name": ["contact_name", "contato", "responsavel", "responsável"],
            "email": ["email", "e-mail", "mail"],
            "phone": ["phone", "telefone", "tel", "fone"],
            "payment_terms": ["payment_terms", "condicao_pagamento", "condição_pagamento", "prazo"],
            "lead_time_days": ["lead_time_days", "prazo_entrega", "lead_time", "entrega"],
        },
        "financials": {
            "document_type": ["document_type", "tipo_documento", "type"],
            "document_number": ["document_number", "numero_documento", "número_documento", "doc"],
            "account_code": ["account_code", "codigo_conta", "código_conta", "account"],
            "account_name": ["account_name", "nome_conta", "description"],
            "debit": ["debit", "debito", "débito", "dr"],
            "credit": ["credit", "credito", "crédito", "cr"],
            "period": ["period", "periodo", "período", "month", "mes", "mês"],
        },
    }

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditLogger(db)
        self.errors: list[str] = []
        self.imported = 0
        self.received = 0

    def import_data(
        self,
        company_id: int,
        data_type: str,
        file_content: bytes,
        file_name: str,
        user: Any | None = None,
    ) -> dict:
        """
        Importa dados de arquivo CSV/Excel.

        Returns:
            {
                'rows_received': int,
                'rows_imported': int,
                'rows_rejected': int,
                'errors': List[str],
                'batch_id': int
            }
        """
        if data_type not in self.ALLOWED_TYPES:
            return {
                "rows_received": 0,
                "rows_imported": 0,
                "rows_rejected": 0,
                "errors": [
                    f"Tipo de dados inválido: {data_type}. Use: {', '.join(self.ALLOWED_TYPES)}"
                ],
                "batch_id": None,
            }

        # Criar batch
        batch = ErpImportBatch(
            company_id=company_id,
            data_type=data_type,
            file_name=file_name,
            status="processing",
            created_at=utcnow_naive(),
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        try:
            # Parse arquivo
            rows = self._parse_file(file_content, file_name)
            self.received = len(rows)

            # Importar conforme tipo
            if data_type == "products":
                self._import_products(company_id, rows)
            elif data_type == "customers":
                self._import_customers(company_id, rows)
            elif data_type == "sales_orders":
                self._import_sales_orders(company_id, rows)
            elif data_type == "production_orders":
                self._import_production_orders(company_id, rows)
            elif data_type == "inventory":
                self._import_inventory(company_id, rows)
            elif data_type == "suppliers":
                self._import_suppliers(company_id, rows)
            elif data_type == "financials":
                self._import_financials(company_id, rows)

            # Atualizar batch
            batch.rows_received = self.received
            batch.rows_imported = self.imported
            batch.rows_rejected = len(self.errors)
            batch.status = "completed" if len(self.errors) < self.received else "partial"
            batch.error_message = json.dumps(self.errors[:10]) if self.errors else None
            self.db.commit()

            # Auditoria
            self.audit.log_import(batch.id, company_id, data_type, self.imported, user)

            return {
                "rows_received": self.received,
                "rows_imported": self.imported,
                "rows_rejected": len(self.errors),
                "errors": self.errors[:20],
                "batch_id": batch.id,
            }

        except Exception as e:
            batch.status = "failed"
            batch.error_message = str(e)
            self.db.commit()
            raise

    def _parse_file(self, content: bytes, file_name: str) -> list[dict]:
        """Parse arquivo CSV ou Excel."""
        if file_name.endswith(".csv"):
            return self._parse_csv(content)
        elif file_name.endswith((".xlsx", ".xls")):
            return self._parse_excel(content)
        else:
            raise ValueError("Formato não suportado. Use CSV ou Excel.")

    def _parse_csv(self, content: bytes) -> list[dict]:
        """Parse CSV."""
        text_content = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text_content))
        return list(reader)

    def _parse_excel(self, content: bytes) -> list[dict]:
        """Parse Excel usando pandas."""
        import pandas as pd

        df = pd.read_excel(io.BytesIO(content))
        return df.to_dict("records")

    def _normalize_columns(self, row: dict, data_type: str) -> dict:
        """Normaliza nomes de colunas para padrão snake_case."""
        mappings = self.COLUMN_MAPPINGS.get(data_type, {})
        normalized = {}

        for standard_name, aliases in mappings.items():
            for alias in aliases:
                if alias in row:
                    normalized[standard_name] = row[alias]
                    break

        return normalized

    def _safe_float(self, value, default=0.0):
        """Converte valor para float de forma segura."""
        if value is None or value == "":
            return default
        try:
            return float(
                str(value).replace(".", "").replace(",", ".") if isinstance(value, str) else value
            )
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default=0):
        """Converte valor para int de forma segura."""
        if value is None or value == "":
            return default
        try:
            return int(
                float(
                    str(value).replace(".", "").replace(",", ".")
                    if isinstance(value, str)
                    else value
                )
            )
        except (TypeError, ValueError):
            return default

    def _safe_date(self, value, default=None):
        """Converte valor para datetime de forma segura."""
        if value is None or value == "":
            return default
        try:
            if isinstance(value, datetime):
                return value
            # Tentar múltiplos formatos
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(str(value), fmt)
                except ValueError:
                    continue
            return default
        except (TypeError, ValueError):
            return default

    # ============================================================
    # IMPORTADORES ESPECÍFICOS
    # ============================================================

    def _import_products(self, company_id: int, rows: list[dict]):
        """Importa produtos."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "products")

                product = Product(
                    company_id=company_id,
                    name=norm.get("name", f"Produto_{i}"),
                    category=norm.get("category", "Geral"),
                    standard_cost=self._safe_float(norm.get("standard_cost")),
                    sale_price=self._safe_float(norm.get("sale_price")),
                    created_at=utcnow_naive(),
                )
                self.db.add(product)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _import_customers(self, company_id: int, rows: list[dict]):
        """Importa clientes."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "customers")

                customer = Customer(
                    company_id=company_id,
                    name=norm.get("name", f"Cliente_{i}"),
                    segment=norm.get("segment", "Geral"),
                    created_at=utcnow_naive(),
                )
                self.db.add(customer)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _import_sales_orders(self, company_id: int, rows: list[dict]):
        """Importa pedidos de venda."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "sales_orders")

                # Resolver customer_id e product_id por nome se necessário
                customer_id = self._resolve_customer(company_id, norm.get("customer_id"))
                product_id = self._resolve_product(company_id, norm.get("product_id"))

                order = SalesOrder(
                    company_id=company_id,
                    customer_id=customer_id,
                    product_id=product_id,
                    revenue=self._safe_float(norm.get("revenue")),
                    discount=self._safe_float(norm.get("discount")),
                    order_date=self._safe_date(norm.get("order_date")),
                    created_at=utcnow_naive(),
                )
                self.db.add(order)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _import_production_orders(self, company_id: int, rows: list[dict]):
        """Importa ordens de produção."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "production_orders")

                product_id = self._resolve_product(company_id, norm.get("product_id"))

                order = ProductionOrder(
                    company_id=company_id,
                    product_id=product_id,
                    planned_qty=self._safe_int(norm.get("planned_qty")),
                    actual_qty=self._safe_int(norm.get("actual_qty")),
                    planned_cost=self._safe_float(norm.get("planned_cost")),
                    actual_cost=self._safe_float(norm.get("actual_cost")),
                    planned_date=self._safe_date(norm.get("planned_date")),
                    actual_date=self._safe_date(norm.get("actual_date")),
                    status=norm.get("status", "planned"),
                    created_at=utcnow_naive(),
                )
                self.db.add(order)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _import_inventory(self, company_id: int, rows: list[dict]):
        """Importa estoque."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "inventory")

                product_id = self._resolve_product(company_id, norm.get("product_id"))
                qty_on_hand = self._safe_int(norm.get("quantity_on_hand"))
                qty_reserved = self._safe_int(norm.get("quantity_reserved"))

                item = Inventory(
                    company_id=company_id,
                    product_id=product_id,
                    warehouse_location=norm.get("warehouse_location", "Principal"),
                    quantity_on_hand=qty_on_hand,
                    quantity_reserved=qty_reserved,
                    quantity_available=max(0, qty_on_hand - qty_reserved),
                    unit_cost=self._safe_float(norm.get("unit_cost")),
                    last_movement_date=utcnow_naive(),
                    created_at=utcnow_naive(),
                )
                self.db.add(item)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _import_suppliers(self, company_id: int, rows: list[dict]):
        """Importa fornecedores."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "suppliers")

                supplier = Supplier(
                    company_id=company_id,
                    name=norm.get("name", f"Fornecedor_{i}"),
                    cnpj=norm.get("cnpj"),
                    contact_name=norm.get("contact_name"),
                    email=norm.get("email"),
                    phone=norm.get("phone"),
                    payment_terms=norm.get("payment_terms"),
                    lead_time_days=self._safe_int(norm.get("lead_time_days")),
                    status="active",
                    created_at=utcnow_naive(),
                )
                self.db.add(supplier)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _import_financials(self, company_id: int, rows: list[dict]):
        """Importa dados financeiros do ERP."""
        for i, row in enumerate(rows):
            try:
                norm = self._normalize_columns(row, "financials")

                financial = ErpFinancial(
                    company_id=company_id,
                    document_type=norm.get("document_type", "LANCAMENTO"),
                    document_number=norm.get("document_number"),
                    account_code=norm.get("account_code"),
                    account_name=norm.get("account_name"),
                    debit=self._safe_float(norm.get("debit")),
                    credit=self._safe_float(norm.get("credit")),
                    balance=self._safe_float(norm.get("debit"))
                    - self._safe_float(norm.get("credit")),
                    period=norm.get("period"),
                    posting_date=self._safe_date(norm.get("posting_date")),
                    created_at=utcnow_naive(),
                )
                self.db.add(financial)
                self.imported += 1

            except Exception as e:
                self.errors.append(f"Linha {i+1}: {str(e)}")

        self.db.commit()

    def _resolve_customer(self, company_id: int, identifier) -> int | None:
        """Resolve customer_id por nome ou ID."""
        if not identifier:
            return None

        # Tentar por ID direto
        try:
            return int(identifier)
        except (TypeError, ValueError):
            pass

        # Buscar por nome
        customer = (
            self.db.query(Customer)
            .filter(Customer.company_id == company_id, Customer.name.ilike(f"%{identifier}%"))
            .first()
        )

        return customer.id if customer else None

    def _resolve_product(self, company_id: int, identifier) -> int | None:
        """Resolve product_id por nome ou ID."""
        if not identifier:
            return None

        try:
            return int(identifier)
        except (TypeError, ValueError):
            pass

        product = (
            self.db.query(Product)
            .filter(Product.company_id == company_id, Product.name.ilike(f"%{identifier}%"))
            .first()
        )

        return product.id if product else None


def get_erp_importer(db: Session = Depends(get_db)) -> ERPImporterV2:
    """Factory para injeção de dependência."""
    return ERPImporterV2(db)
