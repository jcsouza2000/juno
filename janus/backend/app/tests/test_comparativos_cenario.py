"""Testes dos comparativos por cenario (Fase C)."""

from __future__ import annotations

from app.comparativos_cenario import CENARIOS, build_comparativos_cenario
from app.financials import save_financial_statements
from app.models import Company


def _seed_financial(db, name: str = "Cenario Co") -> int:
    c = Company(name=name, sector="industria")
    db.add(c)
    db.flush()
    cid = c.id
    rows = [
        {
            "statement_type": "DRE",
            "period": "2026-05",
            "line_item": "receita_liquida",
            "value": 1000.0,
        },
        {
            "statement_type": "DRE",
            "period": "2026-05",
            "line_item": "ebitda",
            "value": 200.0,
        },
        {
            "statement_type": "DRE",
            "period": "2026-05",
            "line_item": "lucro_liquido",
            "value": 120.0,
        },
    ]
    save_financial_statements(cid, rows, "cenario.csv", db)
    db.commit()
    return cid


def test_build_comparativos_cenario_quatro_colunas(db_session):
    cid = _seed_financial(db_session)
    section = build_comparativos_cenario(cid, db_session)

    assert section["id"] == "comparativos_cenario"
    assert section["cenarios"] == list(CENARIOS)
    assert len(section["linhas"]) == 4

    receita = next(ln for ln in section["linhas"] if ln["indicador_key"] == "receita_liquida")
    assert receita["valores"]["REALIZADO"] == 1000.0
    assert receita["valores"]["ORCAMENTO"] is not None
    assert receita["valores"]["PROJECAO"] is not None
    assert "variacao_vs_realizado_pct" in receita

    ev = next(ln for ln in section["linhas"] if ln["indicador_key"] == "enterprise_value")
    assert ev["valores"]["REALIZADO"] is None
    assert ev["valores"]["VALUATION"] is not None
