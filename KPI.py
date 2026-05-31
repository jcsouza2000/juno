"""Calcula KPIs financeiros a partir das demonstracoes em Templates/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "janus" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.templates_financeiro import (  # noqa: E402
    DEFAULT_COMPETENCIA,
    load_kpi_bundle,
    templates_available,
)


def calcular_painel_kpis(periodo: str = DEFAULT_COMPETENCIA) -> None:
    if not templates_available():
        raise FileNotFoundError(f"Planilha nao encontrada em {ROOT / 'Templates'}")

    bundle = load_kpi_bundle(competencia=periodo)
    if bundle is None:
        raise FileNotFoundError("Nao foi possivel carregar KPIs do modelo Templates.")

    print(f"\n=== RELATÓRIO DE KPIs FINANCEIROS E ADMINISTRATIVOS — PERÍODO: {periodo} ===")
    print(f"Fonte: {bundle.workbook.name}")
    print(f"Modelo: Templates/KPIs_Templates.md")
    print(f"Unidade da planilha: R$ milhões\n")

    print("--------------------------------------------------")
    print("KPI: Margem Bruta")
    print("Fórmula: ((Receita Líquida + CPV) / Receita Líquida) * 100")
    print(
        f"Valores Aplicados: Receita Líq: {bundle.receita_liquida:,.2f} | "
        f"CPV: {bundle.custo_produtos:,.2f}"
    )
    print(f"Resultado: {bundle.margem_bruta_pct:.2f}%")

    print("--------------------------------------------------")
    print("KPI: Margem Líquida")
    print("Fórmula: (Lucro Líquido / Receita Líquida) * 100")
    print(
        f"Valores Aplicados: Lucro Líq: {bundle.lucro_liquido:,.2f} | "
        f"Receita Líq: {bundle.receita_liquida:,.2f}"
    )
    print(f"Resultado: {bundle.margem_liquida_pct:.2f}%")

    print("--------------------------------------------------")
    print("KPI: Margem EBITDA Ajustada")
    print("Fórmula: (EBITDA Ajustado / Receita Líquida) * 100")
    print(
        f"Valores Aplicados: EBITDA Ajustado: {bundle.ebitda_ajustado:,.2f} | "
        f"Receita Líq: {bundle.receita_liquida:,.2f}"
    )
    print(f"Resultado: {bundle.margem_ebitda_pct:.2f}%")

    print("--------------------------------------------------")
    print("KPI: Rácio de Custo Administrativo")
    print("Fórmula: (Despesas Administrativas / Receita Bruta) * 100")
    print(
        f"Valores Aplicados: Desp Admin: {abs(bundle.despesas_admin):,.2f} | "
        f"Receita Bruta: {bundle.receita_bruta:,.2f}"
    )
    print(f"Resultado: {bundle.racio_admin_pct:.2f}%")
    print("--------------------------------------------------")


if __name__ == "__main__":
    calcular_painel_kpis(periodo=DEFAULT_COMPETENCIA)
