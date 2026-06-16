"""Leitura canonica das demonstracoes e KPIs a partir de Templates/."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "Templates"
DEFAULT_COMPETENCIA = "2025"
DEFAULT_PATRIMONIAL = "4T25"
DEFAULT_TRIMESTRES = ("1T25", "2T25", "3T25", "4T25")

SHEET_DRE = "2. DRE"
SHEET_BALANCO = "1. Balanço Patrimonial"
SHEET_DFC = "2. Fluxo de Caixa"
SHEET_EBITDA = "5. EBITDA"

WCM_METAS = {
    "oee": 85.0,
    "ftt_fpy": 98.0,
    "otd": 99.0,
    "tfa": 0.0,
}

ACCOUNT_SLUGS: dict[str, tuple[str, ...]] = {
    "receita_bruta": ("receita bruta",),
    "receita_liquida": ("receita liquida", "receita líquida"),
    "cpv": ("custo dos produtos vendidos", "cpv", "cmv"),
    "despesas_admin": ("gerais & administrativas", "despesas administrativas"),
    "lucro_bruto": ("lucro bruto", "margem bruta"),
    "lucro_liquido": ("lucro (prejuizo) liquido", "lucro (prejuízo) líquido", "lucro liquido"),
    "ebitda_ajustado": ("ebitda ajustado", "ebitda"),
    "estoques": ("estoques",),
    "contas_receber": ("contas a receber",),
    "ativo_circulante": ("ativo circulante",),
    "passivo_circulante": ("passivo circulante",),
}


def templates_dir() -> Path:
    return TEMPLATES_DIR


def templates_available() -> bool:
    return _find_workbook() is not None


def use_templates_as_canonical() -> bool:
    import os

    if os.getenv("JUNO_DISABLE_TEMPLATES", "").lower() in {"1", "true", "yes"}:
        return False
    if os.getenv("JUNO_USE_TEMPLATES", "").lower() in {"0", "false", "no"}:
        return False
    return templates_available()


def _find_workbook() -> Path | None:
    if not TEMPLATES_DIR.exists():
        return None
    matches = sorted(p for p in TEMPLATES_DIR.glob("Demontra*.xlsx") if not p.name.startswith("~$"))
    return matches[0] if matches else None


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return cleaned or "conta"


def _clean_value(raw) -> float:
    if pd.isna(raw) or str(raw).strip() in {"-", ""}:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    val_str = str(raw).strip()
    if "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    else:
        parts = val_str.split(".")
        if len(parts) > 2:
            val_str = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(val_str)
    except ValueError:
        return 0.0


@lru_cache(maxsize=8)
def _load_sheet(workbook_path: str, mtime: float, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None)
    df = df.dropna(how="all")
    if df.empty:
        return df
    df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip()
    return df


def _sheet_headers(df: pd.DataFrame) -> list[Any]:
    return df.iloc[0].tolist()


def resolve_column(df: pd.DataFrame, periodo: str) -> int:
    headers = _sheet_headers(df)
    alvo = str(periodo).strip().lower()
    for idx, header in enumerate(headers):
        if header is None or (isinstance(header, float) and pd.isna(header)):
            continue
        texto = str(header).strip().lower()
        if texto == alvo or texto.replace(".0", "") == alvo.replace(".0", ""):
            return idx
        if alvo.isdigit() and isinstance(header, (int, float)) and not pd.isna(header):
            if int(header) == int(alvo):
                return idx
    raise KeyError(f"Periodo '{periodo}' nao encontrado em {headers}")


def extract_value(df: pd.DataFrame, conta: str, periodo: str) -> float:
    coluna = resolve_column(df, periodo)
    alvo = conta.lower().strip()
    contas = df.iloc[:, 0].astype(str).str.strip().str.lower()
    linha = df[contas == alvo]
    if linha.empty:
        linha = df[contas.str.contains(alvo, regex=False, na=False)]
    if linha.empty:
        raise KeyError(f"Conta '{conta}' nao encontrada")
    return _clean_value(linha.iloc[0, coluna])


def extract_value_safe(df: pd.DataFrame, conta: str, periodo: str) -> float | None:
    try:
        return extract_value(df, conta, periodo)
    except KeyError:
        return None


def _match_account_slug(label: str) -> str | None:
    normalized = _slug(label)
    for slug, aliases in ACCOUNT_SLUGS.items():
        for alias in aliases:
            if normalized == _slug(alias) or _slug(alias) in normalized:
                return slug
    return None


def _period_columns(df: pd.DataFrame) -> list[str]:
    periods: list[str] = []
    for header in _sheet_headers(df)[1:]:
        if header is None or (isinstance(header, float) and pd.isna(header)):
            continue
        periods.append(str(header).strip().replace(".0", ""))
    return periods


def _statements_from_sheet(
    df: pd.DataFrame, statement_type: str
) -> dict[str, dict[str, dict[str, float]]]:
    periods = _period_columns(df)
    result: dict[str, dict[str, float]] = {}
    for period in periods:
        bucket: dict[str, float] = {}
        for _, row in df.iloc[1:].iterrows():
            label = str(row.iloc[0]).strip()
            if not label or label.lower() == "nan":
                continue
            slug = _match_account_slug(label) or _slug(label)
            try:
                col_idx = resolve_column(df, period)
            except KeyError:
                continue
            value = _clean_value(row.iloc[col_idx])
            if value != 0.0 or slug in ACCOUNT_SLUGS:
                bucket[slug] = value
        if bucket:
            result[period] = bucket
    return {statement_type: result}


def build_statements() -> dict[str, dict[str, dict[str, float]]]:
    workbook = _find_workbook()
    if workbook is None:
        return {}
    return _build_statements_cached(str(workbook), workbook.stat().st_mtime)


@lru_cache(maxsize=2)
def _build_statements_cached(
    workbook_path: str, mtime: float
) -> dict[str, dict[str, dict[str, float]]]:
    dre_df = _load_sheet(workbook_path, mtime, SHEET_DRE)
    bal_df = _load_sheet(workbook_path, mtime, SHEET_BALANCO)
    ebitda_df = _load_sheet(workbook_path, mtime, SHEET_EBITDA)

    statements: dict[str, dict[str, dict[str, float]]] = {}
    statements.update(_statements_from_sheet(dre_df, "DRE"))
    statements.update(_statements_from_sheet(bal_df, "BALANCO"))

    ebitda_stmt = _statements_from_sheet(ebitda_df, "EBITDA").get("EBITDA", {})
    statements["EBITDA"] = ebitda_stmt

    for period, ebitda_rows in ebitda_stmt.items():
        dre_period = statements.setdefault("DRE", {}).setdefault(period, {})
        for key, value in ebitda_rows.items():
            dre_period.setdefault(key, value)
            if key == "lucro_liquido":
                dre_period["lucro_liquido"] = value
            if key == "ebitda_ajustado":
                dre_period["ebitda"] = value

    return statements


def _pct(parte: float | None, base: float | None) -> float | None:
    if parte is None or not base:
        return None
    return round(parte / base * 100, 2)


def _score_industrial(
    margem_ebitda: float | None,
    margem_liquida: float | None,
    racio_admin: float | None,
    giro: float | None,
) -> float:
    ebitda = margem_ebitda or 0.0
    liquida = margem_liquida or 0.0
    admin = racio_admin or 0.0
    giro_val = giro or 0.0
    ebitda_score = min(max(ebitda / 40 * 35, 0), 35)
    liquida_score = min(max(liquida / 15 * 25, 0), 25)
    admin_score = max(20 - admin * 2, 0)
    giro_score = min(giro_val / 3 * 20, 20)
    return round(ebitda_score + liquida_score + admin_score + giro_score, 1)


def _sintese_ia(
    score: float,
    margem_ebitda: float | None,
    margem_liquida: float | None,
    giro: float | None,
) -> str:
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
        "conforme modelo Templates; OEE/FTT aguardam conector de producao."
    )


@dataclass(frozen=True)
class TemplateKPIBundle:
    workbook: Path
    competencia: str
    patrimonial: str
    receita_bruta: float
    receita_liquida: float
    custo_produtos: float
    lucro_bruto: float
    lucro_liquido: float
    ebitda_ajustado: float
    despesas_admin: float
    estoques: float
    contas_receber: float
    margem_bruta_pct: float
    margem_liquida_pct: float
    margem_ebitda_pct: float
    racio_admin_pct: float
    giro_estoque: float
    score_industrial: float


def load_kpi_bundle(
    competencia: str = DEFAULT_COMPETENCIA,
    patrimonial: str = DEFAULT_PATRIMONIAL,
) -> TemplateKPIBundle | None:
    workbook = _find_workbook()
    if workbook is None:
        return None

    dre = _load_sheet(str(workbook), workbook.stat().st_mtime, SHEET_DRE)
    balanco = _load_sheet(str(workbook), workbook.stat().st_mtime, SHEET_BALANCO)
    ebitda = _load_sheet(str(workbook), workbook.stat().st_mtime, SHEET_EBITDA)

    receita_bruta = extract_value(dre, "Receita Bruta", competencia)
    receita_liquida = extract_value(dre, "Receita Líquida", competencia)
    custo_produtos = extract_value(dre, "Custo dos Produtos Vendidos", competencia)
    lucro_bruto = receita_liquida + custo_produtos
    despesas_admin = extract_value(dre, "Gerais & Administrativas", competencia)
    lucro_liquido = extract_value(ebitda, "Lucro (prejuízo) Líquido", competencia)
    ebitda_ajustado = extract_value(ebitda, "EBITDA Ajustado", competencia)
    estoques = extract_value(balanco, "Estoques", patrimonial)
    contas_receber = extract_value(balanco, "Contas a Receber", patrimonial)

    margem_bruta = _pct(lucro_bruto, receita_liquida) or 0.0
    margem_liquida = _pct(lucro_liquido, receita_liquida) or 0.0
    margem_ebitda = _pct(ebitda_ajustado, receita_liquida) or 0.0
    racio_admin = _pct(abs(despesas_admin), receita_bruta) or 0.0
    giro = round(abs(custo_produtos) / estoques, 2) if estoques else 0.0
    score = _score_industrial(margem_ebitda, margem_liquida, racio_admin, giro)

    return TemplateKPIBundle(
        workbook=workbook,
        competencia=competencia,
        patrimonial=patrimonial,
        receita_bruta=receita_bruta,
        receita_liquida=receita_liquida,
        custo_produtos=custo_produtos,
        lucro_bruto=lucro_bruto,
        lucro_liquido=lucro_liquido,
        ebitda_ajustado=ebitda_ajustado,
        despesas_admin=despesas_admin,
        estoques=estoques,
        contas_receber=contas_receber,
        margem_bruta_pct=margem_bruta,
        margem_liquida_pct=margem_liquida,
        margem_ebitda_pct=margem_ebitda,
        racio_admin_pct=racio_admin,
        giro_estoque=giro,
        score_industrial=score,
    )


def build_unified_payload(
    competencia: str = DEFAULT_COMPETENCIA,
    patrimonial: str = DEFAULT_PATRIMONIAL,
    trimestres: tuple[str, ...] = DEFAULT_TRIMESTRES,
) -> dict[str, Any] | None:
    workbook = _find_workbook()
    if workbook is None:
        return None
    return _build_unified_payload_cached(
        str(workbook),
        workbook.stat().st_mtime,
        competencia,
        patrimonial,
        trimestres,
    )


@lru_cache(maxsize=4)
def _build_unified_payload_cached(
    workbook_path: str,
    mtime: float,
    competencia: str,
    patrimonial: str,
    trimestres: tuple[str, ...],
) -> dict[str, Any] | None:
    bundle = load_kpi_bundle(competencia=competencia, patrimonial=patrimonial)
    if bundle is None:
        return None

    dre = _load_sheet(workbook_path, mtime, SHEET_DRE)
    balanco = _load_sheet(workbook_path, mtime, SHEET_BALANCO)
    ebitda = _load_sheet(workbook_path, mtime, SHEET_EBITDA)

    tendencia_faturamento = [
        {"periodo": tri, "valor": extract_value(dre, "Receita Líquida", tri)} for tri in trimestres
    ]
    tendencia_margens = []
    tendencia_giro = []
    for tri in trimestres:
        rec = extract_value(dre, "Receita Líquida", tri)
        cpv = extract_value(dre, "Custo dos Produtos Vendidos", tri)
        lucro = extract_value(ebitda, "Lucro (prejuízo) Líquido", tri)
        ebitda_tri = extract_value(ebitda, "EBITDA Ajustado", tri)
        est = extract_value_safe(balanco, "Estoques", tri) or bundle.estoques
        tendencia_margens.append(
            {
                "periodo": tri,
                "margem_bruta": _pct(rec + cpv, rec),
                "margem_liquida": _pct(lucro, rec),
                "margem_ebitda": _pct(ebitda_tri, rec),
            }
        )
        tendencia_giro.append({"periodo": tri, "valor": round(abs(cpv) / est, 2) if est else 0.0})

    kpis_unificados = {
        "Margem Bruta": {
            "formula": "((Receita Líquida + CPV) / Receita Líquida) * 100",
            "valores": f"Receita Líq: {bundle.receita_liquida:,.2f} | CPV: {bundle.custo_produtos:,.2f}",
            "resultado": f"{bundle.margem_bruta_pct:.2f}%",
            "valor_numerico": bundle.margem_bruta_pct,
        },
        "Margem Líquida": {
            "formula": "(Lucro Líquido / Receita Líquida) * 100",
            "valores": f"Lucro Líq: {bundle.lucro_liquido:,.2f} | Receita Líq: {bundle.receita_liquida:,.2f}",
            "resultado": f"{bundle.margem_liquida_pct:.2f}%",
            "valor_numerico": bundle.margem_liquida_pct,
        },
        "Margem EBITDA Ajustada": {
            "formula": "(EBITDA Ajustado / Receita Líquida) * 100",
            "valores": f"EBITDA Ajustado: {bundle.ebitda_ajustado:,.2f} | Receita Líq: {bundle.receita_liquida:,.2f}",
            "resultado": f"{bundle.margem_ebitda_pct:.2f}%",
            "valor_numerico": bundle.margem_ebitda_pct,
        },
        "Rácio Custos Administrativos": {
            "formula": "(Despesas Administrativas / Receita Bruta) * 100",
            "valores": f"Desp Admin: {abs(bundle.despesas_admin):,.2f} | Receita Bruta: {bundle.receita_bruta:,.2f}",
            "resultado": f"{bundle.racio_admin_pct:.2f}%",
            "valor_numerico": bundle.racio_admin_pct,
        },
        "Giro de Estoque (Financeiro)": {
            "formula": "CPV / Saldo de Estoques",
            "valores": f"CPV Absoluto: {abs(bundle.custo_produtos):,.2f} | Estoque: {bundle.estoques:,.2f}",
            "resultado": f"{bundle.giro_estoque:.2f} vezes no ano",
            "valor_numerico": bundle.giro_estoque,
        },
    }

    return {
        "meta": {
            "fonte": bundle.workbook.name,
            "templates_dir": str(TEMPLATES_DIR),
            "unidade": "R$ milhoes",
            "periodo_competencia": competencia,
            "periodo_patrimonial": patrimonial,
            "source_mode": "templates",
            "modelo_kpi": "Templates/KPIs_Templates.md",
        },
        "governanca": {
            "erp_conexao": {"label": "Conexao ERP", "status": "ativa"},
            "auditoria_lgpd": {"label": "Auditoria LGPD", "status": "ok"},
            "busca_inteligente_placeholder": "Pergunte ao UNO sobre a operacao...",
        },
        "core": {
            "score_industrial": bundle.score_industrial,
            "sintese_ia": _sintese_ia(
                bundle.score_industrial,
                bundle.margem_ebitda_pct,
                bundle.margem_liquida_pct,
                bundle.giro_estoque,
            ),
        },
        "quadrantes": {
            "operacoes": {
                "titulo": "Operacoes",
                "series": {
                    "oee": {
                        "valor": None,
                        "meta_wcm": WCM_METAS["oee"],
                        "fonte": "integracao_producao_pendente",
                    },
                    "ftt_fpy": {
                        "valor": None,
                        "meta_wcm": WCM_METAS["ftt_fpy"],
                        "fonte": "integracao_producao_pendente",
                    },
                    "giro_estoque": {
                        "valor": bundle.giro_estoque,
                        "meta_wcm": None,
                        "fonte": "templates_balanco_dre",
                    },
                },
                "tendencia_giro_estoque": tendencia_giro,
            },
            "financeiro": {
                "titulo": "Financeiro",
                "cards": {
                    "faturamento": bundle.receita_liquida,
                    "margem_bruta_pct": bundle.margem_bruta_pct,
                    "margem_liquida_pct": bundle.margem_liquida_pct,
                    "ebitda_ajustado_pct": bundle.margem_ebitda_pct,
                },
                "tendencia_faturamento": tendencia_faturamento,
                "tendencia_margens": tendencia_margens,
            },
            "risco_pessoas": {
                "titulo": "Risco e Pessoas",
                "indicadores": {
                    "tfa": {
                        "valor": None,
                        "meta_wcm": WCM_METAS["tfa"],
                        "fonte": "integracao_rh_pendente",
                    },
                    "turnover": {
                        "valor": None,
                        "meta_wcm": None,
                        "fonte": "integracao_rh_pendente",
                    },
                    "racio_administrativo_pct": bundle.racio_admin_pct,
                },
                "contas_receber": bundle.contas_receber,
            },
        },
        "kpis_unificados": kpis_unificados,
        "resumo_demonstracoes": build_resumo_demonstracoes(competencia, patrimonial),
        "busca_inteligente": _build_busca_inteligente(bundle, kpis_unificados),
        "relatorio_templates": build_demonstracoes_relatorio(competencia, patrimonial, trimestres),
    }


def build_resumo_demonstracoes(
    competencia: str = DEFAULT_COMPETENCIA,
    patrimonial: str = DEFAULT_PATRIMONIAL,
) -> dict[str, Any] | None:
    bundle = load_kpi_bundle(competencia=competencia, patrimonial=patrimonial)
    if bundle is None:
        return None

    workbook = bundle.workbook
    mtime = workbook.stat().st_mtime
    dre = _load_sheet(str(workbook), mtime, SHEET_DRE)
    balanco = _load_sheet(str(workbook), mtime, SHEET_BALANCO)
    ebitda = _load_sheet(str(workbook), mtime, SHEET_EBITDA)

    lucro_bruto_dre = extract_value_safe(dre, "Lucro Bruto", competencia) or bundle.lucro_bruto
    cpv = bundle.custo_produtos
    dre_admin = bundle.despesas_admin

    bal_caixa = extract_value_safe(balanco, "Caixa e equivalente de caixa", patrimonial) or 0.0
    bal_ativo_circ = extract_value_safe(balanco, "Ativo Circulante", patrimonial) or 0.0

    dfc_lucro_antes = extract_value_safe(dre, "Lucro antes I.R. Cont. Social", competencia) or 0.0
    dfc_deprec = (
        extract_value_safe(dre, "Depreciação/Amortização/Exaustão", competencia)
        or extract_value_safe(ebitda, "(+) Depreciação, Exaustão e Amortização", competencia)
        or 0.0
    )

    margem_bruta_dre = _pct(lucro_bruto_dre, bundle.receita_liquida) or 0.0

    return {
        "unidade": "R$ milhoes",
        "competencia": competencia,
        "patrimonial": patrimonial,
        "fonte": workbook.name,
        "dre": {
            "titulo": "Resumo DRE",
            "receita_bruta": bundle.receita_bruta,
            "receita_liquida": bundle.receita_liquida,
            "cpv": cpv,
            "lucro_bruto": lucro_bruto_dre,
            "despesas_admin": dre_admin,
        },
        "balanco": {
            "titulo": "Resumo Balanco Patrimonial",
            "caixa_equivalentes": bal_caixa,
            "contas_receber": bundle.contas_receber,
            "estoques": bundle.estoques,
            "ativo_circulante": bal_ativo_circ,
        },
        "dfc": {
            "titulo": "Resumo Fluxo de Caixa",
            "lucro_antes_tributos": dfc_lucro_antes,
            "depreciacao_amortizacao": dfc_deprec,
        },
        "kpis": {
            "titulo": "Indicadores Chave (KPIs)",
            "margem_bruta_pct": margem_bruta_dre,
            "margem_ebitda_pct": bundle.margem_ebitda_pct,
            "margem_liquida_pct": bundle.margem_liquida_pct,
            "racio_admin_pct": bundle.racio_admin_pct,
            "giro_estoque": bundle.giro_estoque,
            "score_industrial": bundle.score_industrial,
        },
    }


DRE_REPORT_LINES: tuple[tuple[str, str, str, str], ...] = (
    ("dre", "Receita Bruta", "Receita Bruta", "receita_bruta"),
    ("dre", "Receita Líquida", "Receita Líquida", "receita_liquida"),
    (
        "dre",
        "Custo dos Produtos Vendidos",
        "Custo dos Produtos Vendidos (CPV)",
        "cpv",
    ),
    ("dre", "Lucro Bruto", "Lucro Bruto", "lucro_bruto"),
    ("dre", "Gerais & Administrativas", "Gerais & Administrativas", "despesas_admin"),
    ("ebitda", "Lucro (prejuízo) Líquido", "Lucro (Prejuízo) Líquido", "lucro_liquido"),
    ("ebitda", "EBITDA Ajustado", "EBITDA Ajustado", "ebitda"),
)

BALANCO_REPORT_LINES: tuple[tuple[str, bool, str], ...] = (
    ("Caixa e equivalente de caixa", False, "caixa"),
    ("Contas a Receber", False, "contas_receber"),
    ("Estoques", False, "estoques"),
    ("Ativo Circulante", True, "ativo_circulante"),
    ("Ativo Total", True, "ativo_total"),
    ("Passivo Circulante", True, "passivo_circulante"),
    ("Patrim.Líquido - atribuido aos controladores", True, "pl_controladores"),
    ("Patrimônio Líquido - Não Controladores", False, "pl_nao_controladores"),
)

DFC_REPORT_LINES: tuple[tuple[str, str, str, str], ...] = (
    (
        "dre",
        "Lucro antes I.R. Cont. Social",
        "Lucro antes dos tributos sobre o lucro",
        "lucro_antes_ir",
    ),
    (
        "dre",
        "Depreciação/Amortização/Exaustão",
        "Depreciação e amortização",
        "depreciacao",
    ),
)

COMPARATIVO_METRICS: tuple[tuple[str, str, str], ...] = (
    ("dre", "Receita Líquida", "receita_liquida"),
    ("ebitda", "EBITDA Ajustado", "ebitda"),
    ("ebitda", "Lucro (prejuízo) Líquido", "lucro_liquido"),
)

KPI_REPORT_LINES: tuple[tuple[str, str, str], ...] = (
    ("margem_bruta_pct", "Margem Bruta Consolidada", "percent"),
    ("margem_ebitda_pct", "Margem EBITDA Ajustada", "percent"),
    ("margem_liquida_pct", "Margem Líquida Final", "percent"),
    ("racio_admin_pct", "Peso Estrutura Administrativa (G&A / Rec. Bruta)", "percent"),
    ("giro_estoque", "Giro de Estoque Financeiro", "ratio"),
    ("score_industrial", "Score Industrial UNO", "score"),
)


def _row_values_for_periods(
    sheets: dict[str, pd.DataFrame],
    sheet_key: str,
    account: str,
    periods: list[str],
) -> list[float | None]:
    df = sheets[sheet_key]
    return [extract_value_safe(df, account, period) for period in periods]


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def build_comparativos_section(
    sheets: dict[str, pd.DataFrame],
    trimestres: tuple[str, ...] = DEFAULT_TRIMESTRES,
    competencia: str = DEFAULT_COMPETENCIA,
) -> dict[str, Any]:
    """Comparativos sequenciais (QoQ) e anuais (YoY) a partir dos periodos do Templates."""
    dre_periods = [*trimestres, competencia]
    linhas: list[dict[str, Any]] = []

    for sheet_key, account, conta_key in COMPARATIVO_METRICS:
        valores = _row_values_for_periods(sheets, sheet_key, account, dre_periods)
        for idx in range(1, len(dre_periods)):
            linhas.append(
                {
                    "indicador_key": conta_key,
                    "periodo_de": dre_periods[idx - 1],
                    "periodo_para": dre_periods[idx],
                    "valor_de": valores[idx - 1],
                    "valor_para": valores[idx],
                    "variacao_pct": _pct_change(valores[idx], valores[idx - 1]),
                    "tipo": "QoQ",
                }
            )

        if len(dre_periods) >= 2:
            ultimo_tri = dre_periods[-2]
            anual = dre_periods[-1]
            linhas.append(
                {
                    "indicador_key": conta_key,
                    "periodo_de": ultimo_tri,
                    "periodo_para": anual,
                    "valor_de": valores[-2],
                    "valor_para": valores[-1],
                    "variacao_pct": _pct_change(valores[-1], valores[-2]),
                    "tipo": "YoY",
                }
            )

    return {
        "id": "comparativos",
        "titulo": "Comparativos Históricos",
        "periodos": dre_periods,
        "linhas": linhas,
        "nota": "Variações percentuais entre trimestres (QoQ) e último trimestre vs ano (YoY).",
    }


def build_demonstracoes_relatorio(
    competencia: str = DEFAULT_COMPETENCIA,
    patrimonial: str = DEFAULT_PATRIMONIAL,
    trimestres: tuple[str, ...] = DEFAULT_TRIMESTRES,
) -> dict[str, Any] | None:
    """Monta tabelas DRE/Balanço/DFC/KPIs no layout do modelo Templates."""
    workbook = _find_workbook()
    if workbook is None:
        return None

    bundle = load_kpi_bundle(competencia=competencia, patrimonial=patrimonial)
    if bundle is None:
        return None

    mtime = workbook.stat().st_mtime
    path = str(workbook)
    sheets = {
        "dre": _load_sheet(path, mtime, SHEET_DRE),
        "balanco": _load_sheet(path, mtime, SHEET_BALANCO),
        "ebitda": _load_sheet(path, mtime, SHEET_EBITDA),
    }

    dre_periods = [*trimestres, competencia]
    dre_linhas = []
    for sheet_key, account, label, conta_key in DRE_REPORT_LINES:
        valores = _row_values_for_periods(sheets, sheet_key, account, dre_periods)
        dre_linhas.append(
            {
                "conta": label,
                "conta_key": conta_key,
                "valores": valores,
                "destaque": conta_key in {"lucro_bruto", "lucro_liquido", "ebitda"},
            }
        )

    bal_periods = [patrimonial]
    bal_linhas = []
    for account, destaque, conta_key in BALANCO_REPORT_LINES:
        valores = _row_values_for_periods(sheets, "balanco", account, bal_periods)
        bal_linhas.append(
            {"conta": account, "conta_key": conta_key, "valores": valores, "destaque": destaque}
        )

    dfc_periods = [competencia]
    dfc_linhas = []
    for sheet_key, account, label, conta_key in DFC_REPORT_LINES:
        valores = _row_values_for_periods(sheets, sheet_key, account, dfc_periods)
        dfc_linhas.append(
            {
                "conta": label,
                "conta_key": conta_key,
                "valores": valores,
                "destaque": conta_key == "lucro_antes_ir",
            }
        )

    comparativos = build_comparativos_section(sheets, trimestres, competencia)

    kpis = build_resumo_demonstracoes(competencia, patrimonial)
    kpi_data = (kpis or {}).get("kpis", {})
    kpi_linhas = []
    for key, label, unit in KPI_REPORT_LINES:
        value = kpi_data.get(key)
        kpi_linhas.append(
            {
                "conta": label,
                "conta_key": key,
                "valores": [value],
                "unit": unit,
                "destaque": key == "score_industrial",
            }
        )

    return {
        "titulo": "Resumo das Demonstrações Financeiras",
        "subtitulo": "Relatório Executivo — modelo Templates",
        "fonte": workbook.name,
        "unidade": "R$ milhões",
        "competencia": competencia,
        "patrimonial": patrimonial,
        "secoes": [
            {
                "id": "dre",
                "titulo": "Demonstração do Resultado do Exercício (DRE)",
                "periodos": dre_periods,
                "linhas": dre_linhas,
                "nota": "Valores em R$ milhões — trimestres e ano fiscal conforme Templates.",
            },
            {
                "id": "balanco",
                "titulo": "Balanço Patrimonial",
                "periodos": bal_periods,
                "linhas": bal_linhas,
                "nota": f"Valores em R$ milhões — posição {patrimonial}.",
            },
            {
                "id": "dfc",
                "titulo": "Demonstração de Fluxo de Caixa (DFC)",
                "periodos": dfc_periods,
                "linhas": dfc_linhas,
                "nota": f"Valores em R$ milhões — competência {competencia} (ajustes DRE/EBITDA).",
            },
            {
                "id": "kpis",
                "titulo": "Indicadores-Chave de Performance (KPIs)",
                "periodos": [competencia],
                "linhas": kpi_linhas,
                "nota": "Percentuais, múltiplos e score UNO conforme Templates/KPIs_Templates.md.",
            },
            comparativos,
        ],
    }


def _build_busca_inteligente(bundle: TemplateKPIBundle, kpis: dict[str, Any]) -> dict[str, Any]:
    resumo = build_resumo_demonstracoes(bundle.competencia, bundle.patrimonial) or {}
    dre = resumo.get("dre", {})
    bal = resumo.get("balanco", {})
    dfc = resumo.get("dfc", {})
    kpi = resumo.get("kpis", {})

    def money(value: float) -> str:
        return f"R$ {value:,.2f} mi"

    faq = [
        {
            "tags": ["receita", "faturamento", "vendas", "dre"],
            "resposta": (
                f"Receita liquida consolidada em {bundle.competencia}: {money(bundle.receita_liquida)} "
                f"(receita bruta {money(bundle.receita_bruta)}). Fonte: Templates/{bundle.workbook.name}."
            ),
        },
        {
            "tags": ["margem bruta", "lucro bruto", "cpv", "custo"],
            "resposta": (
                f"Margem bruta: {kpi.get('margem_bruta_pct', 0):.2f}% sobre receita liquida. "
                f"Lucro bruto DRE: {money(float(dre.get('lucro_bruto', 0)))}; CPV: {money(abs(bundle.custo_produtos))}."
            ),
        },
        {
            "tags": ["ebitda", "caixa operacional", "geracao"],
            "resposta": (
                f"EBITDA ajustado: {money(bundle.ebitda_ajustado)} "
                f"({bundle.margem_ebitda_pct:.2f}% da receita liquida)."
            ),
        },
        {
            "tags": ["margem liquida", "lucro liquido", "resultado"],
            "resposta": (
                f"Margem liquida: {bundle.margem_liquida_pct:.2f}%. "
                f"Lucro liquido: {money(bundle.lucro_liquido)}."
            ),
        },
        {
            "tags": ["administr", "ga", "estrutura", "backoffice"],
            "resposta": (
                f"Racio de custos administrativos: {bundle.racio_admin_pct:.2f}% "
                f"sobre receita bruta (despesas G&A {money(abs(bundle.despesas_admin))})."
            ),
        },
        {
            "tags": ["estoque", "giro", "cpv"],
            "resposta": (
                f"Giro de estoque financeiro: {bundle.giro_estoque:.2f}x "
                f"(CPV {money(abs(bundle.custo_produtos))} / estoques {money(bundle.estoques)} em {bundle.patrimonial})."
            ),
        },
        {
            "tags": ["caixa", "balanco", "disponibilidade", "liquidez"],
            "resposta": (
                f"Caixa e equivalentes ({bundle.patrimonial}): {money(float(bal.get('caixa_equivalentes', 0)))}. "
                f"Ativo circulante: {money(float(bal.get('ativo_circulante', 0)))}."
            ),
        },
        {
            "tags": ["receber", "clientes", "contas a receber"],
            "resposta": f"Contas a receber ({bundle.patrimonial}): {money(bundle.contas_receber)}.",
        },
        {
            "tags": ["fluxo", "dfc", "depreciacao", "amortizacao"],
            "resposta": (
                f"DFC {bundle.competencia}: lucro antes dos tributos {money(float(dfc.get('lucro_antes_tributos', 0)))}; "
                f"depreciacao/amortizacao {money(float(dfc.get('depreciacao_amortizacao', 0)))}."
            ),
        },
        {
            "tags": ["score", "uno", "industrial", "operacional"],
            "resposta": f"Score industrial UNO: {bundle.score_industrial:.1f}/100 com base nos KPIs do modelo Templates.",
        },
        {
            "tags": ["kpi", "indicador", "resumo", "demonstrac"],
            "resposta": (
                "KPIs consolidados (Templates): "
                + "; ".join(
                    f"{nome} {dados.get('resultado', 'n/d')}" for nome, dados in kpis.items()
                )
            ),
        },
    ]
    return {
        "ativo": True,
        "placeholder": "Pergunte ao UNO sobre a operacao...",
        "exemplos": [
            "Qual a margem EBITDA?",
            "Como esta o giro de estoque?",
            "Resumo do balanco patrimonial",
            "Qual o lucro liquido?",
        ],
        "faq": faq,
    }


def build_financial_summary_from_templates() -> dict[str, Any] | None:
    bundle = load_kpi_bundle()
    if bundle is None:
        return None

    return {
        "available": True,
        "source": "templates",
        "workbook": bundle.workbook.name,
        "dre": {
            "periodo": bundle.competencia,
            "receita_bruta": bundle.receita_bruta,
            "receita_liquida": bundle.receita_liquida,
            "lucro_bruto": bundle.lucro_bruto,
            "ebitda": bundle.ebitda_ajustado,
            "lucro_liquido": bundle.lucro_liquido,
            "margem_bruta_pct": bundle.margem_bruta_pct,
            "margem_liquida_pct": bundle.margem_liquida_pct,
            "margem_ebitda_pct": bundle.margem_ebitda_pct,
            "todos_periodos": list(DEFAULT_TRIMESTRES) + [bundle.competencia],
        },
        "balanco": {
            "periodo": bundle.patrimonial,
            "estoques": bundle.estoques,
            "contas_receber": bundle.contas_receber,
        },
        "kpis_template": {
            "racio_admin_pct": bundle.racio_admin_pct,
            "giro_estoque": bundle.giro_estoque,
            "score_industrial": bundle.score_industrial,
        },
    }
