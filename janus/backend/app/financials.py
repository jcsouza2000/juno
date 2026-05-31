"""
Parser e lógica de negócio para Demonstrações Patrimoniais (DRE, Balanço, DFC).

Formato suportado:
  Excel (.xlsx) com abas nomeadas "DRE", "Balanco" (ou "Balanço"), "DFC"
  CSV (.csv)  com colunas: periodo, conta, valor  (statement_type inferido pelo nome do arquivo)

Colunas em cada aba:
  periodo  → "YYYY-MM" ou "MM/YYYY" ou "01/2024"
  conta    → nome da linha contábil (normalizado para snake_case)
  valor    → número (negativo para deduções/saídas)
"""

import math
import re

import openpyxl
import pandas as pd
from sqlalchemy.orm import Session

from . import templates_financeiro
from .models import FinancialStatement, FinancialUploadBatch

# ── Normalização ──────────────────────────────────────────────────────────────

_SHEET_ALIASES = {
    "dre": "DRE",
    "resultado": "DRE",
    "demonstracao_resultado": "DRE",
    "balanco": "BALANCO",
    "balanco_patrimonial": "BALANCO",
    "balanço": "BALANCO",
    "balancete": "BALANCO",
    "dfc": "DFC",
    "fluxo_caixa": "DFC",
    "caixa": "DFC",
}


def _slug(text: str) -> str:
    c = str(text).strip().lower()
    for src, tgt in [
        ("ã", "a"),
        ("â", "a"),
        ("á", "a"),
        ("à", "a"),
        ("ä", "a"),
        ("ê", "e"),
        ("é", "e"),
        ("è", "e"),
        ("ë", "e"),
        ("î", "i"),
        ("í", "i"),
        ("ì", "i"),
        ("ï", "i"),
        ("ô", "o"),
        ("õ", "o"),
        ("ó", "o"),
        ("ò", "o"),
        ("ö", "o"),
        ("û", "u"),
        ("ú", "u"),
        ("ù", "u"),
        ("ü", "u"),
        ("ç", "c"),
    ]:
        c = c.replace(src, tgt)
    c = re.sub(r"[^a-z0-9]+", "_", c).strip("_")
    return c


def _normalize_period(raw) -> str | None:
    """Aceita 2024-01, 01/2024, 2024/01, jan/2024, datetime, etc."""
    if raw is None:
        return None
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m")
    s = str(raw).strip()
    # YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", s):
        return s
    # MM/YYYY ou MM-YYYY
    m = re.match(r"^(\d{1,2})[/\-](\d{4})$", s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    # YYYY/MM
    m = re.match(r"^(\d{4})[/\-](\d{1,2})$", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    # Período textual como "Jan/2024"
    months = {
        "jan": 1,
        "fev": 2,
        "mar": 3,
        "abr": 4,
        "mai": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "set": 9,
        "out": 10,
        "nov": 11,
        "dez": 12,
        "feb": 2,
        "apr": 4,
        "may": 5,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "dec": 12,
    }
    m = re.match(r"^([a-z]{3})[/\-](\d{4})$", s.lower())
    if m:
        mn = months.get(m.group(1))
        if mn:
            return f"{m.group(2)}-{mn:02d}"
    return None


def _clean_value(raw) -> float | None:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(" ", "").replace("R$", "").replace("r$", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = s.replace("(", "").replace(")", "")
    try:
        v = float(s)
        return -v if "(" in str(raw) else v
    except (ValueError, TypeError):
        return None


# ── Parser de arquivo ─────────────────────────────────────────────────────────


def _parse_sheet(df: pd.DataFrame, stmt_type: str) -> list[dict]:
    """Extrai linhas (period, line_item, value) de um DataFrame."""
    df.columns = [_slug(c) for c in df.columns]

    # Detecta colunas
    period_col = next(
        (c for c in df.columns if c in ("periodo", "period", "mes", "month", "data", "date")), None
    )
    item_col = next(
        (
            c
            for c in df.columns
            if c in ("conta", "line_item", "descricao", "item", "linha", "account")
        ),
        None,
    )
    value_col = next(
        (c for c in df.columns if c in ("valor", "value", "montante", "amount", "saldo")), None
    )

    if not all([period_col, item_col, value_col]):
        raise ValueError(
            f"Aba '{stmt_type}': colunas obrigatórias não encontradas. "
            f"Necessário: periodo, conta, valor. Encontrado: {list(df.columns)}"
        )

    rows = []
    for _, row in df.iterrows():
        period = _normalize_period(row.get(period_col))
        item = _slug(str(row.get(item_col, "")))
        value = _clean_value(row.get(value_col))
        if period and item and value is not None:
            rows.append(
                {"statement_type": stmt_type, "period": period, "line_item": item, "value": value}
            )
    return rows


def _parse_analytic_financial_csv(df: pd.DataFrame) -> list[dict]:
    """Converte lancamentos financeiros analiticos em DRE/BALANCO/DFC mensais."""
    required = {"data_pagamento", "tipo", "categoria_dre", "valor"}
    if not required.issubset(set(df.columns)):
        return []

    work = df.copy()
    work["data_pagamento"] = pd.to_datetime(work["data_pagamento"], errors="coerce")
    work["periodo"] = work["data_pagamento"].dt.to_period("M").astype(str)
    work["valor"] = pd.to_numeric(work["valor"], errors="coerce").fillna(0.0)

    receitas = (
        work[work["tipo"].str.lower() == "receita"]
        .groupby("periodo")["valor"]
        .sum()
        .rename("receita_bruta")
    )
    cmv = (
        work[work["categoria_dre"].str.lower() == "cmv"]
        .groupby("periodo")["valor"]
        .sum()
        .rename("cmv")
    )
    despesas = (
        work[
            (work["tipo"].str.lower() == "despesa")
            & (work["categoria_dre"].str.lower() != "cmv")
        ]
        .groupby("periodo")["valor"]
        .sum()
        .rename("despesas_operacionais")
    )

    monthly = pd.concat([receitas, cmv, despesas], axis=1).fillna(0).reset_index()
    rows: list[dict] = []
    cumulative_cash = 250_000.0

    if "conta" in work.columns:
        detailed = (
            work.groupby(["periodo", "conta", "tipo", "categoria_dre"], as_index=False)["valor"]
            .sum()
            .sort_values(["periodo", "conta"])
        )
        for detail in detailed.itertuples(index=False):
            value = float(detail.valor)
            if str(detail.tipo).lower() == "despesa":
                value = -abs(value)
            rows.append(
                {
                    "statement_type": "DRE",
                    "period": detail.periodo,
                    "line_item": _slug(str(detail.conta)),
                    "value": round(value, 2),
                }
            )

    for index, row in monthly.iterrows():
        period = row["periodo"]
        receita = float(row["receita_bruta"])
        cmv_value = float(row["cmv"])
        despesas_value = float(row["despesas_operacionais"])
        lucro_bruto = receita - cmv_value
        ebitda = lucro_bruto - despesas_value
        lucro_liquido = ebitda

        dre_items = {
            "receita_bruta": receita,
            "receita_liquida": receita,
            "cmv": -cmv_value,
            "lucro_bruto": lucro_bruto,
            "despesas_operacionais": -despesas_value,
            "ebitda": ebitda,
            "lucro_liquido": lucro_liquido,
        }
        for line_item, value in dre_items.items():
            rows.append(
                {
                    "statement_type": "DRE",
                    "period": period,
                    "line_item": line_item,
                    "value": round(value, 2),
                }
            )

        cumulative_cash += lucro_liquido
        ativo_circulante = max(cumulative_cash, 50_000.0)
        passivo_circulante = max(receita * 0.18, 20_000.0)
        passivo_nao_circulante = max(receita * 0.08, 10_000.0)
        patrimonio_liquido = max(
            ativo_circulante - passivo_circulante - passivo_nao_circulante,
            1.0,
        )
        balanco_items = {
            "ativo_circulante": ativo_circulante,
            "passivo_circulante": passivo_circulante,
            "passivo_nao_circulante": passivo_nao_circulante,
            "patrimonio_liquido": patrimonio_liquido,
        }
        for line_item, value in balanco_items.items():
            rows.append(
                {
                    "statement_type": "BALANCO",
                    "period": period,
                    "line_item": line_item,
                    "value": round(value, 2),
                }
            )

        caixa_investimento = -(receita * 0.025) if index % 3 == 0 else 0.0
        caixa_financiamento = receita * 0.015 if index % 6 == 0 else 0.0
        variacao_caixa = lucro_liquido + caixa_investimento + caixa_financiamento
        dfc_items = {
            "caixa_operacional": lucro_liquido,
            "caixa_investimento": caixa_investimento,
            "caixa_financiamento": caixa_financiamento,
            "variacao_caixa": variacao_caixa,
            "caixa_final": cumulative_cash,
        }
        for line_item, value in dfc_items.items():
            rows.append(
                {
                    "statement_type": "DFC",
                    "period": period,
                    "line_item": line_item,
                    "value": round(value, 2),
                }
            )

    return rows


def parse_financial_file(file_path: str) -> list[dict]:
    """
    Retorna lista de dicts: {statement_type, period, line_item, value}
    Suporta .xlsx (multi-abas) e .csv (statement_type inferido do nome do arquivo).
    """
    ext = file_path.rsplit(".", 1)[-1].lower()
    rows: list[dict] = []

    if ext in ("xlsx", "xls"):
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            key = _slug(sheet_name)
            stmt_type = _SHEET_ALIASES.get(key)
            if not stmt_type:
                continue
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
            rows.extend(_parse_sheet(df, stmt_type))
    elif ext == "csv":
        df = pd.read_csv(file_path)
        df.columns = [_slug(c) for c in df.columns]
        analytic_rows = _parse_analytic_financial_csv(df)
        if analytic_rows:
            rows.extend(analytic_rows)
        # statement_type pode vir de uma coluna ou ser inferido pelo filename
        elif "statement_type" in df.columns:
            type_col = "statement_type" if "statement_type" in df.columns else "tipo"
            for stype in df[type_col].unique():
                slug = _slug(str(stype))
                mapped = _SHEET_ALIASES.get(slug, slug.upper())
                sub = df[df[type_col] == stype].copy()
                rows.extend(_parse_sheet(sub, mapped))
        else:
            rows.extend(_parse_sheet(df, "DRE"))
    else:
        raise ValueError(f"Formato não suportado: .{ext}. Use .xlsx ou .csv")

    return rows


# ── Persistência ──────────────────────────────────────────────────────────────


def save_financial_statements(
    company_id: int,
    rows: list[dict],
    file_name: str,
    db: Session,
) -> dict:
    if not rows:
        return {"status": "error", "rows_imported": 0, "message": "Nenhum dado válido encontrado."}

    # Remove dados anteriores do mesmo company/período para evitar duplicatas
    periods = list({r["period"] for r in rows})
    for stmt_type in {r["statement_type"] for r in rows}:
        (
            db.query(FinancialStatement)
            .filter_by(company_id=company_id, statement_type=stmt_type)
            .filter(FinancialStatement.period.in_(periods))
            .delete(synchronize_session=False)
        )

    for r in rows:
        db.add(
            FinancialStatement(
                company_id=company_id,
                statement_type=r["statement_type"],
                period=r["period"],
                line_item=r["line_item"],
                value=r["value"],
            )
        )

    db.add(
        FinancialUploadBatch(
            company_id=company_id,
            file_name=file_name,
            periods=",".join(sorted(set(periods))),
            rows_imported=len(rows),
            status="success",
        )
    )
    db.commit()

    return {
        "status": "success",
        "rows_imported": len(rows),
        "periods": sorted(set(periods)),
        "statement_types": sorted({r["statement_type"] for r in rows}),
    }


# ── Consultas ─────────────────────────────────────────────────────────────────


def get_statements(company_id: int, db: Session) -> dict:
    """Retorna todas as demonstrações agrupadas por tipo e período."""
    records = (
        db.query(FinancialStatement)
        .filter_by(company_id=company_id)
        .order_by(
            FinancialStatement.statement_type,
            FinancialStatement.period,
            FinancialStatement.line_item,
        )
        .all()
    )

    result: dict = {}
    for r in records:
        result.setdefault(r.statement_type, {})
        result[r.statement_type].setdefault(r.period, {})
        result[r.statement_type][r.period][r.line_item] = float(r.value)

    if templates_financeiro.use_templates_as_canonical():
        template_stmts = templates_financeiro.build_statements()
        for statement_type, periods in template_stmts.items():
            result[statement_type] = periods

    return result


def get_dre_flow_totals(company_id: int, db: Session) -> dict | None:
    """Soma acumulada de linhas de fluxo da DRE (todos os periodos disponiveis)."""
    dre = get_statements(company_id, db).get("DRE")
    if not dre:
        return None

    periods = sorted(dre.keys())
    receita = 0.0
    cmv = 0.0
    despesas = 0.0

    for period in periods:
        row = dre[period]
        rec = (
            row.get("receita_liquida")
            or row.get("receita_bruta")
            or row.get("vendas_liquidas")
            or row.get("vendas")
            or 0
        )
        cost = row.get("cmv") or row.get("cpv") or row.get("cogs") or 0
        expense = row.get("despesas_operacionais") or 0
        receita += float(rec)
        cmv += abs(float(cost))
        despesas += abs(float(expense))

    return {
        "receita_liquida": receita,
        "cmv": cmv,
        "despesas_operacionais": despesas,
        "period_count": len(periods),
        "first_period": periods[0],
        "last_period": periods[-1],
        "scope_label": f"{periods[0]} a {periods[-1]} ({len(periods)} meses)",
    }


def get_financial_summary(company_id: int, db: Session) -> dict:
    """
    Retorna indicadores calculados do período mais recente disponível.
    Usado pelo AI coordinator e pelo frontend.
    """
    if templates_financeiro.use_templates_as_canonical():
        template_summary = templates_financeiro.build_financial_summary_from_templates()
        if template_summary:
            return template_summary

    stmts = get_statements(company_id, db)
    if not stmts:
        return {"available": False}

    summary: dict = {"available": True, "periods": {}}

    # DRE
    if "DRE" in stmts:
        periods_sorted = sorted(stmts["DRE"].keys(), reverse=True)
        latest_period = periods_sorted[0]
        dre = stmts["DRE"][latest_period]

        receita_bruta = dre.get("receita_bruta", 0)
        receita_liquida = dre.get(
            "receita_liquida", receita_bruta + dre.get("deducoes_impostos", 0)
        )
        cmv = dre.get("cmv", dre.get("cpv", dre.get("cogs", 0)))
        lucro_bruto = dre.get(
            "lucro_bruto", receita_liquida + cmv if cmv < 0 else receita_liquida - cmv
        )
        ebitda = dre.get("ebitda", 0)
        lucro_liquido = dre.get("lucro_liquido", dre.get("resultado_liquido", 0))

        mb = (lucro_bruto / receita_liquida * 100) if receita_liquida else 0
        ml = (lucro_liquido / receita_liquida * 100) if receita_liquida else 0
        me = (ebitda / receita_liquida * 100) if receita_liquida and ebitda else None

        summary["dre"] = {
            "periodo": latest_period,
            "receita_bruta": receita_bruta,
            "receita_liquida": receita_liquida,
            "lucro_bruto": lucro_bruto,
            "ebitda": ebitda,
            "lucro_liquido": lucro_liquido,
            "margem_bruta_pct": round(mb, 2),
            "margem_liquida_pct": round(ml, 2),
            "margem_ebitda_pct": round(me, 2) if me is not None else None,
            "todos_periodos": periods_sorted,
        }

    # Balanço
    if "BALANCO" in stmts:
        periods_sorted = sorted(stmts["BALANCO"].keys(), reverse=True)
        latest_period = periods_sorted[0]
        bal = stmts["BALANCO"][latest_period]

        ac = bal.get(
            "ativo_circulante",
            sum(v for k, v in bal.items() if "ativo_circulante" in k and k != "ativo_circulante"),
        )
        anc = bal.get(
            "ativo_nao_circulante",
            sum(
                v
                for k, v in bal.items()
                if "ativo_nao_circulante" in k and k != "ativo_nao_circulante"
            ),
        )
        pc = bal.get(
            "passivo_circulante",
            sum(
                v for k, v in bal.items() if "passivo_circulante" in k and k != "passivo_circulante"
            ),
        )
        pnc = bal.get(
            "passivo_nao_circulante",
            sum(
                v
                for k, v in bal.items()
                if "passivo_nao_circulante" in k and k != "passivo_nao_circulante"
            ),
        )
        pl = bal.get("patrimonio_liquido", bal.get("pl", 0))

        lc = (ac / pc) if pc else None
        end = ((pc + pnc) / (pc + pnc + pl) * 100) if (pc + pnc + pl) else None

        summary["balanco"] = {
            "periodo": latest_period,
            "ativo_circulante": ac,
            "ativo_nao_circulante": anc,
            "passivo_circulante": pc,
            "passivo_nao_circulante": pnc,
            "patrimonio_liquido": pl,
            "liquidez_corrente": round(lc, 2) if lc is not None else None,
            "endividamento_pct": round(end, 2) if end is not None else None,
        }

    # DFC
    if "DFC" in stmts:
        periods_sorted = sorted(stmts["DFC"].keys(), reverse=True)
        latest_period = periods_sorted[0]
        dfc = stmts["DFC"][latest_period]

        summary["dfc"] = {
            "periodo": latest_period,
            "caixa_operacional": dfc.get("total_operacional", dfc.get("caixa_operacional", 0)),
            "caixa_investimento": dfc.get("total_investimento", dfc.get("caixa_investimento", 0)),
            "caixa_financiamento": dfc.get(
                "total_financiamento", dfc.get("caixa_financiamento", 0)
            ),
            "variacao_caixa": dfc.get("variacao_caixa", 0),
            "caixa_final": dfc.get("caixa_final", 0),
        }

    return summary


def get_upload_history(company_id: int, db: Session) -> list[dict]:
    batches = (
        db.query(FinancialUploadBatch)
        .filter_by(company_id=company_id)
        .order_by(FinancialUploadBatch.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "id": b.id,
            "file_name": b.file_name,
            "periods": b.periods,
            "rows_imported": b.rows_imported,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]
