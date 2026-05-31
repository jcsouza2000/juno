"""Consolidated data quality and audit center services."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import data_quality
from app.core.datetime_utils import utcnow_naive
from app.financials import get_dre_flow_totals, get_statements
from app.models import (
    Customer,
    ERPImportBatch,
    EventLog,
    FinancialStatement,
    FinancialUploadBatch,
    Inventory,
    Product,
    ProductionOrder,
    SalesOrder,
    Supplier,
)


def get_data_quality_center(company_id: int, db: Session) -> dict[str, Any]:
    base = data_quality.get_full_validation_report(company_id, db)
    coverage = _coverage(company_id, db)
    domain_validations = _domain_validations(company_id, db)
    reconciliation = _reconciliation(company_id, db)
    event_summary = _event_summary(company_id, db)
    pending_actions = _pending_actions(base, coverage, domain_validations, reconciliation)
    readiness = _executive_readiness(base, coverage, pending_actions)

    return {
        **base,
        "coverage": coverage,
        "domain_validations": domain_validations,
        "reconciliation": reconciliation,
        "event_summary": event_summary,
        "pending_actions": pending_actions,
        "executive_readiness": readiness,
        "exports": [
            {
                "label": "PDF de Auditoria",
                "format": "pdf",
                "available": True,
                "endpoint": f"/audit/data-quality/{company_id}?format=pdf",
                "description": "Relatorio executivo de confianca e pendencias.",
            },
            {
                "label": "Pendencias CSV",
                "format": "csv",
                "available": True,
                "endpoint": f"/audit/data-quality/{company_id}/pending.csv",
                "description": "Lista de problemas e acoes recomendadas.",
            },
            {
                "label": "Evidencias JSON",
                "format": "json",
                "available": True,
                "endpoint": f"/audit/data-quality/{company_id}",
                "description": "Payload completo para integracao ou arquivo tecnico.",
            },
        ],
    }


def get_events(
    company_id: int,
    db: Session,
    *,
    event_type: str | None = None,
    days: int | None = None,
    limit: int = 50,
    count_only: bool = False,
) -> dict[str, int] | list[dict[str, Any]]:
    query = db.query(EventLog).filter(EventLog.company_id == company_id)
    if event_type:
        query = query.filter(EventLog.event_type == event_type)
    if days:
        query = query.filter(EventLog.created_at >= utcnow_naive() - timedelta(days=days))

    if count_only:
        return {"count": int(query.count())}

    rows = query.order_by(EventLog.created_at.desc()).limit(limit).all()
    return [_event_to_dict(row) for row in rows]


def _coverage(company_id: int, db: Session) -> dict[str, Any]:
    product_count = _count(db, Product, company_id)
    customer_count = _count(db, Customer, company_id)
    sales_count = _count(db, SalesOrder, company_id)
    production_count = _count(db, ProductionOrder, company_id)
    inventory_count = _count(db, Inventory, company_id)
    supplier_count = _count(db, Supplier, company_id)
    statements = get_statements(company_id, db)
    erp_uploads = _count(db, ERPImportBatch, company_id)
    fin_uploads = _count(db, FinancialUploadBatch, company_id)

    sources = [
        _source("Produtos", product_count > 0, product_count, "Integracoes ERP > Produtos"),
        _source("Clientes", customer_count > 0, customer_count, "Integracoes ERP > Clientes"),
        _source("Pedidos", sales_count > 0, sales_count, "Integracoes ERP > Pedidos de Venda"),
        _source(
            "Ordens de Producao",
            production_count > 0,
            production_count,
            "Integracoes ERP > Ordens de Producao",
        ),
        _source("Estoque", inventory_count > 0, inventory_count, "Integracoes ERP > Estoque"),
        _source(
            "Fornecedores", supplier_count > 0, supplier_count, "Integracoes ERP > Fornecedores"
        ),
        _source("DRE", bool(statements.get("DRE")), None, "Demonstracoes > DRE"),
        _source("Balanco", bool(statements.get("BALANCO")), None, "Demonstracoes > Balanco"),
        _source("DFC", bool(statements.get("DFC")), None, "Demonstracoes > DFC"),
        _source("Historico ERP", erp_uploads > 0, erp_uploads, "Integracoes ERP"),
        _source("Historico Financeiro", fin_uploads > 0, fin_uploads, "Demonstracoes"),
    ]
    loaded = sum(1 for s in sources if s["loaded"])
    pct = round(loaded / len(sources) * 100, 2)
    return {
        "score": pct,
        "loaded": loaded,
        "total": len(sources),
        "sources": sources,
        "missing": [s["name"] for s in sources if not s["loaded"]],
    }


def _domain_validations(company_id: int, db: Session) -> list[dict[str, Any]]:
    product_total = _count(db, Product, company_id)
    product_no_cost = _scalar(
        db.query(func.count(Product.id)).filter(
            Product.company_id == company_id,
            (Product.standard_cost.is_(None)) | (Product.standard_cost == 0),
        )
    )
    product_no_price = _scalar(
        db.query(func.count(Product.id)).filter(
            Product.company_id == company_id,
            (Product.sale_price.is_(None)) | (Product.sale_price == 0),
        )
    )

    sales_total = _count(db, SalesOrder, company_id)
    sales_no_customer = _scalar(
        db.query(func.count(SalesOrder.id)).filter(
            SalesOrder.company_id == company_id, SalesOrder.customer_id.is_(None)
        )
    )
    sales_no_product = _scalar(
        db.query(func.count(SalesOrder.id)).filter(
            SalesOrder.company_id == company_id, SalesOrder.product_id.is_(None)
        )
    )
    sales_negative = _scalar(
        db.query(func.count(SalesOrder.id)).filter(
            SalesOrder.company_id == company_id, SalesOrder.revenue < 0
        )
    )
    sales_zero = _scalar(
        db.query(func.count(SalesOrder.id)).filter(
            SalesOrder.company_id == company_id, SalesOrder.revenue == 0
        )
    )

    op_total = _count(db, ProductionOrder, company_id)
    op_no_product = _scalar(
        db.query(func.count(ProductionOrder.id)).filter(
            ProductionOrder.company_id == company_id, ProductionOrder.product_id.is_(None)
        )
    )
    op_qty_issue = _scalar(
        db.query(func.count(ProductionOrder.id)).filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_qty > 0,
            ProductionOrder.actual_qty > ProductionOrder.planned_qty * 1.5,
        )
    )
    op_cost_issue = _scalar(
        db.query(func.count(ProductionOrder.id)).filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_cost > 0,
            ProductionOrder.actual_cost > ProductionOrder.planned_cost * 2,
        )
    )

    inventory_total = _count(db, Inventory, company_id)
    inventory_negative = _scalar(
        db.query(func.count(Inventory.id)).filter(
            Inventory.company_id == company_id, Inventory.quantity_on_hand < 0
        )
    )
    inventory_reserved = _scalar(
        db.query(func.count(Inventory.id)).filter(
            Inventory.company_id == company_id,
            Inventory.quantity_reserved > Inventory.quantity_on_hand,
        )
    )

    supplier_total = _count(db, Supplier, company_id)
    supplier_no_lead = _scalar(
        db.query(func.count(Supplier.id)).filter(
            Supplier.company_id == company_id,
            (Supplier.lead_time_days.is_(None)) | (Supplier.lead_time_days == 0),
        )
    )

    financial_total = _count(db, FinancialStatement, company_id)
    statements = get_statements(company_id, db)

    return [
        _domain(
            "Produtos",
            product_total,
            [
                _check("Produtos sem custo", product_no_cost, "Medio", "Cadastrar custo padrao."),
                _check(
                    "Produtos sem preco", product_no_price, "Medio", "Cadastrar preco de venda."
                ),
            ],
        ),
        _domain(
            "Pedidos de Venda",
            sales_total,
            [
                _check(
                    "Pedidos sem cliente",
                    sales_no_customer,
                    "Alto",
                    "Corrigir cliente no ERP ou mapeamento.",
                ),
                _check(
                    "Pedidos sem produto",
                    sales_no_product,
                    "Alto",
                    "Corrigir produto no ERP ou mapeamento.",
                ),
                _check(
                    "Receita negativa",
                    sales_negative,
                    "Alto",
                    "Revisar notas, devolucoes ou sinal de valor.",
                ),
                _check(
                    "Receita zerada", sales_zero, "Baixo", "Remover rascunhos ou corrigir valores."
                ),
            ],
        ),
        _domain(
            "Ordens de Producao",
            op_total,
            [
                _check("OPs sem produto", op_no_product, "Alto", "Vincular produto correto."),
                _check(
                    "Quantidade real incoerente",
                    op_qty_issue,
                    "Medio",
                    "Auditar apontamentos de producao.",
                ),
                _check("Custo real extremo", op_cost_issue, "Alto", "Auditar custos de OP."),
            ],
        ),
        _domain(
            "Estoque",
            inventory_total,
            [
                _check(
                    "Estoque negativo", inventory_negative, "Alto", "Corrigir saldo de estoque."
                ),
                _check(
                    "Reservado maior que saldo", inventory_reserved, "Medio", "Revisar reservas."
                ),
            ],
        ),
        _domain(
            "Fornecedores",
            supplier_total,
            [
                _check(
                    "Fornecedor sem lead time",
                    supplier_no_lead,
                    "Baixo",
                    "Completar prazo de reposicao.",
                ),
            ],
        ),
        _domain(
            "Demonstracoes",
            financial_total,
            [
                _check("DRE ausente", 0 if statements.get("DRE") else 1, "Alto", "Carregar DRE."),
                _check(
                    "Balanco ausente",
                    0 if statements.get("BALANCO") else 1,
                    "Alto",
                    "Carregar Balanco.",
                ),
                _check("DFC ausente", 0 if statements.get("DFC") else 1, "Medio", "Carregar DFC."),
            ],
        ),
    ]


def _reconciliation(company_id: int, db: Session) -> list[dict[str, Any]]:
    sales_revenue = float(
        db.query(func.sum(SalesOrder.revenue - SalesOrder.discount))
        .filter(SalesOrder.company_id == company_id)
        .scalar()
        or 0
    )
    dre_totals = get_dre_flow_totals(company_id, db)
    dre_revenue = dre_totals["receita_liquida"] if dre_totals else None

    total_products = _count(db, Product, company_id)
    products_sold = _scalar(
        db.query(func.count(func.distinct(SalesOrder.product_id))).filter(
            SalesOrder.company_id == company_id, SalesOrder.product_id.isnot(None)
        )
    )
    op_products = _scalar(
        db.query(func.count(func.distinct(ProductionOrder.product_id))).filter(
            ProductionOrder.company_id == company_id, ProductionOrder.product_id.isnot(None)
        )
    )

    revenue_status = "missing"
    diff_pct = None
    if dre_revenue is not None and dre_revenue != 0:
        diff_pct = round((sales_revenue - dre_revenue) / abs(dre_revenue) * 100, 2)
        revenue_status = (
            "ok" if abs(diff_pct) <= 5 else "warning" if abs(diff_pct) <= 15 else "critical"
        )

    return [
        {
            "label": "Receita Pedidos x DRE",
            "status": revenue_status,
            "value": sales_revenue,
            "reference": dre_revenue,
            "difference_pct": diff_pct,
            "message": "Compara receita operacional importada com demonstracao financeira.",
        },
        {
            "label": "Produtos vendidos x cadastro",
            "status": "ok" if total_products and products_sold <= total_products else "missing",
            "value": products_sold,
            "reference": total_products,
            "difference_pct": None,
            "message": "Confere se pedidos usam produtos cadastrados.",
        },
        {
            "label": "OPs x cadastro de produtos",
            "status": "ok" if total_products and op_products <= total_products else "missing",
            "value": op_products,
            "reference": total_products,
            "difference_pct": None,
            "message": "Confere se ordens de producao estao ligadas a produtos.",
        },
    ]


def _event_summary(company_id: int, db: Session) -> dict[str, Any]:
    since7 = utcnow_naive() - timedelta(days=7)
    since30 = utcnow_naive() - timedelta(days=30)
    return {
        "total_7d": int(
            db.query(EventLog)
            .filter(EventLog.company_id == company_id, EventLog.created_at >= since7)
            .count()
        ),
        "total_30d": int(
            db.query(EventLog)
            .filter(EventLog.company_id == company_id, EventLog.created_at >= since30)
            .count()
        ),
        "erp_import_30d": int(
            db.query(EventLog)
            .filter(
                EventLog.company_id == company_id,
                EventLog.event_type == "erp_import",
                EventLog.created_at >= since30,
            )
            .count()
        ),
        "price_update_30d": int(
            db.query(EventLog)
            .filter(
                EventLog.company_id == company_id,
                EventLog.event_type == "price_update",
                EventLog.created_at >= since30,
            )
            .count()
        ),
    }


def _pending_actions(
    base: dict[str, Any],
    coverage: dict[str, Any],
    domains: list[dict[str, Any]],
    reconciliation: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for source in coverage["sources"]:
        if not source["loaded"]:
            actions.append(
                {
                    "priority": (
                        "Alta"
                        if source["name"] in {"Produtos", "Pedidos", "DRE", "Balanco"}
                        else "Media"
                    ),
                    "owner": _owner_for_source(source["name"]),
                    "action": f"Carregar fonte pendente: {source['name']}",
                    "status": "aberto",
                    "reason": source["action"],
                }
            )
    for domain in domains:
        for check in domain["checks"]:
            if check["status"] != "ok":
                actions.append(
                    {
                        "priority": "Alta" if check["severity"] == "Alto" else "Media",
                        "owner": _owner_for_source(domain["domain"]),
                        "action": check["action"],
                        "status": "aberto",
                        "reason": check["label"],
                    }
                )
    for item in reconciliation:
        if item["status"] in {"critical", "warning"}:
            actions.append(
                {
                    "priority": "Alta" if item["status"] == "critical" else "Media",
                    "owner": "CFO/Consultoria",
                    "action": f"Reconciliar: {item['label']}",
                    "status": "aberto",
                    "reason": item["message"],
                }
            )
    if base["trust_score"]["score"] < 80:
        actions.append(
            {
                "priority": "Alta",
                "owner": "Consultoria",
                "action": "Elevar Data Trust Score antes da apresentacao executiva.",
                "status": "aberto",
                "reason": f"Score atual {base['trust_score']['score']}/100.",
            }
        )
    return actions[:20]


def _executive_readiness(
    base: dict[str, Any], coverage: dict[str, Any], pending_actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    trust = int(base["trust_score"]["score"])
    coverage_score = float(coverage["score"])
    critical = any(a["priority"] == "Alta" for a in pending_actions)

    def readiness(audience: str, needs_financial: bool, needs_ops: bool) -> dict[str, Any]:
        missing = set(coverage["missing"])
        blockers = []
        if trust < 80:
            blockers.append("Data Trust abaixo de 80")
        if needs_financial and {"DRE", "Balanco"} & missing:
            blockers.append("Demonstracoes financeiras incompletas")
        if needs_ops and {"Produtos", "Pedidos", "Ordens de Producao"} & missing:
            blockers.append("Dados operacionais incompletos")
        if critical:
            blockers.append("Pendencias de alta prioridade abertas")
        ready = not blockers and coverage_score >= 70
        return {
            "audience": audience,
            "ready": ready,
            "status": "ready" if ready else "blocked",
            "message": "Pronto para apresentacao." if ready else "; ".join(blockers),
        }

    return [
        readiness("CEO", needs_financial=True, needs_ops=True),
        readiness("CFO", needs_financial=True, needs_ops=False),
        readiness("COO", needs_financial=False, needs_ops=True),
        readiness("Conselho", needs_financial=True, needs_ops=True),
    ]


def _event_to_dict(row: EventLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "event_type": row.event_type,
        "old_state": _decode_state(row.old_state),
        "new_state": _decode_state(row.new_state),
        "user_id": str(row.user_id) if row.user_id is not None else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _decode_state(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {"raw": str(value)}


def _source(name: str, loaded: bool, records: int | None, action: str) -> dict[str, Any]:
    return {
        "name": name,
        "loaded": loaded,
        "records": records,
        "status": "loaded" if loaded else "missing",
        "action": action,
    }


def _domain(domain: str, total_records: int, checks: list[dict[str, Any]]) -> dict[str, Any]:
    if total_records == 0:
        return {
            "domain": domain,
            "status": "missing",
            "total_records": total_records,
            "checks": checks,
        }
    statuses = {c["status"] for c in checks}
    status = "critical" if "critical" in statuses else "warning" if "warning" in statuses else "ok"
    return {"domain": domain, "status": status, "total_records": total_records, "checks": checks}


def _check(label: str, count: int, severity: str, action: str) -> dict[str, Any]:
    if count == 0:
        status = "ok"
    elif severity == "Alto":
        status = "critical"
    else:
        status = "warning"
    return {
        "label": label,
        "status": status,
        "severity": severity,
        "count": int(count),
        "message": "OK" if count == 0 else f"{count} ocorrencia(s)",
        "action": action,
    }


def _owner_for_source(source: str) -> str:
    if source in {"DRE", "Balanco", "DFC", "Demonstracoes"}:
        return "CFO"
    if source in {"Ordens de Producao", "Estoque", "Fornecedores"}:
        return "COO"
    if source in {"Historico ERP", "Produtos", "Clientes", "Pedidos"}:
        return "TI/Consultoria"
    return "Consultoria"


def _count(db: Session, model, company_id: int) -> int:
    return int(db.query(func.count(model.id)).filter(model.company_id == company_id).scalar() or 0)


def _scalar(query) -> int:
    return int(query.scalar() or 0)
