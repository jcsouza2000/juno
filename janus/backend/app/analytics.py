"""
Analises operacionais avancadas para o Coordinator (Fase 4).

Funcoes de negocio que respondem perguntas executivas recorrentes sobre os
dados reais do tenant — concentracao de clientes e curva ABC de produtos.
Todas escopadas por company_id e sem efeitos colaterais (somente leitura).
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Customer, Product, SalesOrder


def _abc_class(cumulative_pct: float) -> str:
    """Classe ABC pela receita acumulada: A<=80%, B<=95%, C o resto."""
    if cumulative_pct <= 80.0:
        return "A"
    if cumulative_pct <= 95.0:
        return "B"
    return "C"


def get_customer_concentration(db: Session, company_id: int, top_n: int = 10) -> dict:
    """
    Concentracao de receita por cliente (risco de dependencia comercial).

    Retorna os maiores clientes com receita, participacao (%) e classe ABC,
    alem de indicadores de concentracao (top 1 e top 5) para alerta de risco.
    """
    rows = (
        db.query(
            Customer.name,
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita"),
        )
        .join(SalesOrder, SalesOrder.customer_id == Customer.id)
        .filter(Customer.company_id == company_id)
        .group_by(Customer.id, Customer.name)
        .order_by(func.sum(SalesOrder.revenue - SalesOrder.discount).desc())
        .all()
    )

    ranked = [(name, float(receita or 0)) for name, receita in rows if (receita or 0) > 0]
    total = sum(r for _, r in ranked)
    if not ranked or total <= 0:
        return {
            "kind": "customer_concentration",
            "available": False,
            "total_customers": 0,
            "receita_total": 0.0,
            "clientes": [],
        }

    cumulative = 0.0
    clientes = []
    for name, receita in ranked:
        pct = receita / total * 100.0
        cumulative += pct
        clientes.append(
            {
                "cliente": name,
                "receita": round(receita, 2),
                "participacao_pct": round(pct, 2),
                "acumulado_pct": round(cumulative, 2),
                "classe_abc": _abc_class(cumulative),
            }
        )

    top1 = clientes[0]["participacao_pct"]
    top5 = round(sum(c["participacao_pct"] for c in clientes[:5]), 2)

    return {
        "kind": "customer_concentration",
        "available": True,
        "total_customers": len(clientes),
        "receita_total": round(total, 2),
        "top_1_pct": top1,
        "top_5_pct": top5,
        "risco_concentracao": top1 >= 30.0,
        "clientes": clientes[:top_n],
    }


def get_product_abc(db: Session, company_id: int, top_n: int = 20) -> dict:
    """
    Curva ABC de produtos por receita liquida.

    Classifica os produtos em A/B/C pela contribuicao acumulada na receita,
    util para priorizar mix, estoque e esforco comercial.
    """
    rows = (
        db.query(
            Product.name,
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita"),
            func.count(SalesOrder.id).label("qtd_vendas"),
        )
        .join(SalesOrder, SalesOrder.product_id == Product.id)
        .filter(Product.company_id == company_id)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(SalesOrder.revenue - SalesOrder.discount).desc())
        .all()
    )

    ranked = [
        (name, float(receita or 0), int(qtd or 0))
        for name, receita, qtd in rows
        if (receita or 0) > 0
    ]
    total = sum(r for _, r, _ in ranked)
    if not ranked or total <= 0:
        return {
            "kind": "product_abc",
            "available": False,
            "total_products": 0,
            "receita_total": 0.0,
            "resumo_classes": {},
            "produtos": [],
        }

    cumulative = 0.0
    produtos = []
    resumo: dict[str, dict[str, float]] = {
        "A": {"itens": 0, "receita": 0.0},
        "B": {"itens": 0, "receita": 0.0},
        "C": {"itens": 0, "receita": 0.0},
    }
    for name, receita, qtd in ranked:
        pct = receita / total * 100.0
        cumulative += pct
        classe = _abc_class(cumulative)
        produtos.append(
            {
                "produto": name,
                "receita": round(receita, 2),
                "qtd_vendas": qtd,
                "participacao_pct": round(pct, 2),
                "acumulado_pct": round(cumulative, 2),
                "classe_abc": classe,
            }
        )
        resumo[classe]["itens"] += 1
        resumo[classe]["receita"] = round(resumo[classe]["receita"] + receita, 2)

    return {
        "kind": "product_abc",
        "available": True,
        "total_products": len(produtos),
        "receita_total": round(total, 2),
        "resumo_classes": resumo,
        "produtos": produtos[:top_n],
    }
