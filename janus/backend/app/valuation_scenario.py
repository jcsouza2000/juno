"""
Motor determinístico de valuation por cenário (DRE/DFC projetados + EV).
Usado pela IA (tool run_valuation_scenario) e pelo endpoint REST.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import financials as fin_module
from . import templates_financeiro as tf


def _round2(value: float) -> float:
    return round(float(value), 2)


def _parse_base_year(competencia: str) -> int:
    digits = "".join(ch for ch in competencia if ch.isdigit())
    if len(digits) >= 4:
        return int(digits[:4])
    return 2025


def _load_base_metrics(company_id: int, db: Session) -> dict[str, Any]:
    summary = fin_module.get_financial_summary(company_id, db)
    if not summary.get("available"):
        raise ValueError("Demonstrações financeiras indisponíveis para valuation.")

    dre = summary.get("dre") or {}
    resumo = tf.build_resumo_demonstracoes() if tf.use_templates_as_canonical() else None
    dfc = (resumo or {}).get("dfc") or {}

    receita = float(dre.get("receita_liquida") or 0)
    ebitda = float(dre.get("ebitda") or 0)
    lucro_liquido = float(dre.get("lucro_liquido") or 0)
    lucro_antes = float(dfc.get("lucro_antes_tributos") or 0)
    deprec = float(dfc.get("depreciacao_amortizacao") or 0)

    if receita <= 0 or ebitda <= 0:
        raise ValueError("Receita ou EBITDA base inválidos para projeção.")

    if lucro_antes <= 0:
        lucro_antes = ebitda - deprec
    if deprec <= 0:
        deprec = max(ebitda - lucro_antes, 0)

    imposto = max(lucro_antes - lucro_liquido, 0)
    tax_rate = imposto / lucro_antes if lucro_antes > 0 else 0.34

    custos_operacionais = receita - ebitda
    deducoes_pre_ir = max(ebitda - deprec - lucro_antes, 0)

    periodo = str(dre.get("periodo") or tf.DEFAULT_COMPETENCIA)
    ano_base = _parse_base_year(periodo)

    fcf_base = lucro_liquido + deprec - (deprec * (receita / receita))

    return {
        "company_id": company_id,
        "source": summary.get("source", "database"),
        "periodo": periodo,
        "ano_base": ano_base,
        "receita_liquida": receita,
        "ebitda": ebitda,
        "lucro_liquido": lucro_liquido,
        "lucro_antes_ir": lucro_antes,
        "depreciacao": deprec,
        "imposto": imposto,
        "tax_rate": tax_rate,
        "custos_operacionais": custos_operacionais,
        "deducoes_pre_ir": deducoes_pre_ir,
        "fcf_base": fcf_base,
    }


def run_valuation_scenario(
    company_id: int,
    db: Session,
    *,
    anos: int = 5,
    crescimento_receita: float = 0.10,
    crescimento_custos_fixos: float = 0.05,
    taxa_desconto: float = 0.10,
) -> dict[str, Any]:
    """
    Projeta DRE/DFC por `anos` períodos (inclui ano base + anos futuros).
    Premissas:
      - receita: crescimento composto anual (ex.: 0.10 = 10% a.a.)
      - custos operacionais (receita − EBITDA base): crescimento composto (ex.: 5% a.a.)
      - depreciação: constante (ano base)
      - deduções pré-IR: escalam com receita
      - imposto: alíquota efetiva do ano base
      - capex de manutenção = depreciação × (receita_t / receita_0)
      - EV = Σ PV(FCF) dos anos projetados após o ano base
    """
    if anos < 1 or anos > 20:
        raise ValueError("Parâmetro 'anos' deve estar entre 1 e 20.")
    if not 0 <= crescimento_receita <= 1:
        raise ValueError("crescimento_receita deve ser decimal (ex.: 0.10 para 10%).")
    if not 0 <= crescimento_custos_fixos <= 1:
        raise ValueError("crescimento_custos_fixos deve ser decimal (ex.: 0.05 para 5%).")
    if not 0 < taxa_desconto <= 1:
        raise ValueError("taxa_desconto deve ser decimal (ex.: 0.10 para 10%).")

    base = _load_base_metrics(company_id, db)
    receita_0 = base["receita_liquida"]
    custos_0 = base["custos_operacionais"]
    deprec_0 = base["depreciacao"]
    deducoes_0 = base["deducoes_pre_ir"]
    tax_rate = base["tax_rate"]
    ano_base = base["ano_base"]

    dre_rows: list[dict[str, Any]] = []
    dfc_rows: list[dict[str, Any]] = []
    pv_total = 0.0

    for t in range(anos):
        ano = ano_base + t
        is_base = t == 0

        if is_base:
            receita = base["receita_liquida"]
            custos = base["custos_operacionais"]
            ebitda = base["ebitda"]
            lucro_antes = base["lucro_antes_ir"]
            imposto = base["imposto"]
            lucro_liq = base["lucro_liquido"]
            deprec = base["depreciacao"]
        else:
            receita = receita_0 * ((1 + crescimento_receita) ** t)
            custos = custos_0 * ((1 + crescimento_custos_fixos) ** t)
            ebitda = receita - custos
            deducoes = deducoes_0 * (receita / receita_0) if receita_0 else deducoes_0
            lucro_antes = ebitda - deprec_0 - deducoes
            imposto = max(lucro_antes, 0) * tax_rate
            lucro_liq = lucro_antes - imposto
            deprec = deprec_0

        capex = deprec * (receita / receita_0) if receita_0 else deprec
        fcf = lucro_liq + deprec - capex

        fator = (1 + taxa_desconto) ** t
        pv = fcf / fator if t > 0 else 0.0
        if t > 0:
            pv_total += pv

        dre_rows.append(
            {
                "ano": ano,
                "tipo": "realizado" if is_base else "projecao",
                "receita_liquida": _round2(receita),
                "custos_operacionais": _round2(custos),
                "ebitda": _round2(ebitda),
                "lucro_liquido": _round2(lucro_liq),
            }
        )
        dfc_rows.append(
            {
                "ano": ano,
                "tipo": "realizado" if is_base else "projecao",
                "ebitda": _round2(ebitda),
                "depreciacao": _round2(deprec),
                "lucro_antes_ir": _round2(lucro_antes),
                "imposto": _round2(imposto),
                "lucro_liquido": _round2(lucro_liq),
                "capex": _round2(capex),
                "fcf": _round2(fcf),
                "fator_desconto": _round2(fator),
                "pv_fcf": _round2(pv),
            }
        )

    projecoes = [r for r in dfc_rows if r["tipo"] == "projecao"]
    anos_projecao = len(projecoes)

    return {
        "kind": "valuation_scenario",
        "company_id": company_id,
        "cenario": "PROJECAO",
        "unidade": "R$ milhoes",
        "ano_base": ano_base,
        "fonte_base": base["source"],
        "periodo_base": base["periodo"],
        "premissas": {
            "anos": anos,
            "crescimento_receita_pct": _round2(crescimento_receita * 100),
            "crescimento_custos_fixos_pct": _round2(crescimento_custos_fixos * 100),
            "taxa_desconto_pct": _round2(taxa_desconto * 100),
            "anos_descontados": anos_projecao,
        },
        "base": {
            "receita_liquida": _round2(base["receita_liquida"]),
            "ebitda": _round2(base["ebitda"]),
            "lucro_liquido": _round2(base["lucro_liquido"]),
            "depreciacao": _round2(base["depreciacao"]),
            "fcf": _round2(base["fcf_base"]),
        },
        "dre_projetada": dre_rows,
        "dfc_projetado": dfc_rows,
        "valuation": {
            "enterprise_value": _round2(pv_total),
            "pv_fcf_total": _round2(pv_total),
            "taxa_desconto_pct": _round2(taxa_desconto * 100),
            "metodo": "FCF descontado (WACC) — fluxos projetados após ano base",
        },
        "diagnostico": (
            f"Cenário de valuation em {anos} anos a partir de {ano_base}: "
            f"receita +{crescimento_receita * 100:.0f}% a.a., "
            f"custos operacionais +{crescimento_custos_fixos * 100:.0f}% a.a., "
            f"WACC {taxa_desconto * 100:.0f}%. "
            f"Enterprise Value (PV FCF {anos_projecao} anos): R$ {_round2(pv_total):,.2f} mi."
        ),
    }
