"""
Comparativos por cenario (Fase C) — REALIZADO | ORCAMENTO | PROJECAO | VALUATION.

Monta matriz auditavel a partir de:
  - REALIZADO: demonstracoes ativas (DB ou templates canonicos)
  - ORCAMENTO: coluna Orçamento/Budget no template, ou meta sintetica documentada
  - PROJECAO: ano +1 do motor run_valuation_scenario
  - VALUATION: ano terminal da projecao + Enterprise Value
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import templates_financeiro as tf
from .financials import get_financial_summary
from .valuation_scenario import run_valuation_scenario

CENARIOS = ("REALIZADO", "ORCAMENTO", "PROJECAO", "VALUATION")
INDICADORES = (
    ("receita_liquida", "Receita Liquida"),
    ("ebitda", "EBITDA"),
    ("lucro_liquido", "Lucro Liquido"),
    ("enterprise_value", "Enterprise Value"),
)

BUDGET_HEADER_HINTS = ("orç", "orc", "budget", "meta", "planej")


def _pct_vs_base(base: float | None, other: float | None) -> float | None:
    if base is None or other is None or base == 0:
        return None
    return round((other - base) / abs(base) * 100, 2)


def _realizado_metrics(company_id: int, db: Session) -> dict[str, float | None]:
    summary = get_financial_summary(company_id, db)
    if not summary.get("available"):
        return {k: None for k, _ in INDICADORES}
    dre = summary.get("dre") or {}
    return {
        "receita_liquida": _f(dre.get("receita_liquida")),
        "ebitda": _f(dre.get("ebitda")),
        "lucro_liquido": _f(dre.get("lucro_liquido")),
        "enterprise_value": None,
    }


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _budget_period_from_templates() -> tuple[str | None, str]:
    workbook = tf._find_workbook()
    if workbook is None:
        return None, "sintetico"
    path = str(workbook)
    mtime = workbook.stat().st_mtime
    dre = tf._load_sheet(path, mtime, tf.SHEET_DRE)
    for header in tf._sheet_headers(dre):
        if header is None:
            continue
        text = str(header).strip().lower()
        if any(h in text for h in BUDGET_HEADER_HINTS):
            return str(header).strip(), "template"
    return None, "sintetico"


def _orcamento_metrics(realizado: dict[str, float | None]) -> tuple[dict[str, float | None], str]:
    period, source = _budget_period_from_templates()
    out: dict[str, float | None] = {
        "receita_liquida": None,
        "ebitda": None,
        "lucro_liquido": None,
        "enterprise_value": None,
    }

    if source == "template" and period:
        workbook = tf._find_workbook()
        assert workbook is not None
        path = str(workbook)
        mtime = workbook.stat().st_mtime
        sheets = {
            "dre": tf._load_sheet(path, mtime, tf.SHEET_DRE),
            "ebitda": tf._load_sheet(path, mtime, tf.SHEET_EBITDA),
        }
        out["receita_liquida"] = tf.extract_value_safe(sheets["dre"], "Receita Líquida", period)
        out["ebitda"] = tf.extract_value_safe(sheets["ebitda"], "EBITDA Ajustado", period)
        out["lucro_liquido"] = tf.extract_value_safe(sheets["ebitda"], "Lucro (prejuízo) Líquido", period)
        nota = f"Orçamento lido da coluna '{period}' do template."
        return out, nota

    factor = 0.97
    nota = (
        "Orçamento sintético (97% do realizado) — substitua por coluna Orçamento/Budget "
        "no template ou upload de budget dedicado."
    )
    for key in ("receita_liquida", "ebitda", "lucro_liquido"):
        base = realizado.get(key)
        out[key] = round(base * factor, 2) if base is not None else None
    return out, nota


def _projecao_e_valuation(
    company_id: int, db: Session
) -> tuple[dict[str, float | None], dict[str, float | None], dict[str, Any]]:
    val = run_valuation_scenario(company_id, db)
    proj_rows = [r for r in val.get("dre_projetada", []) if r.get("tipo") == "projecao"]
    term_rows = proj_rows[-1:] if proj_rows else []
    year1 = proj_rows[0] if proj_rows else {}

    projecao = {
        "receita_liquida": _f(year1.get("receita_liquida")),
        "ebitda": _f(year1.get("ebitda")),
        "lucro_liquido": _f(year1.get("lucro_liquido")),
        "enterprise_value": None,
    }
    terminal = term_rows[0] if term_rows else {}
    valuation = {
        "receita_liquida": _f(terminal.get("receita_liquida")),
        "ebitda": _f(terminal.get("ebitda")),
        "lucro_liquido": _f(terminal.get("lucro_liquido")),
        "enterprise_value": _f((val.get("valuation") or {}).get("enterprise_value")),
    }
    return projecao, valuation, val


def build_comparativos_cenario(company_id: int, db: Session) -> dict[str, Any]:
    realizado = _realizado_metrics(company_id, db)
    orcamento, nota_orc = _orcamento_metrics(realizado)
    projecao, valuation, val_payload = _projecao_e_valuation(company_id, db)

    por_cenario = {
        "REALIZADO": realizado,
        "ORCAMENTO": orcamento,
        "PROJECAO": projecao,
        "VALUATION": valuation,
    }

    linhas: list[dict[str, Any]] = []
    for key, _label in INDICADORES:
        valores = {c: por_cenario[c].get(key) for c in CENARIOS}
        base = valores["REALIZADO"]
        linhas.append(
            {
                "indicador_key": key,
                "valores": valores,
                "variacao_vs_realizado_pct": {
                    c: _pct_vs_base(base, valores[c]) for c in CENARIOS if c != "REALIZADO"
                },
            }
        )

    dre = get_financial_summary(company_id, db).get("dre") or {}
    periodo = dre.get("periodo") or val_payload.get("periodo_base")

    return {
        "id": "comparativos_cenario",
        "titulo": "Comparativos por Cenario",
        "cenarios": list(CENARIOS),
        "periodo_referencia": periodo,
        "linhas": linhas,
        "premissas_valuation": val_payload.get("premissas"),
        "enterprise_value": valuation.get("enterprise_value"),
        "nota": (
            f"{nota_orc} PROJECAO = ano +1 do cenario de valuation; "
            f"VALUATION = ultimo ano projetado + EV (WACC {val_payload.get('premissas', {}).get('taxa_desconto_pct')}%)."
        ),
    }
