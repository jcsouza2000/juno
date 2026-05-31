"""Gera CSVs brutos do piloto Juno (clientes, produtos, vendas, OPs, financeiro analitico)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "janus" / "backend"
OUTPUT_DIR = BASE_DIR / "uploads_piloto_juno"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.templates_financeiro import DEFAULT_COMPETENCIA, load_kpi_bundle  # noqa: E402

# Planilha Templates usa valores em R$ mil (cabecalho milhoes, celulas em mil).
TEMPLATE_MIL_TO_REAIS = 1000.0
PILOT_ANCHOR_YEAR = int(DEFAULT_COMPETENCIA)
PRODUCT_CATEGORIES = ["Metalmecânica", "Plásticos", "Eletrônicos", "Embalagens", "Químicos"]

# Plano de contas analitico (codigo hierarquico + mapeamento DRE)
REVENUE_ACCOUNTS = {
    category: {
        "codigo_conta": f"3.01.{index:03d}",
        "conta": f"Receita de Vendas - {category}",
        "grupo_dre": "Receitas Operacionais",
        "tipo": "Receita",
        "categoria_dre": "Faturamento de Vendas",
    }
    for index, category in enumerate(PRODUCT_CATEGORIES, start=1)
}

CMV_ACCOUNTS = {
    category: {
        "codigo_conta": f"4.01.{index:03d}",
        "conta": f"CMV - {category}",
        "grupo_dre": "Custos dos Produtos Vendidos",
        "tipo": "Despesa",
        "categoria_dre": "CMV",
    }
    for index, category in enumerate(PRODUCT_CATEGORIES, start=1)
}

FIXED_EXPENSE_ACCOUNTS = [
    {
        "codigo_conta": "5.01.001",
        "conta": "Salarios e Ordenados CLT",
        "grupo_dre": "Despesas com Pessoal",
        "tipo": "Despesa",
        "categoria_dre": "Folha de Pagamento",
        "peso": 0.42,
    },
    {
        "codigo_conta": "5.01.002",
        "conta": "Encargos Sociais FGTS/INSS",
        "grupo_dre": "Despesas com Pessoal",
        "tipo": "Despesa",
        "categoria_dre": "Folha de Pagamento",
        "peso": 0.18,
    },
    {
        "codigo_conta": "5.01.003",
        "conta": "Pro-labore Administrativo",
        "grupo_dre": "Despesas com Pessoal",
        "tipo": "Despesa",
        "categoria_dre": "Folha de Pagamento",
        "peso": 0.10,
    },
    {
        "codigo_conta": "5.02.001",
        "conta": "Aluguel e Condominio",
        "grupo_dre": "Despesas Ocupacionais",
        "tipo": "Despesa",
        "categoria_dre": "Custos Ocupacionais",
        "peso": 0.08,
    },
    {
        "codigo_conta": "5.02.002",
        "conta": "Energia Eletrica e Utilidades",
        "grupo_dre": "Despesas Ocupacionais",
        "tipo": "Despesa",
        "categoria_dre": "Custos Ocupacionais",
        "peso": 0.04,
    },
    {
        "codigo_conta": "5.03.001",
        "conta": "Marketing Digital e Feiras",
        "grupo_dre": "Despesas Comerciais",
        "tipo": "Despesa",
        "categoria_dre": "Marketing e Vendas",
        "peso": 0.05,
    },
    {
        "codigo_conta": "5.03.002",
        "conta": "Comissoes e Bonificacoes de Vendas",
        "grupo_dre": "Despesas Comerciais",
        "tipo": "Despesa",
        "categoria_dre": "Marketing e Vendas",
        "peso": 0.03,
    },
    {
        "codigo_conta": "5.04.001",
        "conta": "Software ERP e Ferramentas SaaS",
        "grupo_dre": "Despesas Administrativas",
        "tipo": "Despesa",
        "categoria_dre": "Despesas Administrativas (Software/SaaS)",
        "peso": 0.035,
    },
    {
        "codigo_conta": "5.04.002",
        "conta": "Contabilidade e Assessoria Juridica",
        "grupo_dre": "Despesas Administrativas",
        "tipo": "Despesa",
        "categoria_dre": "Despesas Administrativas (Software/SaaS)",
        "peso": 0.025,
    },
    {
        "codigo_conta": "5.04.003",
        "conta": "Material de Escritorio e Viagens",
        "grupo_dre": "Despesas Administrativas",
        "tipo": "Despesa",
        "categoria_dre": "Despesas Administrativas (Software/SaaS)",
        "peso": 0.015,
    },
    {
        "codigo_conta": "5.05.001",
        "conta": "PIS sobre Faturamento",
        "grupo_dre": "Impostos sobre Vendas",
        "tipo": "Despesa",
        "categoria_dre": "Impostos sobre Vendas",
        "peso": 0.0165,
    },
    {
        "codigo_conta": "5.05.002",
        "conta": "COFINS sobre Faturamento",
        "grupo_dre": "Impostos sobre Vendas",
        "tipo": "Despesa",
        "categoria_dre": "Impostos sobre Vendas",
        "peso": 0.076,
    },
]

FIXED_EXPENSE_BASE = 68_500.0  # base mensal antes de variacao (anos fora do ancora Templates)


def _load_template_targets() -> dict[str, float]:
    bundle = load_kpi_bundle(competencia=str(PILOT_ANCHOR_YEAR))
    if bundle is None:
        raise FileNotFoundError(
            f"Planilha Templates nao encontrada em {BASE_DIR / 'Templates'}. "
            "Necessaria para ancorar o piloto nas demonstracoes financeiras."
        )

    receita_liquida = round(bundle.receita_liquida * TEMPLATE_MIL_TO_REAIS, 2)
    receita_bruta = round(bundle.receita_bruta * TEMPLATE_MIL_TO_REAIS, 2)
    cmv = round(abs(bundle.custo_produtos) * TEMPLATE_MIL_TO_REAIS, 2)
    lucro_liquido = round(bundle.lucro_liquido * TEMPLATE_MIL_TO_REAIS, 2)
    despesas_admin = round(abs(bundle.despesas_admin) * TEMPLATE_MIL_TO_REAIS, 2)
    lucro_bruto = round(receita_liquida - cmv, 2)
    opex_total = round(lucro_bruto - lucro_liquido, 2)

    return {
        "fonte": bundle.workbook.name,
        "competencia": str(PILOT_ANCHOR_YEAR),
        "unidade_planilha": "R$ mil",
        "receita_liquida": receita_liquida,
        "receita_bruta": receita_bruta,
        "cmv": cmv,
        "lucro_bruto": lucro_bruto,
        "lucro_liquido": lucro_liquido,
        "despesas_admin": despesas_admin,
        "opex_total": opex_total,
        "margem_bruta_pct": bundle.margem_bruta_pct,
        "margem_liquida_pct": bundle.margem_liquida_pct,
        "margem_ebitda_pct": bundle.margem_ebitda_pct,
    }


def _anchor_vendas_to_template(df_vendas: pd.DataFrame, targets: dict[str, float]) -> pd.DataFrame:
    vendas = df_vendas.copy()
    mask = (pd.to_datetime(vendas["data_emissao"]).dt.year == PILOT_ANCHOR_YEAR) & (
        vendas["status"] == "Faturado"
    )
    if not mask.any():
        raise ValueError(f"Sem vendas faturadas em {PILOT_ANCHOR_YEAR} para ancoragem.")

    receita_atual = float(vendas.loc[mask, "total"].sum())
    cmv_atual = float(vendas.loc[mask, "custo_total_item"].sum())
    if receita_atual <= 0 or cmv_atual <= 0:
        raise ValueError("Receita ou CMV do ano ancora invalidos para proporcao.")

    fator_receita = targets["receita_liquida"] / receita_atual
    fator_cmv = targets["cmv"] / cmv_atual

    vendas.loc[mask, "total"] = (vendas.loc[mask, "total"] * fator_receita).round(2)
    vendas.loc[mask, "custo_total_item"] = (vendas.loc[mask, "custo_total_item"] * fator_cmv).round(2)
    return vendas


def _validate_template_alignment(
    df_vendas: pd.DataFrame,
    df_financeiro: pd.DataFrame,
    targets: dict[str, float],
) -> None:
    mask = (pd.to_datetime(df_vendas["data_emissao"]).dt.year == PILOT_ANCHOR_YEAR) & (
        df_vendas["status"] == "Faturado"
    )
    fin = df_financeiro.copy()
    fin["ano"] = pd.to_datetime(fin["data_pagamento"]).dt.year
    fin_ano = fin[fin["ano"] == PILOT_ANCHOR_YEAR]

    receita_pedidos = round(float(df_vendas.loc[mask, "total"].sum()), 2)
    receita_fin = round(float(fin_ano[fin_ano["tipo"].str.lower() == "receita"]["valor"].sum()), 2)
    cmv_pedidos = round(float(df_vendas.loc[mask, "custo_total_item"].sum()), 2)
    cmv_fin = round(float(fin_ano[fin_ano["categoria_dre"].str.lower() == "cmv"]["valor"].sum()), 2)
    despesas_fin = round(
        float(
            fin_ano[
                (fin_ano["tipo"].str.lower() == "despesa") & (fin_ano["categoria_dre"].str.lower() != "cmv")
            ]["valor"].sum()
        ),
        2,
    )

    tolerancia = 1.0
    checks = [
        ("receita_liquida", receita_pedidos, targets["receita_liquida"]),
        ("cmv", cmv_pedidos, targets["cmv"]),
        ("receita_financeiro", receita_fin, targets["receita_liquida"]),
        ("cmv_financeiro", cmv_fin, targets["cmv"]),
        ("despesas_operacionais", despesas_fin, targets["opex_total"]),
    ]
    divergencias = []
    for nome, atual, alvo in checks:
        if abs(atual - alvo) > tolerancia:
            divergencias.append(f"{nome}: atual={atual:,.2f} alvo={alvo:,.2f}")

    if divergencias:
        raise ValueError(
            "Piloto nao fechou com Templates "
            f"({targets['fonte']}, {PILOT_ANCHOR_YEAR}): " + "; ".join(divergencias)
        )


def _validate_unique(df: pd.DataFrame, column: str, label: str) -> None:
    duplicates = int(df[column].duplicated().sum())
    if duplicates:
        raise ValueError(f"{label}: {duplicates} IDs duplicados na coluna '{column}'.")


def _append_lancamento(
    entries: list[dict],
    lancamento_id: int,
    *,
    data_pagamento: str,
    account: dict,
    valor: float,
    centro_custo: str,
    documento_origem: str,
) -> int:
    entries.append(
        {
            "id_lancamento": f"F{lancamento_id:07d}",
            "data_pagamento": data_pagamento,
            "codigo_conta": account["codigo_conta"],
            "conta": account["conta"],
            "grupo_dre": account["grupo_dre"],
            "tipo": account["tipo"],
            "categoria_dre": account["categoria_dre"],
            "centro_custo": centro_custo,
            "documento_origem": documento_origem,
            "valor": round(float(valor), 2),
        }
    )
    return lancamento_id + 1


def _validate_financial_reconciliation(df_vendas: pd.DataFrame, df_financeiro: pd.DataFrame) -> None:
    faturado = df_vendas[df_vendas["status"] == "Faturado"]
    receita_pedidos = round(float(faturado["total"].sum()), 2)
    receita_fin = round(
        float(df_financeiro[df_financeiro["tipo"].str.lower() == "receita"]["valor"].sum()), 2
    )
    cmv_pedidos = round(float(faturado["custo_total_item"].sum()), 2)
    cmv_fin = round(
        float(df_financeiro[df_financeiro["categoria_dre"].str.lower() == "cmv"]["valor"].sum()), 2
    )

    if receita_pedidos != receita_fin:
        raise ValueError(
            f"Receita divergente: pedidos={receita_pedidos:,.2f} financeiro={receita_fin:,.2f}"
        )
    if cmv_pedidos != cmv_fin:
        raise ValueError(f"CMV divergente: pedidos={cmv_pedidos:,.2f} financeiro={cmv_fin:,.2f}")


def _build_plano_contas() -> pd.DataFrame:
    rows: list[dict] = []
    for category in PRODUCT_CATEGORIES:
        rows.append({**REVENUE_ACCOUNTS[category], "natureza": "credito"})
        rows.append({**CMV_ACCOUNTS[category], "natureza": "debito"})
    for account in FIXED_EXPENSE_ACCOUNTS:
        rows.append({**account, "natureza": "debito"})
    return pd.DataFrame(rows)


def _generate_detailed_financials(
    df_vendas: pd.DataFrame,
    df_produtos: pd.DataFrame,
    targets: dict[str, float],
) -> pd.DataFrame:
    """Gera lancamentos analiticos por conta contabil (nao consolidados por dia)."""
    print("Gerando lancamentos financeiros analiticos por conta...")
    vendas = df_vendas.merge(df_produtos[["id_produto", "categoria"]], on="id_produto", how="left")
    vendas_faturadas = vendas[vendas["status"] == "Faturado"]

    financeiro_lista: list[dict] = []
    lancamento_id = 1

    for row in vendas_faturadas.itertuples(index=False):
        category = row.categoria
        revenue_account = REVENUE_ACCOUNTS[category]
        cmv_account = CMV_ACCOUNTS[category]
        centro = f"CC-{category[:3].upper()}"

        lancamento_id = _append_lancamento(
            financeiro_lista,
            lancamento_id,
            data_pagamento=row.data_emissao,
            account=revenue_account,
            valor=row.total,
            centro_custo=centro,
            documento_origem=row.id_pedido,
        )
        lancamento_id = _append_lancamento(
            financeiro_lista,
            lancamento_id,
            data_pagamento=row.data_emissao,
            account=cmv_account,
            valor=row.custo_total_item,
            centro_custo=centro,
            documento_origem=row.id_pedido,
        )

    print(f"Adicionando despesas alinhadas ao Templates ({PILOT_ANCHOR_YEAR})...")
    vendas_faturadas = vendas_faturadas.copy()
    vendas_faturadas["periodo"] = pd.to_datetime(vendas_faturadas["data_emissao"]).dt.to_period("M")
    receita_mensal = vendas_faturadas.groupby("periodo")["total"].sum()

    tax_accounts = [acc for acc in FIXED_EXPENSE_ACCOUNTS if acc["categoria_dre"] == "Impostos sobre Vendas"]
    other_accounts = [acc for acc in FIXED_EXPENSE_ACCOUNTS if acc["categoria_dre"] != "Impostos sobre Vendas"]
    other_peso_total = sum(acc["peso"] for acc in other_accounts)

    periodos_ancora = [p for p in receita_mensal.index if p.year == PILOT_ANCHOR_YEAR]
    impostos_ancora = sum(
        targets["receita_liquida"] * acc["peso"] for acc in tax_accounts
    )
    opex_nao_imposto = max(targets["opex_total"] - impostos_ancora, 0.0)
    opex_nao_imposto_mes = opex_nao_imposto / len(periodos_ancora) if periodos_ancora else 0.0

    for periodo, receita_mes in receita_mensal.items():
        data_fixo = datetime.strptime(f"{periodo}-05", "%Y-%m-%d").strftime("%Y-%m-%d")
        usar_template = periodo.year == PILOT_ANCHOR_YEAR

        for account in FIXED_EXPENSE_ACCOUNTS:
            if usar_template:
                if account["categoria_dre"] == "Impostos sobre Vendas":
                    valor = receita_mes * account["peso"]
                else:
                    valor = opex_nao_imposto_mes * (account["peso"] / other_peso_total)
            else:
                variacao = np.random.uniform(0.95, 1.05)
                base_mes = FIXED_EXPENSE_BASE * variacao
                if account["categoria_dre"] == "Impostos sobre Vendas":
                    valor = receita_mes * account["peso"]
                else:
                    valor = base_mes * account["peso"]

            lancamento_id = _append_lancamento(
                financeiro_lista,
                lancamento_id,
                data_pagamento=data_fixo,
                account=account,
                valor=valor,
                centro_custo="CC-ADM",
                documento_origem=f"DESP-{periodo}",
            )

    return pd.DataFrame(financeiro_lista)

def generate_pilot_data() -> dict[str, pd.DataFrame]:
    print("Iniciando geracao de grande volume de dados para o JUNO AI...")
    targets = _load_template_targets()
    print(
        f"Ancoragem Templates ({targets['fonte']}, {PILOT_ANCHOR_YEAR}): "
        f"receita R$ {targets['receita_liquida']:,.2f} | CMV R$ {targets['cmv']:,.2f}"
    )
    np.random.seed(42)
    n_clientes = 250
    df_clientes = pd.DataFrame(
        {
            "id_cliente": [f"C{i:04d}" for i in range(1, n_clientes + 1)],
            "razao_social": [f"Cliente Piloto {i} S/A" for i in range(1, n_clientes + 1)],
            "estado_uf": np.random.choice(
                ["SP", "MG", "RJ", "PR", "SC", "GO", "BA"],
                size=n_clientes,
                p=[0.4, 0.15, 0.15, 0.1, 0.1, 0.05, 0.05],
            ),
            "segmento": np.random.choice(
                ["Industria", "Comercio Atacadista", "Varejo", "Distribuicao"], size=n_clientes
            ),
        }
    )

    n_produtos = 500
    precos_base = np.random.exponential(scale=150, size=n_produtos) + 10
    df_produtos = pd.DataFrame(
        {
            "id_produto": [f"P{i:04d}" for i in range(1, n_produtos + 1)],
            "nome_produto": [f"Item SKU Industrial {i}" for i in range(1, n_produtos + 1)],
            "categoria": np.random.choice(PRODUCT_CATEGORIES, size=n_produtos),
            "preco_venda": np.round(precos_base, 2),
        }
    )
    df_produtos["custo_unitario"] = np.round(
        df_produtos["preco_venda"] * np.random.uniform(0.45, 0.65, size=n_produtos), 2
    )

    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 5, 25)
    dias_totais = (end_date - start_date).days

    vendas_lista: list[dict] = []
    pedido_id = 1

    print("Gerando historico de vendas (3 anos)...")
    for dia in range(dias_totais):
        data_atual = start_date + timedelta(days=dia)
        ano = data_atual.year
        mes = data_atual.month

        base_pedidos = 20 if ano == 2024 else (30 if ano == 2025 else 40)
        if mes in [11, 12]:
            base_pedidos = int(base_pedidos * 1.4)
        if data_atual.weekday() in [5, 6]:
            base_pedidos = int(base_pedidos * 0.2)

        n_pedidos_hoje = np.random.poisson(lam=base_pedidos)
        if n_pedidos_hoje <= 0:
            continue

        produtos_venda = df_produtos.sample(n=n_pedidos_hoje, replace=True).to_dict("records")
        clientes_venda = df_clientes.sample(n=n_pedidos_hoje, replace=True).to_dict("records")
        quantidades = np.random.randint(1, 50, size=n_pedidos_hoje)

        for idx in range(n_pedidos_hoje):
            prod = produtos_venda[idx]
            cli = clientes_venda[idx]
            qtd = int(quantidades[idx])
            total_item = round(qtd * prod["preco_venda"], 2)

            vendas_lista.append(
                {
                    "id_pedido": f"V{pedido_id:06d}",
                    "data_emissao": data_atual.strftime("%Y-%m-%d"),
                    "id_cliente": cli["id_cliente"],
                    "id_produto": prod["id_produto"],
                    "quantidade": qtd,
                    "valor_unitario": prod["preco_venda"],
                    "total": total_item,
                    "custo_total_item": round(qtd * prod["custo_unitario"], 2),
                    "status": "Faturado"
                    if data_atual < (end_date - timedelta(days=2))
                    else "Aberto",
                }
            )
            pedido_id += 1

    df_vendas = pd.DataFrame(vendas_lista)
    df_vendas = _anchor_vendas_to_template(df_vendas, targets)

    print("Gerando ordens de producao...")
    df_faturado = df_vendas[df_vendas["status"] == "Faturado"]
    df_op_amostra = df_faturado.sample(frac=0.5)

    df_op = pd.DataFrame(
        {
            "id_op": [f"OP{i:06d}" for i in range(1, len(df_op_amostra) + 1)],
            "id_produto": df_op_amostra["id_produto"].values,
            "quantidade_planejada": (df_op_amostra["quantidade"] * 1.1).astype(int),
            "quantidade_produzida": (df_op_amostra["quantidade"] * 1.1).astype(int),
            "data_inicio": df_op_amostra["data_emissao"].values,
            "status": "Finalizada",
        }
    )

    df_financeiro = _generate_detailed_financials(df_vendas, df_produtos, targets)
    df_plano_contas = _build_plano_contas()

    _validate_unique(df_clientes, "id_cliente", "Clientes")
    _validate_unique(df_produtos, "id_produto", "Produtos")
    _validate_unique(df_vendas, "id_pedido", "Pedidos de venda")
    _validate_unique(df_op, "id_op", "Ordens de producao")
    _validate_unique(df_financeiro, "id_lancamento", "Financeiro")
    _validate_financial_reconciliation(df_vendas, df_financeiro)
    _validate_template_alignment(df_vendas, df_financeiro, targets)

    frames = {
        "clientes": df_clientes,
        "produtos": df_produtos,
        "vendas": df_vendas,
        "op": df_op,
        "financeiro": df_financeiro,
        "plano_contas": df_plano_contas,
    }
    frames["_template_targets"] = pd.DataFrame([targets])
    return frames

def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    df.to_csv(temp_path, index=False)
    try:
        temp_path.replace(path)
    except PermissionError:
        fallback = BASE_DIR / path.name
        temp_path.replace(fallback)
        print(f"Aviso: {path.name} estava bloqueado; salvo em {fallback}")


def export_pilot_data(frames: dict[str, pd.DataFrame]) -> dict[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    export_frames = {k: v for k, v in frames.items() if not k.startswith("_")}

    output_files = {
        "clientes": OUTPUT_DIR / "clientes_piloto_larga_escala.csv",
        "produtos": OUTPUT_DIR / "produtos_piloto_larga_escala.csv",
        "vendas": OUTPUT_DIR / "pedidos_venda_piloto_larga_escala.csv",
        "op": OUTPUT_DIR / "ordens_producao_piloto_larga_escala.csv",
        "financeiro": OUTPUT_DIR / "financeiro_piloto_larga_escala.csv",
        "plano_contas": OUTPUT_DIR / "plano_contas_piloto.csv",
    }

    for key, path in output_files.items():
        _write_csv(export_frames[key], path)

    if "_template_targets" in frames:
        targets_path = OUTPUT_DIR / "piloto_template_targets.json"
        targets_path.write_text(
            json.dumps(frames["_template_targets"].iloc[0].to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return output_files

def write_manifest(frames: dict[str, pd.DataFrame], output_files: dict[str, Path]) -> Path:
    fin = frames["financeiro"]
    targets = frames.get("_template_targets")
    targets_row = targets.iloc[0].to_dict() if targets is not None else {}
    receita = round(float(fin[fin["tipo"].str.lower() == "receita"]["valor"].sum()), 2)
    cmv = round(float(fin[fin["categoria_dre"].str.lower() == "cmv"]["valor"].sum()), 2)
    despesa = round(
        float(
            fin[
                (fin["tipo"].str.lower() == "despesa") & (fin["categoria_dre"].str.lower() != "cmv")
            ]["valor"].sum()
        ),
        2,
    )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "output_dir": str(OUTPUT_DIR),
        "format": "financeiro_analitico_por_conta",
        "counts": {
            "clientes": int(len(frames["clientes"])),
            "produtos": int(len(frames["produtos"])),
            "pedidos_venda": int(len(frames["vendas"])),
            "ordens_producao": int(len(frames["op"])),
            "lancamentos_financeiros": int(len(frames["financeiro"])),
            "contas_plano_contas": int(len(frames["plano_contas"])),
            "contas_distintas_lancadas": int(fin["codigo_conta"].nunique()),
        },
        "totals": {
            "receita": receita,
            "cmv": cmv,
            "despesa_operacional": despesa,
        },
        "template_alignment": {
            "fonte": targets_row.get("fonte"),
            "competencia": targets_row.get("competencia"),
            "receita_liquida_alvo": targets_row.get("receita_liquida"),
            "cmv_alvo": targets_row.get("cmv"),
            "lucro_liquido_alvo": targets_row.get("lucro_liquido"),
            "opex_total_alvo": targets_row.get("opex_total"),
            "margem_bruta_pct": targets_row.get("margem_bruta_pct"),
            "margem_liquida_pct": targets_row.get("margem_liquida_pct"),
        },
        "files": {key: str(path) for key, path in output_files.items()},
        "upload_hint": {
            "erp_integrations": ["01..04 *_juno.csv"],
            "financials_page": "05_financial_ledger_juno.csv (analitico) ou 06_financial_statements_juno.csv (DRE gerencial agregada)",
        },
    }

    manifest_path = OUTPUT_DIR / "piloto_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def main() -> None:
    frames = generate_pilot_data()
    output_files = export_pilot_data(frames)
    manifest_path = write_manifest(frames, output_files)

    fin = frames["financeiro"]
    targets = frames["_template_targets"].iloc[0]
    mask_2025 = (pd.to_datetime(frames["vendas"]["data_emissao"]).dt.year == PILOT_ANCHOR_YEAR) & (
        frames["vendas"]["status"] == "Faturado"
    )

    print("\n--- GERACAO CONCLUIDA ---")
    print(f"Clientes gerados: {len(frames['clientes'])}")
    print(f"Produtos gerados: {len(frames['produtos'])}")
    print(f"Pedidos de Venda gerados: {len(frames['vendas'])}")
    print(f"Ordens de Producao geradas: {len(frames['op'])}")
    print(f"Lancamentos financeiros analiticos: {len(fin)}")
    print(f"Contas distintas no plano: {fin['codigo_conta'].nunique()}")
    print(f"Receita total: R$ {fin[fin['tipo'].str.lower() == 'receita']['valor'].sum():,.2f}")
    print(f"CMV total: R$ {fin[fin['categoria_dre'].str.lower() == 'cmv']['valor'].sum():,.2f}")
    print(f"\n--- FECHAMENTO {PILOT_ANCHOR_YEAR} vs TEMPLATES ({targets['fonte']}) ---")
    print(f"Receita liquida pedidos: R$ {frames['vendas'].loc[mask_2025, 'total'].sum():,.2f} | alvo R$ {targets['receita_liquida']:,.2f}")
    print(f"CMV pedidos: R$ {frames['vendas'].loc[mask_2025, 'custo_total_item'].sum():,.2f} | alvo R$ {targets['cmv']:,.2f}")
    print(f"Margem bruta Templates: {targets['margem_bruta_pct']:.2f}% | Margem liquida: {targets['margem_liquida_pct']:.2f}%")
    print(f"Arquivos em: {OUTPUT_DIR}")
    print(f"Manifesto: {manifest_path}")

if __name__ == "__main__":
    main()
