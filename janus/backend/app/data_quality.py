from sqlalchemy import func
from sqlalchemy.orm import Session

from .financials import get_dre_flow_totals
from .models import ErpImportBatch, Product, ProductionOrder, SalesOrder

# ── Basic sanity check ────────────────────────────────────────────────────────


def validate_data(company_id: int, db: Session) -> dict:
    """Check basic data presence and compute base stats."""
    receita_pedidos = (
        db.query(func.sum(SalesOrder.revenue)).filter(SalesOrder.company_id == company_id).scalar()
    )

    qtd_orders = (
        db.query(func.count(SalesOrder.id)).filter(SalesOrder.company_id == company_id).scalar()
        or 0
    )

    qtd_products = (
        db.query(func.count(Product.id)).filter(Product.company_id == company_id).scalar() or 0
    )

    qtd_production = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .scalar()
        or 0
    )

    receita_pedidos_val = float(receita_pedidos or 0)
    dre_totals = get_dre_flow_totals(company_id, db)

    if dre_totals:
        receita_val = dre_totals["receita_liquida"]
        cmv_val = dre_totals["cmv"]
        despesa_val = dre_totals["despesas_operacionais"]
        financial_source = "dre"
        financial_scope = dre_totals["scope_label"]
    else:
        receita_val = receita_pedidos_val
        cmv_val = 0.0
        despesa_val = 0.0
        financial_source = "pedidos"
        financial_scope = None

    ok = receita_val > 0 and qtd_orders > 0

    return {
        "receita_total": receita_val,
        "cmv_total": cmv_val,
        "despesa_total": despesa_val,
        "receita_pedidos": receita_pedidos_val,
        "financial_source": financial_source,
        "financial_scope": financial_scope,
        "total_pedidos": qtd_orders,
        "total_produtos": qtd_products,
        "total_ordens_producao": qtd_production,
        "status": "ok" if ok else "erro",
        "mensagem": (
            "Dados básicos validados com sucesso."
            if ok
            else "Receita total zerada ou ausente — verificar dados importados."
        ),
    }


# ── Problem detection ─────────────────────────────────────────────────────────


def detect_data_issues(company_id: int, db: Session) -> list[dict]:
    """Return a list of specific data quality problems found."""
    issues: list[dict] = []

    # 1. Receita negativa
    neg_rev = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.revenue < 0,
        )
        .scalar()
        or 0
    )
    if neg_rev:
        issues.append(
            {
                "type": "negative_revenue",
                "severity": "Alto",
                "message": f"{neg_rev} pedido(s) com receita negativa detectado(s)",
                "count": neg_rev,
                "action": "Revisar pedidos com valor negativo — possível erro de lançamento no ERP.",
            }
        )

    dre_totals = get_dre_flow_totals(company_id, db)
    if dre_totals and dre_totals["receita_liquida"]:
        sales_revenue = float(
            db.query(func.sum(SalesOrder.revenue - SalesOrder.discount))
            .filter(SalesOrder.company_id == company_id)
            .scalar()
            or 0
        )
        dre_revenue = dre_totals["receita_liquida"]
        diff_pct = abs(sales_revenue - dre_revenue) / abs(dre_revenue) * 100
        if diff_pct > 5:
            issues.append(
                {
                    "type": "sales_dre_mismatch",
                    "severity": "Alto" if diff_pct > 15 else "Médio",
                    "message": (
                        f"Receita de pedidos (R$ {sales_revenue:,.2f}) diverge da DRE "
                        f"(R$ {dre_revenue:,.2f}) em {diff_pct:.1f}%"
                    ),
                    "count": 1,
                    "action": (
                        "Usar a DRE como referencia financeira e revisar importacoes duplicadas "
                        "de pedidos de venda."
                    ),
                }
            )

    # 2. Produtos sem custo padrão
    no_cost = (
        db.query(func.count(Product.id))
        .filter(
            Product.company_id == company_id,
            Product.standard_cost.is_(None),
        )
        .scalar()
        or 0
    )
    if no_cost:
        issues.append(
            {
                "type": "missing_cost",
                "severity": "Médio",
                "message": f"{no_cost} produto(s) sem custo padrão cadastrado",
                "count": no_cost,
                "action": "Cadastrar custo padrão para cálculo correto de margem e diagnóstico executivo.",
            }
        )

    # 3. Ordens com quantidade real >50 % acima do planejado
    inconsistent = (
        db.query(func.count(ProductionOrder.id))
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_qty > 0,
            ProductionOrder.actual_qty > ProductionOrder.planned_qty * 1.5,
        )
        .scalar()
        or 0
    )
    if inconsistent:
        issues.append(
            {
                "type": "inconsistent_orders",
                "severity": "Médio",
                "message": f"{inconsistent} ordem(ns) com quantidade real >50% acima do planejado",
                "count": inconsistent,
                "action": "Verificar lançamentos de quantidade nas ordens de produção.",
            }
        )

    # 4. Desvio de custo extremo (custo real > 2× planejado)
    extreme_cost = (
        db.query(func.count(ProductionOrder.id))
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_cost > 0,
            ProductionOrder.actual_cost > ProductionOrder.planned_cost * 2,
        )
        .scalar()
        or 0
    )
    if extreme_cost:
        issues.append(
            {
                "type": "extreme_cost_overrun",
                "severity": "Alto",
                "message": f"{extreme_cost} ordem(ns) com custo real mais que o dobro do planejado",
                "count": extreme_cost,
                "action": "Auditar custos de produção — desvio crítico que impacta o diagnóstico de margem.",
            }
        )

    # 5. Pedidos com faturamento zero
    zero_rev = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.revenue == 0,
        )
        .scalar()
        or 0
    )
    if zero_rev:
        issues.append(
            {
                "type": "zero_revenue",
                "severity": "Baixo",
                "message": f"{zero_rev} pedido(s) com faturamento zerado",
                "count": zero_rev,
                "action": "Revisar pedidos com receita zero — possível dado incompleto ou rascunho.",
            }
        )

    return issues


# ── Data Trust Score ──────────────────────────────────────────────────────────


def calculate_trust_score(company_id: int, db: Session) -> dict:
    """Return a 0–100 Data Trust Score with a deduction breakdown."""
    score = 100
    deductions: list[dict] = []

    qtd_orders = (
        db.query(func.count(SalesOrder.id)).filter(SalesOrder.company_id == company_id).scalar()
        or 0
    )

    qtd_products = (
        db.query(func.count(Product.id)).filter(Product.company_id == company_id).scalar() or 0
    )

    # No orders
    if qtd_orders == 0:
        score -= 30
        deductions.append({"reason": "Nenhum pedido de venda cadastrado", "deduction": 30})

    # No products
    if qtd_products == 0:
        score -= 20
        deductions.append({"reason": "Nenhum produto cadastrado", "deduction": 20})

    # Missing product costs (proportional, max -20)
    if qtd_products > 0:
        no_cost = (
            db.query(func.count(Product.id))
            .filter(
                Product.company_id == company_id,
                Product.standard_cost.is_(None),
            )
            .scalar()
            or 0
        )
        if no_cost:
            pct = no_cost / qtd_products
            ded = min(20, round(pct * 20))
            score -= ded
            deductions.append(
                {
                    "reason": f"Produtos sem custo: {no_cost} ({pct * 100:.0f}%)",
                    "deduction": ded,
                }
            )

    # Negative revenue
    neg_rev = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.revenue < 0,
        )
        .scalar()
        or 0
    )
    if neg_rev:
        score -= 20
        deductions.append({"reason": f"Receita negativa em {neg_rev} pedido(s)", "deduction": 20})

    # Inconsistent production quantities
    inconsistent = (
        db.query(func.count(ProductionOrder.id))
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_qty > 0,
            ProductionOrder.actual_qty > ProductionOrder.planned_qty * 1.5,
        )
        .scalar()
        or 0
    )
    if inconsistent:
        score -= 15
        deductions.append(
            {"reason": f"Ordens com qtd. inconsistente: {inconsistent}", "deduction": 15}
        )

    # Extreme cost overrun
    extreme_cost = (
        db.query(func.count(ProductionOrder.id))
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_cost > 0,
            ProductionOrder.actual_cost > ProductionOrder.planned_cost * 2,
        )
        .scalar()
        or 0
    )
    if extreme_cost:
        score -= 15
        deductions.append(
            {"reason": f"Desvio de custo extremo: {extreme_cost} ordens", "deduction": 15}
        )

    # Zero-revenue orders (only penalise if >10 % of all orders)
    if qtd_orders > 0:
        zero_rev = (
            db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.revenue == 0,
            )
            .scalar()
            or 0
        )
        if zero_rev / qtd_orders > 0.10:
            score -= 10
            deductions.append(
                {
                    "reason": f"Pedidos com receita zero: {zero_rev} (>{10}% do total)",
                    "deduction": 10,
                }
            )

    score = max(0, score)
    label = "Alta" if score >= 80 else "Média" if score >= 60 else "Baixa"

    return {"score": score, "label": label, "deductions": deductions}


# ── Data quality insights (same format as generate_insights) ──────────────────


def generate_data_quality_insights(company_id: int, db: Session) -> list[dict]:
    return [
        {
            "type": f"data_{i['type']}",
            "message": i["message"],
            "impact": i["severity"],
            "action": i["action"],
        }
        for i in detect_data_issues(company_id, db)
    ]


# ── Full validation report ────────────────────────────────────────────────────


def get_full_validation_report(company_id: int, db: Session) -> dict:
    validation = validate_data(company_id, db)
    trust = calculate_trust_score(company_id, db)
    issues = detect_data_issues(company_id, db)

    last = (
        db.query(ErpImportBatch)
        .filter(ErpImportBatch.company_id == company_id)
        .order_by(ErpImportBatch.created_at.desc())
        .first()
    )
    last_import = (
        {
            "data_type": last.data_type,
            "file_name": last.file_name,
            "rows_imported": last.rows_imported,
            "status": last.status,
            "created_at": last.created_at.isoformat() if last.created_at else None,
        }
        if last
        else None
    )

    return {
        "company_id": company_id,
        "validation": validation,
        "trust_score": trust,
        "issues": issues,
        "last_import": last_import,
        "total_issues": len(issues),
        "high_severity": sum(1 for i in issues if i["severity"] == "Alto"),
    }
