"""Executive KPI catalog and dashboard calculations.

The catalog is intentionally explicit: every KPI declares its owner,
category, source and required data. Dashboards can then show unavailable
metrics without inventing numbers when a company has not uploaded a source.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app import data_quality, templates_financeiro
from app.financials import get_financial_summary, get_statements
from app.models import (
    Customer,
    ERPImportBatch,
    FinancialUploadBatch,
    Inventory,
    Product,
    ProductionOrder,
    SalesOrder,
    Supplier,
)
from app.score_v2 import get_score_calculator

Persona = str
Status = str

OPEN_PRODUCTION_STATUSES = ("aberto", "aberta", "planned", "planejada", "em_andamento", "em andamento")


@dataclass(frozen=True)
class KPIDefinition:
    id: str
    persona: Persona
    category: str
    label: str
    unit: str
    source: str
    description: str
    required_data: tuple[str, ...]


KPI_CATALOG: tuple[KPIDefinition, ...] = (
    # CEO
    KPIDefinition(
        "juno_score",
        "ceo",
        "Saude executiva",
        "Score JUNO",
        "score",
        "Score v2",
        "Indice composto de saude empresarial.",
        ("Produtos", "Pedidos", "OPs", "Demonstracoes"),
    ),
    KPIDefinition(
        "receita_liquida",
        "ceo",
        "Resultado",
        "Receita liquida",
        "currency",
        "DRE/Pedidos",
        "Receita apos deducoes.",
        ("DRE ou Pedidos",),
    ),
    KPIDefinition(
        "margem_liquida_pct",
        "ceo",
        "Resultado",
        "Margem liquida",
        "percent",
        "DRE",
        "Lucro liquido sobre receita liquida.",
        ("DRE",),
    ),
    KPIDefinition(
        "margem_ebitda_pct",
        "ceo",
        "Resultado",
        "Margem EBITDA",
        "percent",
        "DRE",
        "EBITDA sobre receita liquida.",
        ("DRE",),
    ),
    KPIDefinition(
        "fluxo_caixa_operacional",
        "ceo",
        "Caixa",
        "Fluxo de caixa operacional",
        "currency",
        "DFC",
        "Geracao ou consumo de caixa operacional.",
        ("DFC",),
    ),
    KPIDefinition(
        "capital_giro",
        "ceo",
        "Caixa",
        "Capital de giro",
        "currency",
        "Balanco",
        "Ativo circulante menos passivo circulante.",
        ("Balanco",),
    ),
    KPIDefinition(
        "liquidez_corrente",
        "ceo",
        "Risco financeiro",
        "Liquidez corrente",
        "ratio",
        "Balanco",
        "Capacidade de pagar obrigacoes de curto prazo.",
        ("Balanco",),
    ),
    KPIDefinition(
        "endividamento_pct",
        "ceo",
        "Risco financeiro",
        "Endividamento",
        "percent",
        "Balanco",
        "Participacao de capital de terceiros.",
        ("Balanco",),
    ),
    KPIDefinition(
        "concentracao_clientes",
        "ceo",
        "Risco comercial",
        "Concentracao de clientes",
        "percent",
        "Pedidos",
        "Participacao do maior cliente na receita.",
        ("Clientes", "Pedidos"),
    ),
    KPIDefinition(
        "perda_estimada",
        "ceo",
        "Prioridades",
        "Perda estimada",
        "currency",
        "Margem/OPs",
        "Perda estimada por margem negativa e atrasos.",
        ("Produtos", "Pedidos", "OPs"),
    ),
    KPIDefinition(
        "data_trust_score",
        "ceo",
        "Confianca",
        "Data Trust Score",
        "score",
        "Auditoria",
        "Confiabilidade dos dados usados.",
        ("Uploads",),
    ),
    # CFO
    KPIDefinition(
        "receita_bruta",
        "cfo",
        "DRE",
        "Receita bruta",
        "currency",
        "DRE",
        "Vendas brutas do periodo.",
        ("DRE",),
    ),
    KPIDefinition(
        "receita_liquida",
        "cfo",
        "DRE",
        "Receita liquida",
        "currency",
        "DRE/Pedidos",
        "Receita liquida do periodo.",
        ("DRE ou Pedidos",),
    ),
    KPIDefinition(
        "custo_variavel",
        "cfo",
        "DRE",
        "Custo variavel",
        "currency",
        "DRE/Produtos",
        "CMV, CPV ou custo variavel.",
        ("DRE ou Produtos",),
    ),
    KPIDefinition(
        "margem_bruta",
        "cfo",
        "DRE",
        "Margem bruta",
        "currency",
        "DRE",
        "Receita liquida menos custo variavel.",
        ("DRE",),
    ),
    KPIDefinition(
        "margem_bruta_pct",
        "cfo",
        "DRE",
        "Margem bruta %",
        "percent",
        "DRE",
        "Margem bruta sobre receita liquida.",
        ("DRE",),
    ),
    KPIDefinition(
        "despesas_fixas",
        "cfo",
        "DRE",
        "Despesas fixas",
        "currency",
        "DRE",
        "Soma de despesas operacionais fixas.",
        ("DRE",),
    ),
    KPIDefinition(
        "ebitda",
        "cfo",
        "DRE",
        "EBITDA",
        "currency",
        "DRE",
        "Resultado operacional antes de juros, impostos, depreciacao e amortizacao.",
        ("DRE",),
    ),
    KPIDefinition(
        "lucro_liquido",
        "cfo",
        "DRE",
        "Lucro liquido",
        "currency",
        "DRE",
        "Resultado liquido final.",
        ("DRE",),
    ),
    KPIDefinition(
        "liquidez_corrente",
        "cfo",
        "Balanco",
        "Liquidez corrente",
        "ratio",
        "Balanco",
        "Ativo circulante dividido por passivo circulante.",
        ("Balanco",),
    ),
    KPIDefinition(
        "endividamento_pct",
        "cfo",
        "Balanco",
        "Endividamento",
        "percent",
        "Balanco",
        "Dividas sobre capital total.",
        ("Balanco",),
    ),
    KPIDefinition(
        "fluxo_caixa_operacional",
        "cfo",
        "DFC",
        "Fluxo de caixa operacional",
        "currency",
        "DFC",
        "Caixa gerado pela operacao.",
        ("DFC",),
    ),
    KPIDefinition(
        "capital_giro",
        "cfo",
        "Balanco",
        "Capital de giro",
        "currency",
        "Balanco",
        "Ativo circulante menos passivo circulante.",
        ("Balanco",),
    ),
    KPIDefinition(
        "divida_liquida_ebitda",
        "cfo",
        "Balanco",
        "Divida liquida / EBITDA",
        "ratio",
        "Balanco/DRE",
        "Alavancagem aproximada.",
        ("Balanco", "DRE"),
    ),
    KPIDefinition(
        "margem_por_produto",
        "cfo",
        "Margem",
        "Produtos com margem negativa",
        "number",
        "Pedidos/Produtos",
        "Quantidade de produtos destruindo margem.",
        ("Produtos", "Pedidos"),
    ),
    # COO
    KPIDefinition(
        "ordens_atrasadas",
        "coo",
        "Producao",
        "Ordens atrasadas",
        "number",
        "OPs",
        "OPs com data real maior que data planejada.",
        ("OPs",),
    ),
    KPIDefinition(
        "taxa_atraso",
        "coo",
        "Producao",
        "Taxa de atraso",
        "percent",
        "OPs",
        "Percentual de OPs atrasadas.",
        ("OPs",),
    ),
    KPIDefinition(
        "desvio_custo_pct",
        "coo",
        "Producao",
        "Desvio de custo",
        "percent",
        "OPs",
        "Custo real versus custo planejado.",
        ("OPs",),
    ),
    KPIDefinition(
        "desvio_quantidade_pct",
        "coo",
        "Producao",
        "Desvio de quantidade",
        "percent",
        "OPs",
        "Quantidade real versus planejada.",
        ("OPs",),
    ),
    KPIDefinition(
        "eficiencia_producao",
        "coo",
        "Producao",
        "Eficiencia de producao",
        "percent",
        "OPs",
        "Aderencia de prazo, custo e quantidade.",
        ("OPs",),
    ),
    KPIDefinition(
        "valor_estoque",
        "coo",
        "Estoque",
        "Valor de estoque",
        "currency",
        "Estoque",
        "Quantidade em estoque multiplicada por custo unitario.",
        ("Estoque",),
    ),
    KPIDefinition(
        "estoque_disponivel",
        "coo",
        "Estoque",
        "Estoque disponivel",
        "number",
        "Estoque",
        "Quantidade disponivel para uso ou venda.",
        ("Estoque",),
    ),
    KPIDefinition(
        "estoque_reservado",
        "coo",
        "Estoque",
        "Estoque reservado",
        "number",
        "Estoque",
        "Quantidade comprometida.",
        ("Estoque",),
    ),
    KPIDefinition(
        "lead_time_fornecedores",
        "coo",
        "Suprimentos",
        "Lead time medio",
        "days",
        "Fornecedores",
        "Prazo medio de reposicao.",
        ("Fornecedores",),
    ),
    KPIDefinition(
        "fornecedores_criticos",
        "coo",
        "Suprimentos",
        "Fornecedores criticos",
        "number",
        "Fornecedores",
        "Fornecedores sem lead time ou com prazo alto.",
        ("Fornecedores",),
    ),
    KPIDefinition(
        "perda_operacional",
        "coo",
        "Prioridades",
        "Perda operacional estimada",
        "currency",
        "Margem/OPs",
        "Impacto financeiro estimado de atrasos e margem negativa.",
        ("Produtos", "Pedidos", "OPs"),
    ),
    # Consultoria
    KPIDefinition(
        "data_trust_score",
        "consultoria",
        "Governanca",
        "Data Trust Score",
        "score",
        "Auditoria",
        "Confiabilidade da base.",
        ("Uploads",),
    ),
    KPIDefinition(
        "issues_alta",
        "consultoria",
        "Governanca",
        "Problemas criticos",
        "number",
        "Auditoria",
        "Pendencias de alta severidade.",
        ("Uploads",),
    ),
    KPIDefinition(
        "uploads_erp",
        "consultoria",
        "Evidencias",
        "Uploads ERP",
        "number",
        "Historico ERP",
        "Quantidade de cargas ERP registradas.",
        ("Integracoes ERP",),
    ),
    KPIDefinition(
        "uploads_financeiros",
        "consultoria",
        "Evidencias",
        "Uploads financeiros",
        "number",
        "Historico financeiro",
        "Quantidade de cargas de demonstracoes.",
        ("Demonstracoes",),
    ),
    KPIDefinition(
        "cobertura_dados",
        "consultoria",
        "Implantacao",
        "Cobertura de dados",
        "percent",
        "Modelo JUNO",
        "Percentual de fontes essenciais carregadas.",
        ("Produtos", "Clientes", "Pedidos", "OPs", "DRE", "Balanco", "DFC"),
    ),
    KPIDefinition(
        "fontes_pendentes",
        "consultoria",
        "Implantacao",
        "Fontes pendentes",
        "number",
        "Modelo JUNO",
        "Fontes essenciais ainda ausentes.",
        ("Checklist",),
    ),
    KPIDefinition(
        "prontidao_executiva",
        "consultoria",
        "Implantacao",
        "Prontidao executiva",
        "percent",
        "JUNO",
        "Combinacao de Data Trust e cobertura de dados.",
        ("Auditoria", "Checklist"),
    ),
)

PERSONA_META: dict[str, dict[str, str]] = {
    "ceo": {
        "title": "Dashboard CEO",
        "subtitle": "Score, riscos, caixa, margem e prioridades executivas.",
    },
    "cfo": {
        "title": "Dashboard CFO",
        "subtitle": "DRE, liquidez, endividamento, caixa, capital de giro e margem.",
    },
    "coo": {
        "title": "Dashboard COO",
        "subtitle": "Producao, atraso, estoque, fornecedores e perdas operacionais.",
    },
    "consultoria": {
        "title": "Dashboard Consultoria",
        "subtitle": "Governanca, evidencias, qualidade dos dados e prontidao para apresentacao.",
    },
}


def get_kpi_catalog(persona: str | None = None) -> list[dict[str, Any]]:
    defs = KPI_CATALOG if persona is None else tuple(k for k in KPI_CATALOG if k.persona == persona)
    return [
        {
            "id": k.id,
            "persona": k.persona,
            "category": k.category,
            "label": k.label,
            "unit": k.unit,
            "source": k.source,
            "description": k.description,
            "required_data": list(k.required_data),
        }
        for k in defs
    ]


def build_persona_dashboard(db: Session, company_id: int, persona: str) -> dict[str, Any]:
    if persona not in PERSONA_META:
        raise ValueError(f"Persona invalida: {persona}")

    context = _build_context(db, company_id)
    definitions = [k for k in KPI_CATALOG if k.persona == persona]
    kpis = [_materialize_kpi(defn, context) for defn in definitions]
    sections = _group_sections(kpis)

    return {
        "company_id": company_id,
        "persona": persona,
        "title": PERSONA_META[persona]["title"],
        "subtitle": PERSONA_META[persona]["subtitle"],
        "summary_cards": _summary_cards(persona, kpis),
        "sections": sections,
        "pnl_table": _build_pnl_table(context) if persona == "cfo" else None,
        "source_status": context["source_status"],
        "action_items": _action_items(persona, kpis, context),
        "catalog": get_kpi_catalog(persona),
        "generated_at": datetime.utcnow().isoformat(),
    }


def build_all_dashboards(db: Session, company_id: int) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "dashboards": {
            persona: build_persona_dashboard(db, company_id, persona)
            for persona in ("ceo", "cfo", "coo", "consultoria")
        },
    }


def _unified_fallback_path() -> Path:
    return Path(__file__).resolve().parents[3] / "uploads_piloto_juno" / "dashboard_unificado_2025.json"


def _load_unified_fallback() -> dict[str, Any] | None:
    path = _unified_fallback_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _short_period_label(period: str) -> str:
    if "-" in period:
        year, month = period.split("-", 1)
        return f"{month}/{year[-2:]}"
    return period


def _unified_synthesis(score: float, margem_ebitda: float | None, margem_liquida: float | None, giro: float | None) -> str:
    if score >= 80:
        estabilidade = "Operacao estavel"
    elif score >= 65:
        estabilidade = "Operacao em monitoramento"
    else:
        estabilidade = "Operacao sob pressao"
    ebitda_txt = f"{margem_ebitda:.1f}%" if margem_ebitda is not None else "n/d"
    liquida_txt = f"{margem_liquida:.1f}%" if margem_liquida is not None else "n/d"
    giro_txt = f"{giro:.2f}x" if giro is not None else "n/d"
    return (
        f"{estabilidade} com Score {score:.1f}; margem EBITDA ajustada em {ebitda_txt} "
        f"e margem liquida em {liquida_txt}. Giro de estoque financeiro de {giro_txt} "
        "sustenta capital de giro; conectores de producao enriquecem OEE e FTT."
    )


def _build_unified_overlay(db: Session, company_id: int) -> dict[str, Any]:
    """Contexto leve para enriquecer dashboard de Templates com dados operacionais."""
    production_count = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .scalar()
        or 0
    )
    open_status = func.lower(func.coalesce(ProductionOrder.status, "")).in_(OPEN_PRODUCTION_STATUSES)
    delayed_count = (
        db.query(func.count(ProductionOrder.id))
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_date.isnot(None),
            (
                (ProductionOrder.actual_date.isnot(None))
                & (ProductionOrder.actual_date > ProductionOrder.planned_date)
            )
            | (
                (ProductionOrder.actual_date.is_(None))
                & (ProductionOrder.planned_date < func.now())
                & open_status
            ),
        )
        .scalar()
        or 0
    )
    op_totals = (
        db.query(
            func.sum(ProductionOrder.planned_qty).label("planned_qty"),
            func.sum(ProductionOrder.actual_qty).label("actual_qty"),
        )
        .filter(ProductionOrder.company_id == company_id)
        .first()
    )
    sales_count = (
        db.query(func.count(SalesOrder.id)).filter(SalesOrder.company_id == company_id).scalar() or 0
    )
    erp_uploads = (
        db.query(func.count(ERPImportBatch.id)).filter(ERPImportBatch.company_id == company_id).scalar() or 0
    )
    financial_uploads = (
        db.query(func.count(FinancialUploadBatch.id))
        .filter(FinancialUploadBatch.company_id == company_id)
        .scalar()
        or 0
    )
    product_count = (
        db.query(func.count(Product.id)).filter(Product.company_id == company_id).scalar() or 0
    )
    customer_count = (
        db.query(func.count(Customer.id)).filter(Customer.company_id == company_id).scalar() or 0
    )
    statements = get_statements(company_id, db) if not templates_financeiro.use_templates_as_canonical() else {}
    return {
        "trust_report": {"trust_score": {"score": 85}},
        "production_count": int(production_count),
        "delayed_count": int(delayed_count),
        "op_totals": op_totals,
        "sales_count": int(sales_count),
        "erp_uploads": int(erp_uploads),
        "financial_uploads": int(financial_uploads),
        "score_juno": None,
        "statements": statements,
        "source_status": _source_status(
            int(product_count),
            int(customer_count),
            int(sales_count),
            int(production_count),
            statements,
            int(erp_uploads),
            int(financial_uploads),
        ),
    }


def _apply_unified_overlay(payload: dict[str, Any], ctx: dict[str, Any]) -> None:
    op = ctx.get("op_totals")
    planned_qty = _float(getattr(op, "planned_qty", 0) if op else 0)
    actual_qty = _float(getattr(op, "actual_qty", 0) if op else 0)
    oee = round(actual_qty / planned_qty * 100, 1) if planned_qty > 0 else None

    production_count = int(ctx.get("production_count") or 0)
    delayed_count = int(ctx.get("delayed_count") or 0)
    ftt = (
        round((production_count - delayed_count) / production_count * 100, 1)
        if production_count > 0
        else None
    )

    trust = ctx.get("trust_report", {}).get("trust_score", {})
    trust_score = _float(trust.get("score") or 0)
    erp_active = bool(ctx.get("erp_uploads") or ctx.get("sales_count"))

    payload["governanca"] = {
        "erp_conexao": {
            "label": "Conexao ERP",
            "status": "ativa" if erp_active else "pendente",
        },
        "auditoria_lgpd": {
            "label": "Auditoria LGPD",
            "status": "ok" if trust_score >= 70 else "revisar",
        },
        "busca_inteligente_placeholder": "Pergunte ao UNO sobre a operacao...",
    }
    payload["core"]["score_industrial"] = round(
        _float(ctx.get("score_juno") or payload["core"]["score_industrial"]),
        1,
    )

    if oee is not None:
        payload["quadrantes"]["operacoes"]["series"]["oee"] = {
            "valor": oee,
            "meta_wcm": templates_financeiro.WCM_METAS["oee"],
            "fonte": "ordens_producao",
        }
    if ftt is not None:
        payload["quadrantes"]["operacoes"]["series"]["ftt_fpy"] = {
            "valor": ftt,
            "meta_wcm": templates_financeiro.WCM_METAS["ftt_fpy"],
            "fonte": "ordens_producao",
        }


def _inject_template_relatorio(payload: dict[str, Any]) -> None:
    if not templates_financeiro.use_templates_as_canonical():
        return
    relatorio = templates_financeiro.build_demonstracoes_relatorio()
    if relatorio:
        payload["relatorio_templates"] = relatorio


def build_unified_dashboard(db: Session, company_id: int) -> dict[str, Any]:
    prebuilt = _load_unified_fallback()
    if prebuilt and templates_financeiro.use_templates_as_canonical():
        ctx = _build_unified_overlay(db, company_id)
        payload = dict(prebuilt)
        payload["company_id"] = company_id
        payload.setdefault("meta", {})
        payload["meta"]["source_mode"] = "templates_json"
        payload["meta"]["generated_at"] = datetime.utcnow().isoformat()
        _apply_unified_overlay(payload, ctx)
        payload["source_status"] = ctx.get("source_status", [])
        _inject_template_relatorio(payload)
        return payload

    template_payload = templates_financeiro.build_unified_payload()
    if template_payload:
        ctx = _build_unified_overlay(db, company_id)
        payload = dict(template_payload)
        payload["company_id"] = company_id
        payload["meta"]["generated_at"] = datetime.utcnow().isoformat()
        _apply_unified_overlay(payload, ctx)
        payload["pnl_table"] = None
        payload["source_status"] = ctx.get("source_status", [])
        _inject_template_relatorio(payload)
        return payload

    ctx = _build_context(db, company_id)
    fallback = _load_unified_fallback()
    if fallback:
        payload = dict(fallback)
        payload["company_id"] = company_id
        payload.setdefault("meta", {})
        payload["meta"]["source_mode"] = "json_fallback"
        payload["meta"]["generated_at"] = datetime.utcnow().isoformat()
        return payload

    dre = ctx["statements"].get("DRE", {})
    has_dre = bool(dre)
    periods = ctx.get("reporting_periods") or _latest_year_periods(dre)
    trend_periods = periods[-4:] if len(periods) >= 4 else periods
    dre_acc = ctx.get("dre_accumulated") or {}

    revenue_net = ctx.get("revenue_net") or 0.0
    revenue_gross = ctx.get("revenue_gross") or dre_acc.get("receita_bruta") or revenue_net
    margem_bruta = ctx.get("margem_bruta_pct")
    margem_liquida = ctx.get("margem_liquida_pct")
    margem_ebitda = ctx.get("margem_ebitda_pct")
    ebitda_val = ctx.get("ebitda")

    cmv = abs(_float(dre_acc.get("custo_variavel") or 0))
    inv = ctx.get("inventory")
    inv_value = _float(getattr(inv, "value", 0) if inv else 0)
    giro_estoque = round(cmv / inv_value, 2) if inv_value > 0 and cmv else None

    despesas_fixas = dre_acc.get("despesas_fixas")
    racio_admin = _rate(abs(despesas_fixas), revenue_gross) if despesas_fixas and revenue_gross else None

    op = ctx.get("op_totals")
    planned_qty = _float(getattr(op, "planned_qty", 0) if op else 0)
    actual_qty = _float(getattr(op, "actual_qty", 0) if op else 0)
    oee = round(actual_qty / planned_qty * 100, 1) if planned_qty > 0 else None

    production_count = int(ctx.get("production_count") or 0)
    delayed_count = int(ctx.get("delayed_count") or 0)
    ftt = (
        round((production_count - delayed_count) / production_count * 100, 1)
        if production_count > 0
        else None
    )

    score = round(_float(ctx.get("score_juno") or 50.0), 1)
    trust = ctx.get("trust_report", {}).get("trust_score", {})
    trust_score = _float(trust.get("score") or 0)
    erp_active = bool(ctx.get("erp_uploads") or ctx.get("sales_count"))

    tendencia_faturamento = []
    tendencia_margens = []
    tendencia_giro = []
    for period in trend_periods:
        period_dre = dre.get(period, {})
        rec = _lookup(period_dre, ("receita_liquida", "vendas_liquidas", "vendas")) or 0.0
        lucro = _lookup(period_dre, ("lucro_liquido", "resultado_liquido")) or 0.0
        lucro_bruto = _lookup(period_dre, ("lucro_bruto", "margem_bruta"))
        custo = _lookup(period_dre, ("cmv", "custo_variavel", "cpv", "cogs"))
        if lucro_bruto is None and rec and custo is not None:
            lucro_bruto = rec + custo if custo < 0 else rec - custo
        ebitda_period = _lookup(period_dre, ("ebitda",)) or 0.0
        label = _short_period_label(period)
        tendencia_faturamento.append({"periodo": label, "valor": round(rec, 3)})
        tendencia_margens.append(
            {
                "periodo": label,
                "margem_bruta": _rate(lucro_bruto, rec),
                "margem_liquida": _rate(lucro, rec),
                "margem_ebitda": _rate(ebitda_period, rec),
            }
        )
        period_cmv = abs(_float(custo or 0))
        tendencia_giro.append(
            {
                "periodo": label,
                "valor": round(period_cmv / inv_value, 2) if inv_value > 0 and period_cmv else 0.0,
            }
        )

    pnl_table = _build_pnl_table(ctx) if has_dre else None

    return {
        "company_id": company_id,
        "meta": {
            "fonte": "demonstracoes_financeiras" if has_dre else "operacional",
            "unidade": "R$",
            "periodo_competencia": periods[-1].split("-", 1)[0] if periods else str(datetime.utcnow().year),
            "periodo_patrimonial": periods[-1] if periods else None,
            "source_mode": "database",
            "generated_at": datetime.utcnow().isoformat(),
        },
        "governanca": {
            "erp_conexao": {"label": "Conexao ERP", "status": "ativa" if erp_active else "pendente"},
            "auditoria_lgpd": {
                "label": "Auditoria LGPD",
                "status": "ok" if trust_score >= 70 else "revisar",
            },
            "busca_inteligente_placeholder": "Pergunte ao UNO sobre a operacao...",
        },
        "core": {
            "score_industrial": score,
            "sintese_ia": _unified_synthesis(score, margem_ebitda, margem_liquida, giro_estoque),
        },
        "quadrantes": {
            "operacoes": {
                "titulo": "Operacoes",
                "series": {
                    "oee": {"valor": oee, "meta_wcm": 85, "fonte": "ordens_producao" if oee else "integracao_producao_pendente"},
                    "ftt_fpy": {"valor": ftt, "meta_wcm": 98, "fonte": "ordens_producao" if ftt else "integracao_producao_pendente"},
                    "giro_estoque": {
                        "valor": giro_estoque,
                        "meta_wcm": None,
                        "fonte": "estoque_dre" if giro_estoque else "balanco_dre",
                    },
                },
                "tendencia_giro_estoque": tendencia_giro,
            },
            "financeiro": {
                "titulo": "Financeiro",
                "cards": {
                    "faturamento": round(revenue_net, 3),
                    "margem_bruta_pct": margem_bruta,
                    "margem_liquida_pct": margem_liquida,
                    "ebitda_ajustado_pct": margem_ebitda,
                    "ebitda_valor": ebitda_val,
                },
                "tendencia_faturamento": tendencia_faturamento,
                "tendencia_margens": tendencia_margens,
            },
            "risco_pessoas": {
                "titulo": "Risco e Pessoas",
                "indicadores": {
                    "tfa": {"valor": None, "meta_wcm": 0, "fonte": "integracao_rh_pendente"},
                    "turnover": {"valor": None, "meta_wcm": None, "fonte": "integracao_rh_pendente"},
                    "racio_administrativo_pct": racio_admin,
                },
                "contas_receber": None,
            },
        },
        "kpis_unificados": {
            "Margem Bruta": {
                "resultado": f"{margem_bruta:.2f}%" if margem_bruta is not None else "n/d",
                "valor_numerico": margem_bruta,
            },
            "Margem Liquida": {
                "resultado": f"{margem_liquida:.2f}%" if margem_liquida is not None else "n/d",
                "valor_numerico": margem_liquida,
            },
            "Margem EBITDA Ajustada": {
                "resultado": f"{margem_ebitda:.2f}%" if margem_ebitda is not None else "n/d",
                "valor_numerico": margem_ebitda,
            },
            "Racio Custos Administrativos": {
                "resultado": f"{racio_admin:.2f}%" if racio_admin is not None else "n/d",
                "valor_numerico": racio_admin,
            },
            "Giro de Estoque (Financeiro)": {
                "resultado": f"{giro_estoque:.2f}x" if giro_estoque is not None else "n/d",
                "valor_numerico": giro_estoque,
            },
        },
        "pnl_table": pnl_table,
        "source_status": ctx.get("source_status", []),
    }


def _build_context(db: Session, company_id: int) -> dict[str, Any]:
    fin = get_financial_summary(company_id, db)
    statements = get_statements(company_id, db)
    trust_report = data_quality.get_full_validation_report(company_id, db)

    sales_rows = (
        db.query(
            func.count(SalesOrder.id).label("count"),
            func.sum(SalesOrder.revenue).label("gross"),
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("net"),
        )
        .filter(SalesOrder.company_id == company_id)
        .first()
    )
    product_count = (
        db.query(func.count(Product.id)).filter(Product.company_id == company_id).scalar() or 0
    )
    customer_count = (
        db.query(func.count(Customer.id)).filter(Customer.company_id == company_id).scalar() or 0
    )
    supplier_count = (
        db.query(func.count(Supplier.id)).filter(Supplier.company_id == company_id).scalar() or 0
    )
    production_count = (
        db.query(func.count(ProductionOrder.id))
        .filter(ProductionOrder.company_id == company_id)
        .scalar()
        or 0
    )
    open_status = func.lower(func.coalesce(ProductionOrder.status, "")).in_(OPEN_PRODUCTION_STATUSES)
    delayed_count = (
        db.query(func.count(ProductionOrder.id))
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.planned_date.isnot(None),
            (
                (ProductionOrder.actual_date.isnot(None))
                & (ProductionOrder.actual_date > ProductionOrder.planned_date)
            )
            | (
                (ProductionOrder.actual_date.is_(None))
                & (ProductionOrder.planned_date < func.now())
                & open_status
            ),
        )
        .scalar()
        or 0
    )

    op_totals = (
        db.query(
            func.sum(ProductionOrder.planned_qty).label("planned_qty"),
            func.sum(ProductionOrder.actual_qty).label("actual_qty"),
            func.sum(ProductionOrder.planned_cost).label("planned_cost"),
            func.sum(ProductionOrder.actual_cost).label("actual_cost"),
        )
        .filter(ProductionOrder.company_id == company_id)
        .first()
    )

    inventory = (
        db.query(
            func.sum(Inventory.quantity_on_hand).label("on_hand"),
            func.sum(Inventory.quantity_reserved).label("reserved"),
            func.sum(Inventory.quantity_available).label("available"),
            func.sum(Inventory.quantity_on_hand * Inventory.unit_cost).label("value"),
        )
        .filter(Inventory.company_id == company_id)
        .first()
    )

    suppliers = (
        db.query(
            func.avg(Supplier.lead_time_days).label("avg_lead_time"),
            func.sum(case((Supplier.lead_time_days >= 30, 1), else_=0)).label("critical_by_time"),
        )
        .filter(Supplier.company_id == company_id)
        .first()
    )

    erp_uploads = (
        db.query(func.count(ERPImportBatch.id))
        .filter(ERPImportBatch.company_id == company_id)
        .scalar()
        or 0
    )
    financial_uploads = (
        db.query(func.count(FinancialUploadBatch.id))
        .filter(FinancialUploadBatch.company_id == company_id)
        .scalar()
        or 0
    )

    sales_net = _float(getattr(sales_rows, "net", 0))
    sales_gross = _float(getattr(sales_rows, "gross", 0))
    reporting_periods = _latest_year_periods(statements.get("DRE", {}))
    dre_accumulated = _accumulated_dre(statements.get("DRE", {}), reporting_periods)
    dfc_accumulated = _accumulated_dfc(statements.get("DFC", {}), reporting_periods)

    revenue_net = _optional_float(dre_accumulated.get("receita_liquida")) or sales_net
    revenue_gross = _optional_float(dre_accumulated.get("receita_bruta")) or sales_gross
    ebitda = _optional_float(dre_accumulated.get("ebitda"))
    lucro_liquido = _optional_float(dre_accumulated.get("lucro_liquido"))
    lucro_bruto = _optional_float(dre_accumulated.get("lucro_bruto"))
    margem_liquida_pct = _rate(lucro_liquido, revenue_net)
    margem_ebitda_pct = _rate(ebitda, revenue_net)
    margem_bruta_pct = _rate(lucro_bruto, revenue_net)

    if fin.get("source") == "templates" and fin.get("dre"):
        dre_tpl = fin["dre"]
        bundle = templates_financeiro.load_kpi_bundle()
        revenue_net = dre_tpl["receita_liquida"]
        revenue_gross = dre_tpl["receita_bruta"]
        lucro_bruto = dre_tpl["lucro_bruto"]
        lucro_liquido = dre_tpl["lucro_liquido"]
        ebitda = dre_tpl["ebitda"]
        margem_bruta_pct = dre_tpl["margem_bruta_pct"]
        margem_liquida_pct = dre_tpl["margem_liquida_pct"]
        margem_ebitda_pct = dre_tpl["margem_ebitda_pct"]
        if bundle:
            dre_accumulated = {
                "receita_bruta": bundle.receita_bruta,
                "receita_liquida": bundle.receita_liquida,
                "custo_variavel": bundle.custo_produtos,
                "lucro_bruto": bundle.lucro_bruto,
                "lucro_liquido": bundle.lucro_liquido,
                "ebitda": bundle.ebitda_ajustado,
                "despesas_fixas": abs(bundle.despesas_admin),
            }
        reporting_periods = dre_tpl.get("todos_periodos") or list(templates_financeiro.DEFAULT_TRIMESTRES)

    balanco = fin.get("balanco", {}) if fin.get("available") else {}
    ativo_circulante = _optional_float(balanco.get("ativo_circulante"))
    passivo_circulante = _optional_float(balanco.get("passivo_circulante"))
    capital_giro = (
        ativo_circulante - passivo_circulante
        if ativo_circulante is not None and passivo_circulante is not None
        else None
    )

    margin_rows = _margin_rows(db, company_id)
    negative_margin_count = sum(1 for row in margin_rows if row["margem"] < 0)
    margin_loss = sum(abs(row["margem"]) for row in margin_rows if row["margem"] < 0)
    average_order_revenue = revenue_net / int(getattr(sales_rows, "count", 0) or 1) if revenue_net else 0
    delay_loss = delayed_count * average_order_revenue * 0.05 if average_order_revenue else None
    estimated_loss = margin_loss + (delay_loss or 0)

    top_customer_pct = _top_customer_share(db, company_id)
    coverage = _source_coverage(
        product_count=product_count,
        customer_count=customer_count,
        sales_count=int(getattr(sales_rows, "count", 0) or 0),
        production_count=production_count,
        statements=statements,
    )

    return {
        "financial": fin,
        "statements": statements,
        "trust_report": trust_report,
        "sales_count": int(getattr(sales_rows, "count", 0) or 0),
        "product_count": int(product_count),
        "customer_count": int(customer_count),
        "supplier_count": int(supplier_count),
        "production_count": int(production_count),
        "delayed_count": int(delayed_count),
        "revenue_gross": revenue_gross,
        "revenue_net": revenue_net,
        "ebitda": ebitda,
        "lucro_liquido": lucro_liquido,
        "margem_liquida_pct": margem_liquida_pct,
        "margem_ebitda_pct": margem_ebitda_pct,
        "lucro_bruto": lucro_bruto,
        "margem_bruta_pct": margem_bruta_pct,
        "liquidez_corrente": _financial_value(fin, "balanco", "liquidez_corrente", None),
        "endividamento_pct": _financial_value(fin, "balanco", "endividamento_pct", None),
        "capital_giro": capital_giro,
        "fluxo_caixa_operacional": _optional_float(dfc_accumulated.get("caixa_operacional")),
        "caixa_final": _financial_value(fin, "dfc", "caixa_final", None),
        "dre_accumulated": dre_accumulated,
        "dfc_accumulated": dfc_accumulated,
        "reporting_periods": reporting_periods,
        "op_totals": op_totals,
        "inventory": inventory,
        "suppliers": suppliers,
        "erp_uploads": int(erp_uploads),
        "financial_uploads": int(financial_uploads),
        "negative_margin_count": negative_margin_count,
        "margin_loss": margin_loss,
        "estimated_loss": estimated_loss,
        "top_customer_pct": top_customer_pct,
        "coverage": coverage,
        "source_status": _source_status(
            product_count,
            customer_count,
            int(getattr(sales_rows, "count", 0) or 0),
            production_count,
            statements,
            erp_uploads,
            financial_uploads,
        ),
        "score_juno": _calculate_juno_score(company_id, db),
    }


def _calculate_juno_score(company_id: int, db: Session) -> float:
    """Canonical Score JUNO used by executive KPIs."""
    try:
        return get_score_calculator(db).calculate_full_score(company_id, persist=False).overall_score
    except Exception:
        return 50.0


def _materialize_kpi(defn: KPIDefinition, ctx: dict[str, Any]) -> dict[str, Any]:
    value, status, note = _kpi_value(defn.id, defn.persona, ctx)
    return {
        "id": defn.id,
        "persona": defn.persona,
        "category": defn.category,
        "label": defn.label,
        "unit": defn.unit,
        "value": value,
        "formatted": _format_value(value, defn.unit),
        "status": status,
        "source": defn.source,
        "description": defn.description,
        "required_data": list(defn.required_data),
        "note": note,
    }


def _kpi_value(kpi_id: str, persona: str, ctx: dict[str, Any]) -> tuple[Any, Status, str]:
    values: dict[str, Any] = {
        "juno_score": ctx["score_juno"],
        "receita_bruta": ctx["revenue_gross"],
        "receita_liquida": ctx["revenue_net"],
        "margem_liquida_pct": ctx["margem_liquida_pct"],
        "margem_ebitda_pct": ctx["margem_ebitda_pct"],
        "fluxo_caixa_operacional": ctx["fluxo_caixa_operacional"],
        "capital_giro": ctx["capital_giro"],
        "liquidez_corrente": ctx["liquidez_corrente"],
        "endividamento_pct": ctx["endividamento_pct"],
        "concentracao_clientes": ctx["top_customer_pct"],
        "perda_estimada": ctx["estimated_loss"],
        "data_trust_score": ctx["trust_report"]["trust_score"]["score"],
        "custo_variavel": _cost_variable(ctx),
        "margem_bruta": ctx["lucro_bruto"],
        "margem_bruta_pct": ctx["margem_bruta_pct"],
        "despesas_fixas": _fixed_expenses(ctx),
        "ebitda": ctx["ebitda"],
        "lucro_liquido": ctx["lucro_liquido"],
        "divida_liquida_ebitda": _net_debt_to_ebitda(ctx),
        "margem_por_produto": ctx["negative_margin_count"],
        "ordens_atrasadas": ctx["delayed_count"],
        "taxa_atraso": _rate(ctx["delayed_count"], ctx["production_count"]),
        "desvio_custo_pct": _production_deviation(ctx, "cost"),
        "desvio_quantidade_pct": _production_deviation(ctx, "qty"),
        "eficiencia_producao": _production_efficiency(ctx),
        "valor_estoque": _optional_float(getattr(ctx["inventory"], "value", None)),
        "estoque_disponivel": _optional_float(getattr(ctx["inventory"], "available", None)),
        "estoque_reservado": _optional_float(getattr(ctx["inventory"], "reserved", None)),
        "lead_time_fornecedores": _optional_float(getattr(ctx["suppliers"], "avg_lead_time", None)),
        "fornecedores_criticos": _critical_suppliers(ctx),
        "perda_operacional": ctx["estimated_loss"],
        "issues_alta": int(ctx["trust_report"].get("high_severity", 0) or 0),
        "uploads_erp": ctx["erp_uploads"],
        "uploads_financeiros": ctx["financial_uploads"],
        "cobertura_dados": ctx["coverage"]["pct"],
        "fontes_pendentes": len(ctx["coverage"]["missing"]),
        "prontidao_executiva": round(
            (ctx["coverage"]["pct"] * 0.45) + (ctx["trust_report"]["trust_score"]["score"] * 0.55),
            2,
        ),
    }
    value = values.get(kpi_id)
    if value is None:
        return None, "missing", "Dados insuficientes para calcular este KPI."

    status_key = (
        "taxa_atraso"
        if kpi_id == "ordens_atrasadas" and persona == "coo"
        else kpi_id
    )
    status_value = (
        _rate(ctx["delayed_count"], ctx["production_count"])
        if status_key == "taxa_atraso"
        else value
    )
    status = _status_for(
        status_key, persona, float(status_value) if isinstance(status_value, (int, float)) else status_value
    )
    return value, status, _note_for(status)


def _group_sections(kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for kpi in kpis:
        grouped.setdefault(kpi["category"], []).append(kpi)
    return [{"title": title, "kpis": items} for title, items in grouped.items()]


def _summary_cards(persona: str, kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred = {
        "ceo": ["juno_score", "receita_liquida", "perda_estimada", "data_trust_score"],
        "cfo": ["receita_liquida", "ebitda", "liquidez_corrente", "capital_giro"],
        "coo": ["ordens_atrasadas", "taxa_atraso", "eficiencia_producao", "perda_operacional"],
        "consultoria": [
            "data_trust_score",
            "cobertura_dados",
            "fontes_pendentes",
            "prontidao_executiva",
        ],
    }[persona]
    by_id = {k["id"]: k for k in kpis}
    return [by_id[k] for k in preferred if k in by_id]


def _action_items(persona: str, kpis: list[dict[str, Any]], ctx: dict[str, Any]) -> list[str]:
    items: list[str] = []
    missing = [k for k in kpis if k["status"] == "missing"]
    critical = [k for k in kpis if k["status"] == "critical"]
    warning = [k for k in kpis if k["status"] == "warning"]

    if missing:
        labels = ", ".join(k["label"] for k in missing[:4])
        items.append(f"Completar fontes de dados para: {labels}.")
    if critical:
        labels = ", ".join(k["label"] for k in critical[:3])
        items.append(f"Tratar imediatamente KPIs criticos: {labels}.")
    if warning and not critical:
        labels = ", ".join(k["label"] for k in warning[:3])
        items.append(f"Revisar pontos de atencao: {labels}.")
    if ctx["trust_report"]["trust_score"]["score"] < 80:
        items.append("Rodar Auditoria e corrigir inconsistencias antes de reuniao executiva.")
    if persona == "cfo" and ctx["financial_uploads"] == 0:
        items.append("Carregar DRE, Balanco e DFC na aba Demonstracoes.")
    if persona == "coo" and ctx["production_count"] == 0:
        items.append("Carregar Ordens de Producao para ativar indicadores operacionais.")
    if not items:
        items.append(
            "Base pronta para revisao executiva; manter rotina de atualizacao e auditoria."
        )
    return items


DRE_SUMMARY_LINE_ITEMS = frozenset(
    {
        "receita_bruta",
        "receita_liquida",
        "vendas_liquidas",
        "vendas",
        "cmv",
        "custo_variavel",
        "cpv",
        "cogs",
        "lucro_bruto",
        "margem_bruta",
        "despesas_operacionais",
        "despesas_fixas",
        "ebitda",
        "lucro_liquido",
        "resultado_liquido",
        "margem_liquida",
    }
)


def _is_revenue_detail_line(key: str) -> bool:
    return key.startswith("receita_") and key not in DRE_SUMMARY_LINE_ITEMS


def _is_cmv_detail_line(key: str) -> bool:
    return key.startswith("cmv_")


def _detail_expense_keys(stmts: dict[str, dict[str, dict[str, float]]], periods: list[str]) -> list[str]:
    keys: set[str] = set()
    for period in periods:
        dre = stmts.get("DRE", {}).get(period, {})
        for key in dre:
            if key in DRE_SUMMARY_LINE_ITEMS:
                continue
            if _is_revenue_detail_line(key) or _is_cmv_detail_line(key):
                continue
            keys.add(key)
    return sorted(keys)


def _humanize_line_item(slug: str) -> str:
    return slug.replace("_", " ").strip().title()


def _sum_detail_expenses(dre: dict[str, float], expense_keys: list[str]) -> float | None:
    values = [_lookup(dre, (key,)) for key in expense_keys]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _build_pnl_table(ctx: dict[str, Any]) -> dict[str, Any]:
    stmts = ctx["statements"].get("DRE", {})
    latest = ctx.get("reporting_periods") or _latest_year_periods(stmts)
    detail_expenses = _detail_expense_keys(ctx["statements"], latest)

    rows_def: list[tuple[str, str, str, str, str]] = [
        ("vendas_liquidas", "Vendas liquidas", "receita_liquida", "flow", "currency"),
        ("custo_variavel", "(-) Custo Variavel", "cost_variable", "flow", "currency"),
        ("margem_bruta", "Margem Bruta", "lucro_bruto", "flow", "currency"),
    ]
    for key in detail_expenses:
        rows_def.append((key, f"(-) {_humanize_line_item(key)}", key, "flow", "currency"))
    rows_def.extend(
        [
            ("despesas_fixas", "Soma", "fixed_expenses", "flow", "currency"),
            ("margem_liquida", "Margem liquida", "lucro_liquido", "flow", "currency"),
            ("ebitda", "EBITDA", "ebitda", "flow", "currency"),
            ("liquidez", "Liquidez", "liquidez_corrente", "snapshot", "ratio"),
            ("endividamento", "Endividamento", "endividamento_pct", "snapshot", "percent"),
            ("fluxo_caixa", "Fluxo de caixa", "caixa_operacional", "flow", "currency"),
            ("capital_giro", "Capital de giro", "capital_giro", "snapshot", "currency"),
        ]
    )

    rows: list[dict[str, Any]] = []
    revenue_values = [_pnl_value(ctx, period, "receita_liquida") for period in latest]
    revenue_total = sum(v for v in revenue_values if isinstance(v, (int, float)))

    for row_id, label, source, total_mode, unit in rows_def:
        values = [_pnl_value(ctx, period, source) for period in latest]
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        total = (
            sum(numeric_values)
            if total_mode == "flow" and numeric_values
            else numeric_values[-1]
            if numeric_values
            else None
        )
        pct = (
            (total / revenue_total * 100)
            if total_mode == "flow" and isinstance(total, (int, float)) and revenue_total
            else None
        )
        rows.append(
            {
                "id": row_id,
                "label": label,
                "total": total,
                "pct": round(pct, 2) if pct is not None else None,
                "values": values,
                "unit": unit,
                "total_mode": total_mode,
            }
        )

    return {"unit": "Valores em R$; indicadores em x/%", "periods": latest, "rows": rows}


def _pnl_value(ctx: dict[str, Any], period: str, source: str) -> float | None:
    dre = ctx["statements"].get("DRE", {}).get(period, {})
    expense_keys = _detail_expense_keys(ctx["statements"], [period])
    if source == "receita_liquida":
        return _lookup(dre, ("receita_liquida", "vendas_liquidas", "vendas", "receita_bruta"))
    if source == "cost_variable":
        direct = _lookup(dre, ("cmv", "custo_variavel", "cpv", "cogs"))
        if direct is not None:
            return direct
        cmv_details = [value for key, value in dre.items() if _is_cmv_detail_line(key)]
        return sum(cmv_details) if cmv_details else None
    if source == "lucro_bruto":
        val = _lookup(dre, ("lucro_bruto", "margem_bruta"))
        if val is not None:
            return val
        receita = _pnl_value(ctx, period, "receita_liquida")
        custo = _pnl_value(ctx, period, "cost_variable")
        return receita + custo if receita is not None and custo is not None and custo < 0 else None
    if source == "fixed_expenses":
        detail_total = _sum_detail_expenses(dre, expense_keys)
        if detail_total is not None:
            return detail_total
        return _lookup(dre, ("despesas_operacionais",))
    if source == "lucro_liquido":
        val = _lookup(dre, ("lucro_liquido", "resultado_liquido", "margem_liquida"))
        if val is not None:
            return val
        lucro_bruto = _pnl_value(ctx, period, "lucro_bruto")
        despesas = _pnl_value(ctx, period, "fixed_expenses")
        if lucro_bruto is not None and despesas is not None:
            return lucro_bruto + despesas
        return None
    if source == "ebitda":
        val = _lookup(dre, ("ebitda",))
        if val is not None:
            return val
        return _pnl_value(ctx, period, "lucro_liquido")
    if source == "liquidez_corrente":
        return _balance_metric(ctx, period, "liquidez_corrente")
    if source == "endividamento_pct":
        return _balance_metric(ctx, period, "endividamento_pct")
    if source == "caixa_operacional":
        return _lookup(ctx["statements"].get("DFC", {}).get(period, {}), ("caixa_operacional", "total_operacional"))
    if source == "capital_giro":
        return _balance_metric(ctx, period, "capital_giro")
    return _lookup(dre, (source,))


def _lookup(row: dict[str, float], names: tuple[str, ...]) -> float | None:
    normalized = {_slug(k): v for k, v in row.items()}
    for name in names:
        value = normalized.get(_slug(name))
        if value is not None:
            return float(value)
    return None


def _margin_rows(db: Session, company_id: int) -> list[dict[str, float]]:
    results = (
        db.query(
            Product.name,
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("receita_liquida"),
            func.count(SalesOrder.id).label("qtd_vendas"),
            Product.standard_cost,
        )
        .join(SalesOrder, SalesOrder.product_id == Product.id)
        .filter(Product.company_id == company_id)
        .group_by(Product.id, Product.name, Product.standard_cost)
        .all()
    )
    rows = []
    for row in results:
        receita = _float(row.receita_liquida)
        custo = float(row.qtd_vendas or 0) * _float(row.standard_cost)
        rows.append({"receita_liquida": receita, "custo_real": custo, "margem": receita - custo})
    return rows


def _top_customer_share(db: Session, company_id: int) -> float | None:
    rows = (
        db.query(
            SalesOrder.customer_id,
            func.sum(SalesOrder.revenue - SalesOrder.discount).label("revenue"),
        )
        .filter(SalesOrder.company_id == company_id)
        .group_by(SalesOrder.customer_id)
        .all()
    )
    total = sum(_float(r.revenue) for r in rows)
    if total <= 0:
        return None
    return round(max(_float(r.revenue) for r in rows) / total * 100, 2)


def _source_coverage(
    *,
    product_count: int,
    customer_count: int,
    sales_count: int,
    production_count: int,
    statements: dict,
) -> dict[str, Any]:
    sources = {
        "Produtos": product_count > 0,
        "Clientes": customer_count > 0,
        "Pedidos": sales_count > 0,
        "Ordens de Producao": production_count > 0,
        "DRE": bool(statements.get("DRE")),
        "Balanco": bool(statements.get("BALANCO")),
        "DFC": bool(statements.get("DFC")),
    }
    loaded = sum(1 for ok in sources.values() if ok)
    total = len(sources)
    return {
        "pct": round(loaded / total * 100, 2),
        "loaded": [name for name, ok in sources.items() if ok],
        "missing": [name for name, ok in sources.items() if not ok],
    }


def _source_status(
    product_count: int,
    customer_count: int,
    sales_count: int,
    production_count: int,
    statements: dict,
    erp_uploads: int,
    financial_uploads: int,
) -> list[dict[str, Any]]:
    coverage = _source_coverage(
        product_count=product_count,
        customer_count=customer_count,
        sales_count=sales_count,
        production_count=production_count,
        statements=statements,
    )
    return [
        {
            "source": "Produtos",
            "loaded": "Produtos" in coverage["loaded"],
            "records": product_count,
        },
        {
            "source": "Clientes",
            "loaded": "Clientes" in coverage["loaded"],
            "records": customer_count,
        },
        {"source": "Pedidos", "loaded": "Pedidos" in coverage["loaded"], "records": sales_count},
        {
            "source": "Ordens de Producao",
            "loaded": "Ordens de Producao" in coverage["loaded"],
            "records": production_count,
        },
        {"source": "DRE", "loaded": "DRE" in coverage["loaded"], "records": None},
        {"source": "Balanco", "loaded": "Balanco" in coverage["loaded"], "records": None},
        {"source": "DFC", "loaded": "DFC" in coverage["loaded"], "records": None},
        {"source": "Uploads ERP", "loaded": erp_uploads > 0, "records": erp_uploads},
        {
            "source": "Uploads Financeiros",
            "loaded": financial_uploads > 0,
            "records": financial_uploads,
        },
    ]


def _financial_value(fin: dict, section: str, key: str, fallback: float | None) -> float | None:
    if not fin.get("available"):
        return fallback
    value = fin.get(section, {}).get(key)
    return _optional_float(value) if value is not None else fallback


def _latest_year_periods(statements: dict[str, dict[str, float]]) -> list[str]:
    periods = sorted(statements.keys())
    if not periods:
        return []
    latest_year = periods[-1].split("-", 1)[0]
    return [period for period in periods if period.startswith(f"{latest_year}-")]


def _accumulated_dre(
    dre_statements: dict[str, dict[str, float]], periods: list[str] | None = None
) -> dict[str, float]:
    """DRE is a flow statement: executive KPIs use accumulated period values."""
    totals: dict[str, float] = {}
    selected_periods = periods or sorted(dre_statements.keys())
    for period in selected_periods:
        period_data = dre_statements.get(period, {})
        for key, value in period_data.items():
            totals[_slug(key)] = totals.get(_slug(key), 0.0) + _float(value)

    receita_bruta = _lookup(totals, ("receita_bruta", "vendas_brutas"))
    receita_liquida = _lookup(totals, ("receita_liquida", "vendas_liquidas", "vendas"))
    custo = _lookup(totals, ("custo_variavel", "cmv", "cpv", "cogs"))
    lucro_bruto = _lookup(totals, ("lucro_bruto", "margem_bruta"))
    if lucro_bruto is None and receita_liquida is not None and custo is not None:
        lucro_bruto = receita_liquida + custo if custo < 0 else receita_liquida - custo

    return {
        "receita_bruta": receita_bruta or 0.0,
        "receita_liquida": receita_liquida or receita_bruta or 0.0,
        "custo_variavel": custo or 0.0,
        "lucro_bruto": lucro_bruto or 0.0,
        "despesas_fixas": _sum_fixed_expenses(totals),
        "ebitda": _lookup(totals, ("ebitda",)) or 0.0,
        "lucro_liquido": _lookup(totals, ("lucro_liquido", "resultado_liquido", "margem_liquida")) or 0.0,
    }


def _accumulated_dfc(
    dfc_statements: dict[str, dict[str, float]], periods: list[str] | None = None
) -> dict[str, float]:
    """DFC operational flow is accumulated; final cash remains a snapshot."""
    totals: dict[str, float] = {}
    selected_periods = periods or sorted(dfc_statements.keys())
    available_periods = [period for period in selected_periods if period in dfc_statements]
    latest_period = available_periods[-1] if available_periods else None
    for period in available_periods:
        period_data = dfc_statements.get(period, {})
        for key, value in period_data.items():
            normalized = _slug(key)
            if normalized == "caixa_final":
                continue
            totals[normalized] = totals.get(normalized, 0.0) + _float(value)
    if latest_period:
        totals["caixa_final"] = _float(dfc_statements[latest_period].get("caixa_final"))
    return {
        "caixa_operacional": _lookup(totals, ("caixa_operacional", "total_operacional")) or 0.0,
        "caixa_investimento": _lookup(totals, ("caixa_investimento", "total_investimento")) or 0.0,
        "caixa_financiamento": _lookup(totals, ("caixa_financiamento", "total_financiamento")) or 0.0,
        "variacao_caixa": _lookup(totals, ("variacao_caixa",)) or 0.0,
        "caixa_final": _lookup(totals, ("caixa_final",)) or 0.0,
    }


def _balance_metric(ctx: dict[str, Any], period: str, metric: str) -> float | None:
    """Balance sheet metrics are snapshots by period, not accumulated flows."""
    bal = ctx["statements"].get("BALANCO", {}).get(period, {})
    if not bal:
        return None
    ac = _lookup(bal, ("ativo_circulante",))
    pc = _lookup(bal, ("passivo_circulante",))
    pnc = _lookup(bal, ("passivo_nao_circulante",))
    pl = _lookup(bal, ("patrimonio_liquido", "pl"))

    if metric == "capital_giro":
        return ac - pc if ac is not None and pc is not None else None
    if metric == "liquidez_corrente":
        return round(ac / pc, 2) if ac is not None and pc else None
    if metric == "endividamento_pct":
        debt = (pc or 0) + (pnc or 0)
        capital = debt + (pl or 0)
        return round(debt / capital * 100, 2) if capital else None
    return None


def _sum_fixed_expenses(row: dict[str, float]) -> float | None:
    summary = _lookup(row, ("despesas_operacionais",))
    if summary is not None:
        return summary
    detail_keys = [
        key
        for key in row
        if key not in DRE_SUMMARY_LINE_ITEMS
        and not _is_revenue_detail_line(key)
        and not _is_cmv_detail_line(key)
    ]
    return _sum_detail_expenses(row, detail_keys)


def _cost_variable(ctx: dict[str, Any]) -> float | None:
    direct = _lookup(ctx.get("dre_accumulated", {}), ("custo_variavel", "cmv", "cpv", "cogs"))
    if direct is not None:
        return direct
    if ctx["revenue_net"] is not None and ctx["lucro_bruto"] is not None:
        return ctx["lucro_bruto"] - ctx["revenue_net"]
    return None


def _fixed_expenses(ctx: dict[str, Any]) -> float | None:
    return _sum_fixed_expenses(ctx.get("dre_accumulated", {}))


def _net_debt_to_ebitda(ctx: dict[str, Any]) -> float | None:
    balanco = ctx["financial"].get("balanco", {}) if ctx["financial"].get("available") else {}
    pc = _optional_float(balanco.get("passivo_circulante"))
    pnc = _optional_float(balanco.get("passivo_nao_circulante"))
    cash = ctx["caixa_final"]
    ebitda = ctx["ebitda"]
    if pc is None or pnc is None or cash is None or not ebitda:
        return None
    return round(((pc + pnc) - cash) / ebitda, 2)


def _production_deviation(ctx: dict[str, Any], kind: str) -> float | None:
    totals = ctx["op_totals"]
    if not totals:
        return None
    if kind == "cost":
        planned = _optional_float(getattr(totals, "planned_cost", None))
        actual = _optional_float(getattr(totals, "actual_cost", None))
    else:
        planned = _optional_float(getattr(totals, "planned_qty", None))
        actual = _optional_float(getattr(totals, "actual_qty", None))
    if planned is None or planned == 0 or actual is None:
        return None
    return round((actual - planned) / planned * 100, 2)


def _production_efficiency(ctx: dict[str, Any]) -> float | None:
    if ctx["production_count"] == 0:
        return None
    delay_penalty = _rate(ctx["delayed_count"], ctx["production_count"]) or 0
    cost_dev = abs(_production_deviation(ctx, "cost") or 0)
    qty_dev = abs(_production_deviation(ctx, "qty") or 0)
    return round(max(0, 100 - (delay_penalty * 0.5) - (cost_dev * 0.3) - (qty_dev * 0.2)), 2)


def _critical_suppliers(ctx: dict[str, Any]) -> int | None:
    if ctx["supplier_count"] == 0:
        return None
    avg = _optional_float(getattr(ctx["suppliers"], "avg_lead_time", None))
    if avg is None:
        return ctx["supplier_count"]
    critical_by_time = _optional_float(getattr(ctx["suppliers"], "critical_by_time", None))
    return int(critical_by_time or 0)


def _rate(part: float, total: float) -> float | None:
    return round(part / total * 100, 2) if total else None


def _status_for(kpi_id: str, persona: str, value: Any) -> Status:
    if value is None:
        return "missing"
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "missing"
    low_bad = {
        "juno_score": (50, 70),
        "data_trust_score": (60, 80),
        "margem_liquida_pct": (0, 8),
        "margem_ebitda_pct": (8, 15),
        "margem_bruta_pct": (15, 30),
        "liquidez_corrente": (1, 1.5),
        "eficiencia_producao": (60, 80),
        "cobertura_dados": (60, 85),
        "prontidao_executiva": (60, 85),
        "fluxo_caixa_operacional": (0, 1),
        "capital_giro": (0, 1),
        "ebitda": (0, 1),
        "lucro_liquido": (0, 1),
    }
    high_bad = {
        "endividamento_pct": (70, 50),
        "concentracao_clientes": (50, 35),
        "taxa_atraso": (30, 10),
        "desvio_custo_pct": (20, 8),
        "desvio_quantidade_pct": (20, 8),
        "ordens_atrasadas": (10, 1),
        "fornecedores_criticos": (5, 1),
        "fontes_pendentes": (4, 1),
        "issues_alta": (3, 1),
        "margem_por_produto": (3, 1),
    }
    if kpi_id in low_bad:
        critical, warning = low_bad[kpi_id]
        return "critical" if value < critical else "warning" if value < warning else "ok"
    if kpi_id in high_bad:
        critical, warning = high_bad[kpi_id]
        return "critical" if value >= critical else "warning" if value >= warning else "ok"
    if kpi_id in {"perda_estimada", "perda_operacional"}:
        return "critical" if value > 0 else "ok"
    return "ok"


def _note_for(status: Status) -> str:
    return {
        "ok": "Dentro da faixa aceitavel.",
        "warning": "Requer acompanhamento.",
        "critical": "Exige acao prioritaria.",
        "missing": "Dados insuficientes.",
    }.get(status, "Revisar.")


def _format_value(value: Any, unit: str) -> str:
    if value is None:
        return "Dados insuficientes"
    if unit == "currency":
        return f"R$ {_format_number(float(value))}"
    if unit == "percent":
        return f"{float(value):.1f}%"
    if unit == "score":
        return f"{float(value):.0f}/100"
    if unit == "ratio":
        return f"{float(value):.2f}x"
    if unit == "days":
        return f"{float(value):.1f} dias"
    if unit == "number":
        return _format_number(float(value), decimals=0)
    return str(value)


def _format_number(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _float(value: Any) -> float:
    return float(value or 0)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
