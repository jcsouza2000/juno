"""
Gestao de dados do tenant — "Deposito de dados" (Fase 0+3 do roadmap).

Fornece duas capacidades sobre os dados ja persistidos:

  1. Inventario ("Meus dados"): o que esta depositado por grupo/tabela
     (contagem de linhas, periodos financeiros, historico de uploads).
  2. Purge controlado: exclusao por escopo (financeiro, ERP operacional ou
     tudo), exigindo token de dupla confirmacao no router.

SEGURANCA: o purge NUNCA apaga usuarios, vinculos (user_companies), roles,
conexoes ERP (config/credenciais), auditoria, definicoes de relatorio ou
dashboards. So' remove DADOS DE NEGOCIO (financeiro + operacional ERP) e os
KPIs derivados (score_history) — tudo escopado por company_id.

Decisao de design: nao criamos uma tabela nova "DataDeposit". Os registros de
deposito ja existem em FinancialUploadBatch (uploads financeiros) e
ERPImportBatch (importacoes ERP); este modulo os trata como o historico de
deposito e constroi inventario + purge por cima, sem migration.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from .data_versioning import get_active_batch_id, list_versions
from .models import (
    Customer,
    ErpFinancial,
    ERPImportBatch,
    FinancialStatement,
    FinancialUploadBatch,
    Inventory,
    Product,
    ProductionOrder,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    ScoreHistory,
    Supplier,
    SupplierProduct,
)

# ── Definicao dos grupos de dados ────────────────────────────────────────────
# Cada item: (nome_tabela, model). Apenas models com company_id direto entram
# aqui; tabelas-filho (sem company_id) sao tratadas a parte no purge.

_GROUPS: dict[str, dict] = {
    "financial": {
        "label": "Financeiro",
        "models": [
            ("erp_financials", ErpFinancial),
            ("financial_statements", FinancialStatement),
            ("financial_upload_batches", FinancialUploadBatch),
        ],
    },
    "erp": {
        "label": "Operacional ERP",
        "models": [
            ("sales_orders", SalesOrder),
            ("production_orders", ProductionOrder),
            ("purchase_orders", PurchaseOrder),
            ("inventory", Inventory),
            ("products", Product),
            ("customers", Customer),
            ("suppliers", Supplier),
            ("erp_import_batches", ERPImportBatch),
        ],
    },
    "derived": {
        "label": "KPIs derivados",
        "models": [
            ("score_history", ScoreHistory),
        ],
    },
}

# Escopos aceitos pelo purge -> grupos afetados.
# "all" inclui derived; "financial"/"erp" tambem limpam KPIs derivados, pois
# o score depende desses dados e ficaria desatualizado.
_SCOPE_GROUPS: dict[str, list[str]] = {
    "financial": ["financial", "derived"],
    "erp": ["erp", "derived"],
    "all": ["financial", "erp", "derived"],
}

VALID_SCOPES = tuple(_SCOPE_GROUPS.keys())


def _count(db: Session, model, company_id: int) -> int:
    return int(db.query(func.count(model.id)).filter(model.company_id == company_id).scalar() or 0)


# ── Inventario ("Meus dados") ────────────────────────────────────────────────


def get_company_data_inventory(db: Session, company_id: int) -> dict:
    """Resumo do que esta depositado para o tenant, por grupo e tabela."""
    groups_out = []
    grand_total = 0
    for group_key, spec in _GROUPS.items():
        tables = []
        group_total = 0
        for table_name, model in spec["models"]:
            rows = _count(db, model, company_id)
            group_total += rows
            tables.append({"table": table_name, "rows": rows})
        grand_total += group_total
        groups_out.append(
            {
                "group": group_key,
                "label": spec["label"],
                "total_rows": group_total,
                "tables": tables,
            }
        )

    return {
        "company_id": company_id,
        "total_rows": grand_total,
        "groups": groups_out,
        "periods": _available_periods(db, company_id),
        "uploads": _recent_deposits(db, company_id),
        "active_versions": {
            "financial_batch_id": get_active_batch_id(db, company_id, "financial"),
            "erp_batch_id": get_active_batch_id(db, company_id, "erp"),
        },
        "versions": {
            "financial": list_versions(db, company_id, "financial"),
            "erp": list_versions(db, company_id, "erp"),
        },
    }


def _available_periods(db: Session, company_id: int) -> list[str]:
    """Periodos (YYYY-MM) com dados financeiros, ordenados."""
    periods: set[str] = set()
    for model in (FinancialStatement, ErpFinancial):
        rows = (
            db.query(model.period)
            .filter(model.company_id == company_id, model.period.isnot(None))
            .distinct()
            .all()
        )
        periods.update(p[0] for p in rows if p[0])
    return sorted(periods)


def _recent_deposits(db: Session, company_id: int, limit: int = 20) -> list[dict]:
    """Historico de depositos: uploads financeiros + importacoes ERP."""
    deposits: list[dict] = []

    fin = (
        db.query(FinancialUploadBatch)
        .filter(FinancialUploadBatch.company_id == company_id)
        .order_by(FinancialUploadBatch.created_at.desc())
        .limit(limit)
        .all()
    )
    for b in fin:
        deposits.append(
            {
                "source": "financial",
                "id": b.id,
                "file_name": b.file_name,
                "periods": b.periods,
                "rows": b.rows_imported,
                "status": b.status,
                "version_number": getattr(b, "version_number", 1),
                "version_label": f"v{getattr(b, 'version_number', 1)}",
                "is_active": bool(getattr(b, "is_active", True)),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
        )

    erp = (
        db.query(ERPImportBatch)
        .filter(ERPImportBatch.company_id == company_id)
        .order_by(ERPImportBatch.created_at.desc())
        .limit(limit)
        .all()
    )
    for b in erp:
        deposits.append(
            {
                "source": "erp",
                "id": b.id,
                "file_name": b.file_name,
                "data_type": b.data_type,
                "rows": b.rows_imported,
                "status": b.status,
                "version_number": getattr(b, "version_number", 1),
                "version_label": f"v{getattr(b, 'version_number', 1)}",
                "is_active": bool(getattr(b, "is_active", True)),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
        )

    deposits.sort(key=lambda d: d["created_at"] or "", reverse=True)
    return deposits[:limit]


# ── Purge controlado ─────────────────────────────────────────────────────────


def purge_company_data(db: Session, company_id: int, scope: str) -> dict[str, int]:
    """
    Apaga os dados de negocio do tenant para o escopo dado.

    Retorna {tabela: linhas_removidas}. NAO faz commit por si — o chamador
    decide (aqui commitamos ao final para manter a operacao atomica).

    Tabelas-filho sem company_id (purchase_order_items, supplier_products) sao
    removidas via subconsulta dos pais ANTES dos pais, evitando violacao de FK.
    """
    if scope not in _SCOPE_GROUPS:
        raise ValueError(f"escopo invalido: {scope!r}. Use um de {VALID_SCOPES}.")

    groups = _SCOPE_GROUPS[scope]
    deleted: dict[str, int] = {}

    # 1) Filhos primeiro (somente quando o grupo ERP esta no escopo).
    if "erp" in groups:
        po_ids = db.query(PurchaseOrder.id).filter(PurchaseOrder.company_id == company_id)
        deleted["purchase_order_items"] = (
            db.query(PurchaseOrderItem)
            .filter(PurchaseOrderItem.purchase_order_id.in_(po_ids))
            .delete(synchronize_session=False)
        )

        sup_ids = db.query(Supplier.id).filter(Supplier.company_id == company_id)
        deleted["supplier_products"] = (
            db.query(SupplierProduct)
            .filter(SupplierProduct.supplier_id.in_(sup_ids))
            .delete(synchronize_session=False)
        )

    # 2) Tabelas com company_id direto.
    for group_key in groups:
        for table_name, model in _GROUPS[group_key]["models"]:
            deleted[table_name] = (
                db.query(model)
                .filter(model.company_id == company_id)
                .delete(synchronize_session=False)
            )

    db.commit()
    return deleted
