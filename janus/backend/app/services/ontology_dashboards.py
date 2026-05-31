"""
ontology_dashboards.py - versao v2 dos dashboards que LE produtos via a ontologia.

Mostra o pattern de migracao de service: em vez de SQL direto sobre models,
passa pelo runtime ontologico — ganhando markings, computed properties e
auditoria automatica sem reescrever logica.

Comparativo com a versao legada em app.dashboards:
  - Antes: db.query(Product).filter(company_id=...)
  - Depois: runtime.list_objects("Produto", user=ctx, filters=...)

Ganhos:
  + filtro TenantScoped aplicado automaticamente pelo runtime
  + columns sensiveis (standard_cost, sale_price) podem ser ocultadas
    para usuarios sem grant ConfidencialComercial
  + computed properties (margem_unitaria, margem_percentual) ja' avaliadas
  + cada chamada vira metrica Prometheus
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ontology import runtime
from app.ontology.permissions import UserContext
from app.ontology.registry import registry as _default_registry


def get_cfo_margin_by_product_v2(
    db: Session,
    company_id: int,
    *,
    user: UserContext,
    registry=None,
) -> list[dict[str, Any]]:
    """
    Mesma semantica do dashboards.get_cfo_margin_by_product, mas a leitura de
    Produto passa pela ontologia (com markings + computed + audit metrics).

    A agregacao de vendas continua via SQL direto — em Sem8+ vamos generalizar
    aggregations no runtime tambem.

    Returns:
        Lista de {product, receita_liquida, custo_real, margem, margem_unitaria, margem_critica}.
        Ordenada por margem ascendente (piores primeiro).
    """
    from sqlalchemy import func

    from app.models import SalesOrder

    # 1) Produtos via ontologia: aplica TenantScoped + filter_columns automaticamente
    products_page = runtime.list_objects(
        "Produto",
        user=user,
        db=db,
        registry=registry or _default_registry,
        filters={"company_id": company_id},
        limit=1000,
    )

    out: list[dict[str, Any]] = []
    for prod in products_page["items"]:
        # Se as keys de preco foram suprimidas por marking, o user nao deve
        # ver custo/margem — devolve campos como None.
        standard_cost = prod.get("standard_cost")

        # Agregacao de vendas (continua SQL — porque ainda nao temos aggregation API)
        agg = (
            db.query(
                func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita_liquida"),
                func.count(SalesOrder.id).label("qtd_vendas"),
            )
            .filter(SalesOrder.product_id == prod["id"])
            .first()
        )
        receita = float((agg.receita_liquida if agg else 0) or 0)
        qtd = int((agg.qtd_vendas if agg else 0) or 0)

        custo_real = float(standard_cost or 0) * qtd if standard_cost is not None else None
        margem = (receita - custo_real) if custo_real is not None else None

        out.append(
            {
                "product": prod.get("name"),
                "product_id": prod["id"],
                "receita_liquida": receita,
                "qtd_vendas": qtd,
                "custo_real": custo_real,
                "margem": margem,
                # Computed properties vindas da ontologia (filtradas por marking)
                "margem_unitaria": prod.get("margem_unitaria"),
                "margem_percentual": prod.get("margem_percentual"),
                "margem_critica": prod.get("margem_critica"),
            }
        )

    # Piores primeiro; None vai pro fim
    out.sort(key=lambda r: (r["margem"] is None, r["margem"] or 0))
    return out


def get_ceo_kpis_v2(
    db: Session,
    company_id: int,
    *,
    user: UserContext,
    registry=None,
) -> dict[str, Any]:
    """
    CEO KPIs (receita_total, receita_liquida, score_juno) — leitura via ontologia.

    Versao v2 do app.dashboards.get_ceo_kpis. Aplica TenantScoped + filter_columns
    automaticamente. Receita/lucro continuam vindo de agregacao SQL — esses nao
    estao expostos como Object Type ainda.
    """
    from sqlalchemy import func

    from app.models import SalesOrder

    reg = registry or _default_registry

    # 1) Garante que o user tem acesso ao tipo Empresa (1 query ontologica)
    try:
        emp = runtime.fetch_by_id(
            "Empresa",
            company_id,
            user=user,
            db=db,
            registry=reg,
        )
    except (runtime.ObjectNotFound, KeyError):
        # TenantScoped bloqueou ou Empresa nao existe
        return {"receita_total": 0.0, "receita_liquida": 0.0, "score_juno": 0}

    # 2) Agregacao SQL (vai migrar pra runtime aggregation em Sem9+)
    agg = (
        db.query(
            func.sum(SalesOrder.revenue).label("receita_total"),
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita_liquida"),
        )
        .filter(SalesOrder.company_id == company_id)
        .first()
    )
    return {
        "company_name": emp.get("name"),
        "receita_total": float((agg.receita_total if agg else 0) or 0),
        "receita_liquida": float((agg.receita_liquida if agg else 0) or 0),
        "score_juno": 85,  # placeholder — service real preserva
    }


def get_coo_delayed_orders_v2(
    db: Session,
    company_id: int,
    *,
    user: UserContext,
    registry=None,
) -> list[dict[str, Any]]:
    """
    OrdensProducao atrasadas — usando o ObjectType OrdemProducao via ontologia.

    A computed property `atrasada` ja' encapsula a regra de atraso.
    Markings + TenantScoped aplicados automaticamente.
    """
    reg = registry or _default_registry

    page = runtime.list_objects(
        "OrdemProducao",
        user=user,
        db=db,
        registry=reg,
        filters={"company_id": company_id, "status__ne": "completed"},
        limit=500,
    )
    delayed = [o for o in page["items"] if o.get("atrasada")]
    # Ordena por atraso desc
    delayed.sort(key=lambda x: x.get("atraso_dias") or 0, reverse=True)
    return delayed
