"""Resumo das demonstracoes financeiras e KPIs a partir de Templates/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "janus" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.templates_financeiro import (  # noqa: E402
    build_resumo_demonstracoes,
    templates_available,
)


def main() -> None:
    if not templates_available():
        raise FileNotFoundError(f"Planilha modelo nao encontrada em {ROOT / 'Templates'}")

    resumo = build_resumo_demonstracoes()
    if not resumo:
        raise RuntimeError("Nao foi possivel montar o resumo a partir de Templates.")

    dre = resumo["dre"]
    bal = resumo["balanco"]
    dfc = resumo["dfc"]
    kpis = resumo["kpis"]

    print("=================================================================================")
    print("   JUNO_AI (UNO) - DATA ENGINE: ESTRUTURA PARA CARGA DO DASHBOARD (ABA UNICA)")
    print("=================================================================================\n")
    print(f"Fonte: {resumo['fonte']} | Unidade: {resumo['unidade']}")
    print(f"Competencia DRE/DFC/KPIs: {resumo['competencia']} | Balanco: {resumo['patrimonial']}\n")

    print("CONTEXTO 1: RESUMO DRE (R$ Milhoes)")
    print(f"   Receita Bruta: R$ {dre['receita_bruta']:,.2f}")
    print(f"   Receita Liquida: R$ {dre['receita_liquida']:,.2f}")
    print(f"   Custo dos Produtos Vendidos (CPV): R$ {dre['cpv']:,.2f}")
    print(f"   Lucro Bruto Operacional: R$ {dre['lucro_bruto']:,.2f}\n")

    print("CONTEXTO 2: RESUMO BALANCO PATRIMONIAL (R$ Milhoes - Posicao 4T25)")
    print(f"   Disponibilidades (Caixa e Equivalentes): R$ {bal['caixa_equivalentes']:,.2f}")
    print(f"   Contas a Receber de Clientes: R$ {bal['contas_receber']:,.2f}")
    print(f"   Estoques Imobilizados em Giro: R$ {bal['estoques']:,.2f}")
    print(f"   Total do Ativo Circulante: R$ {bal['ativo_circulante']:,.2f}\n")

    print("CONTEXTO 3: RESUMO FLUXO DE CAIXA (R$ Milhoes / Ajustes)")
    print(f"   Resultado Antes dos Tributos: R$ {dfc['lucro_antes_tributos']:,.2f}")
    print(f"   (+) Reincorporacao de Depreciacao/Amortizacao: R$ {dfc['depreciacao_amortizacao']:,.2f}\n")

    print("CONTEXTO 4: INDICADORES CHAVE DE PERFORMANCE (KPIs)")
    print(f"   Margem Bruta Consolidada: {kpis['margem_bruta_pct']:.2f}%")
    print(f"   Margem EBITDA Ajustada: {kpis['margem_ebitda_pct']:.2f}%")
    print(f"   Margem Liquida Final: {kpis['margem_liquida_pct']:.2f}%")
    print(f"   Peso da Estrutura Administrativa (G&A / Rec. Bruta): {kpis['racio_admin_pct']:.2f}%")
    print(f"   Giro de Estoque Financeiro: {kpis['giro_estoque']:.2f}x no periodo")
    print(f"   Score Industrial UNO: {kpis['score_industrial']:.1f}/100")
    print("=================================================================================")


if __name__ == "__main__":
    main()
