import json
import math
from datetime import date as date_type

import pandas as pd
from sqlalchemy.orm import Session

from ..event_logging import log_event
from ..models import (
    AuditLog,
    Customer,
    ErpImportBatch,
    Product,
    ProductionOrder,
    SalesOrder,
)
from .file_parser import parse_erp_file
from .mapper import apply_mapping, normalize_columns
from .validators import validate_payload

# ── Type helpers ──────────────────────────────────────────────────────────────


def _safe_str(value, default: str = "") -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return str(value).strip()


def _clean_numeric(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "")
    # Brazilian format: 1.000,50 → 1000.50
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _clean_date(value) -> date_type | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


# ── Public entry point ────────────────────────────────────────────────────────


def import_erp_data(
    company_id: int,
    data_type: str,
    file_path: str,
    file_name: str,
    db: Session,
) -> dict:
    # 1. Parse file
    try:
        df = parse_erp_file(file_path)
    except Exception as exc:
        _save_batch(db, company_id, data_type, file_name, 0, 0, 0, "error", str(exc))
        db.commit()
        return _result(company_id, data_type, 0, 0, 0, [str(exc)], "error")

    rows_received = len(df)

    # 2. Normalize + map
    df = normalize_columns(df)
    df = apply_mapping(df, data_type)

    # 3. Validate required columns
    check = validate_payload(data_type, list(df.columns))
    if not check["valid"]:
        msg = f"Campos obrigatórios ausentes após mapeamento: {check['missing']}"
        _save_batch(
            db, company_id, data_type, file_name, rows_received, 0, rows_received, "error", msg
        )
        db.commit()
        return _result(company_id, data_type, rows_received, 0, rows_received, [msg], "error")

    # 4. Import by type
    dispatch = {
        "products": _import_products,
        "customers": _import_customers,
        "sales_orders": _import_sales_orders,
        "production_orders": _import_production_orders,
    }
    handler = dispatch.get(data_type)
    if handler:
        imported, rejected, errors = handler(df, company_id, db)
    else:
        imported, rejected = 0, rows_received
        errors = [
            f"Tipo '{data_type}' recebido — armazenamento direto não implementado nesta versão."
        ]

    status = "success" if rejected == 0 else ("partial" if imported > 0 else "error")

    # 5. Audit + batch record
    db.add(
        AuditLog(
            company_id=company_id,
            action=f"import_{data_type}",
            resource_type=data_type,
            new_values=json.dumps(
                {
                    "file_name": file_name,
                    "rows_received": rows_received,
                    "imported": imported,
                    "rejected": rejected,
                    "status": status,
                },
                default=str,
                ensure_ascii=False,
            ),
            success=status in {"success", "partial"},
            severity="info" if status == "success" else "warning",
        )
    )
    _save_batch(
        db,
        company_id,
        data_type,
        file_name,
        rows_received,
        imported,
        rejected,
        status,
        "; ".join(errors[:5]) if errors else None,
    )

    # Event log incremental (sem afetar fluxo principal)
    log_event(
        db=db,
        company_id=company_id,
        entity_type=data_type,
        entity_id=None,
        event_type="erp_import",
        old_state=None,
        new_state={
            "file_name": file_name,
            "rows_received": rows_received,
            "rows_imported": imported,
            "rows_rejected": rejected,
            "status": status,
        },
        user_id="erp_import",
    )

    db.commit()

    return _result(company_id, data_type, rows_received, imported, rejected, errors[:10], status)


# ── Per-type importers ────────────────────────────────────────────────────────


def _import_products(df: pd.DataFrame, company_id: int, db: Session):
    imported, rejected, errors = 0, 0, []
    for row_idx, row in df.iterrows():
        try:
            name = _safe_str(row.get("name"))
            if not name:
                rejected += 1
                errors.append(f"Linha {row_idx + 2}: nome do produto vazio — ignorado")
                continue

            existing = db.query(Product).filter_by(company_id=company_id, name=name).first()
            if existing:
                if _safe_str(row.get("category")):
                    existing.category = _safe_str(row.get("category"))
                if _clean_numeric(row.get("standard_cost")) is not None:
                    existing.standard_cost = _clean_numeric(row.get("standard_cost"))
                if _clean_numeric(row.get("sale_price")) is not None:
                    existing.sale_price = _clean_numeric(row.get("sale_price"))
            else:
                db.add(
                    Product(
                        company_id=company_id,
                        name=name,
                        category=_safe_str(row.get("category")) or "Importado ERP",
                        standard_cost=_clean_numeric(row.get("standard_cost")),
                        sale_price=_clean_numeric(row.get("sale_price")),
                    )
                )
            imported += 1
        except Exception as exc:
            rejected += 1
            errors.append(f"Linha {row_idx + 2}: {exc}")
    return imported, rejected, errors


def _import_customers(df: pd.DataFrame, company_id: int, db: Session):
    imported, rejected, errors = 0, 0, []
    for row_idx, row in df.iterrows():
        try:
            name = _safe_str(row.get("name"))
            if not name:
                rejected += 1
                errors.append(f"Linha {row_idx + 2}: nome do cliente vazio — ignorado")
                continue

            existing = db.query(Customer).filter_by(company_id=company_id, name=name).first()
            if not existing:
                db.add(
                    Customer(
                        company_id=company_id,
                        name=name,
                        segment=_safe_str(row.get("segment")) or "Importado ERP",
                    )
                )
            imported += 1
        except Exception as exc:
            rejected += 1
            errors.append(f"Linha {row_idx + 2}: {exc}")
    return imported, rejected, errors


def _import_sales_orders(df: pd.DataFrame, company_id: int, db: Session):
    imported, rejected, errors = 0, 0, []
    for row_idx, row in df.iterrows():
        try:
            product_name = _safe_str(row.get("product_name"))
            revenue = _clean_numeric(row.get("revenue"))

            if not product_name or revenue is None:
                rejected += 1
                errors.append(f"Linha {row_idx + 2}: produto ou receita ausente — ignorado")
                continue

            product = _get_or_create_product(db, company_id, product_name)
            customer = _get_or_create_customer(db, company_id, _safe_str(row.get("customer_name")))

            db.add(
                SalesOrder(
                    company_id=company_id,
                    customer_id=customer.id if customer else None,
                    product_id=product.id,
                    revenue=revenue,
                    discount=_clean_numeric(row.get("discount")) or 0.0,
                    order_date=_clean_date(row.get("order_date")),
                )
            )
            imported += 1
        except Exception as exc:
            rejected += 1
            errors.append(f"Linha {row_idx + 2}: {exc}")
    return imported, rejected, errors


def _import_production_orders(df: pd.DataFrame, company_id: int, db: Session):
    imported, rejected, errors = 0, 0, []
    for row_idx, row in df.iterrows():
        try:
            product_name = _safe_str(row.get("product_name"))
            planned_qty = _clean_numeric(row.get("planned_qty"))
            actual_qty = _clean_numeric(row.get("actual_qty"))

            if not product_name or planned_qty is None or actual_qty is None:
                rejected += 1
                errors.append(f"Linha {row_idx + 2}: produto ou quantidades ausentes — ignorado")
                continue

            product = _get_or_create_product(db, company_id, product_name)

            db.add(
                ProductionOrder(
                    company_id=company_id,
                    product_id=product.id,
                    planned_qty=int(planned_qty),
                    actual_qty=int(actual_qty),
                    planned_cost=_clean_numeric(row.get("planned_cost")),
                    actual_cost=_clean_numeric(row.get("actual_cost")),
                    planned_date=_clean_date(row.get("planned_date")),
                    actual_date=_clean_date(row.get("actual_date")),
                    status=_safe_str(row.get("status")) or "Importado",
                )
            )
            imported += 1
        except Exception as exc:
            rejected += 1
            errors.append(f"Linha {row_idx + 2}: {exc}")
    return imported, rejected, errors


# ── DB helpers ────────────────────────────────────────────────────────────────


def _get_or_create_product(db: Session, company_id: int, name: str) -> Product:
    obj = db.query(Product).filter_by(company_id=company_id, name=name).first()
    if not obj:
        obj = Product(company_id=company_id, name=name, category="Importado ERP")
        db.add(obj)
        db.flush()
    return obj


def _get_or_create_customer(db: Session, company_id: int, name: str) -> Customer | None:
    if not name:
        return None
    obj = db.query(Customer).filter_by(company_id=company_id, name=name).first()
    if not obj:
        obj = Customer(company_id=company_id, name=name, segment="Importado ERP")
        db.add(obj)
        db.flush()
    return obj


def _save_batch(
    db: Session, company_id, data_type, file_name, received, imported, rejected, status, error_msg
):
    db.add(
        ErpImportBatch(
            company_id=company_id,
            data_type=data_type,
            file_name=file_name,
            rows_received=received,
            rows_imported=imported,
            rows_rejected=rejected,
            status=status,
            error_message=error_msg,
        )
    )


def _result(company_id, data_type, received, imported, rejected, errors, status) -> dict:
    return {
        "company_id": company_id,
        "data_type": data_type,
        "rows_received": received,
        "rows_imported": imported,
        "rows_rejected": rejected,
        "errors": errors,
        "status": status,
    }
