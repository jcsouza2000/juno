from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "uploads_piloto_juno"

RAW_FILES = {
    "customers": OUTPUT_DIR / "clientes_piloto_larga_escala.csv",
    "products": OUTPUT_DIR / "produtos_piloto_larga_escala.csv",
    "sales": OUTPUT_DIR / "pedidos_venda_piloto_larga_escala.csv",
    "production": OUTPUT_DIR / "ordens_producao_piloto_larga_escala.csv",
    "financial": OUTPUT_DIR / "financeiro_piloto_larga_escala.csv",
    "chart_of_accounts": OUTPUT_DIR / "plano_contas_piloto.csv",
}


def _money(series: pd.Series) -> pd.Series:
    return series.astype(float).round(2)


def _require_raw_files() -> None:
    missing = [str(path) for path in RAW_FILES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Arquivos brutos nao encontrados. Execute primeiro piloto_test.py. Faltando: "
            + ", ".join(missing)
        )


def convert_customers(customers: pd.DataFrame) -> pd.DataFrame:
    return customers.rename(
        columns={
            "razao_social": "name",
            "segmento": "segment",
        }
    )[["name", "segment"]]


def convert_products(products: pd.DataFrame) -> pd.DataFrame:
    converted = products.rename(
        columns={
            "nome_produto": "name",
            "categoria": "category",
            "custo_unitario": "standard_cost",
            "preco_venda": "sale_price",
        }
    )
    converted["standard_cost"] = _money(converted["standard_cost"])
    converted["sale_price"] = _money(converted["sale_price"])
    return converted[["name", "category", "standard_cost", "sale_price"]]


def convert_sales(
    sales: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    customer_lookup = customers[["id_cliente", "razao_social"]].rename(
        columns={"razao_social": "customer_name"}
    )
    product_lookup = products[["id_produto", "nome_produto"]].rename(
        columns={"nome_produto": "product_name"}
    )

    converted = sales.merge(customer_lookup, on="id_cliente", how="left").merge(
        product_lookup, on="id_produto", how="left"
    )
    converted["revenue"] = _money(converted["total"])
    converted["discount"] = 0.0
    converted = converted.rename(columns={"data_emissao": "order_date"})
    return converted[["customer_name", "product_name", "revenue", "discount", "order_date"]]


def convert_production(production: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    product_lookup = products[["id_produto", "nome_produto", "custo_unitario"]].rename(
        columns={"nome_produto": "product_name"}
    )
    converted = production.merge(product_lookup, on="id_produto", how="left").copy()
    converted["op_number"] = converted["id_op"].str.extract(r"(\d+)").astype(int)
    converted["planned_qty"] = converted["quantidade_planejada"].astype(int)
    converted["actual_qty"] = converted["quantidade_produzida"].astype(int)
    converted["planned_cost"] = _money(converted["planned_qty"] * converted["custo_unitario"])

    overrun_factor = 1.0 + converted["op_number"].mod(11).eq(0).astype(float) * 0.15
    converted["actual_cost"] = _money(converted["planned_cost"] * overrun_factor)

    planned_date = pd.to_datetime(converted["data_inicio"]) + pd.to_timedelta(3, unit="D")
    delay_days = pd.Series(0, index=converted.index)
    delay_days = delay_days.mask(converted["op_number"].mod(7).eq(0), 2)
    delay_days = delay_days.mask(converted["op_number"].mod(29).eq(0), 8)
    actual_date = planned_date + pd.to_timedelta(delay_days, unit="D")

    converted["planned_date"] = planned_date.dt.strftime("%Y-%m-%d")
    converted["actual_date"] = actual_date.dt.strftime("%Y-%m-%d")
    converted["status"] = delay_days.gt(0).map({True: "completed_late", False: "completed"})

    return converted[
        [
            "product_name",
            "planned_qty",
            "actual_qty",
            "planned_cost",
            "actual_cost",
            "planned_date",
            "actual_date",
            "status",
        ]
    ]


def convert_financial_ledger(financial: pd.DataFrame) -> pd.DataFrame:
    """Mantem lancamentos analiticos por conta para auditoria e upload financeiro bruto."""
    columns = [
        "id_lancamento",
        "data_pagamento",
        "codigo_conta",
        "conta",
        "grupo_dre",
        "tipo",
        "categoria_dre",
        "centro_custo",
        "documento_origem",
        "valor",
    ]
    return financial[columns].copy()


def convert_financial_statements(financial: pd.DataFrame) -> pd.DataFrame:
    """Agrega contas analiticas em DRE gerencial + balanco + DFC (KPIs)."""
    df = financial.copy()
    df["data_pagamento"] = pd.to_datetime(df["data_pagamento"])
    df["periodo"] = df["data_pagamento"].dt.to_period("M").astype(str)

    detailed = (
        df.groupby(["periodo", "codigo_conta", "conta", "tipo", "categoria_dre"], as_index=False)["valor"]
        .sum()
        .sort_values(["periodo", "codigo_conta"])
    )

    receitas = (
        df[df["tipo"].str.lower() == "receita"].groupby("periodo")["valor"].sum().rename("receita_bruta")
    )
    cmv = df[df["categoria_dre"].str.lower() == "cmv"].groupby("periodo")["valor"].sum().rename("cmv")
    despesas = (
        df[(df["tipo"].str.lower() == "despesa") & (df["categoria_dre"].str.lower() != "cmv")]
        .groupby("periodo")["valor"]
        .sum()
        .rename("despesas_operacionais")
    )

    monthly = pd.concat([receitas, cmv, despesas], axis=1).fillna(0).reset_index()
    monthly["receita_liquida"] = monthly["receita_bruta"]
    monthly["lucro_bruto"] = monthly["receita_liquida"] - monthly["cmv"]
    monthly["ebitda"] = monthly["lucro_bruto"] - monthly["despesas_operacionais"]
    monthly["lucro_liquido"] = monthly["ebitda"]

    rows: list[dict[str, object]] = []

    for _, detail in detailed.iterrows():
        valor = float(detail["valor"])
        if detail["tipo"].lower() == "despesa":
            valor = -abs(valor)
        rows.append(
            {
                "statement_type": "DRE",
                "periodo": detail["periodo"],
                "codigo_conta": detail["codigo_conta"],
                "conta": detail["conta"],
                "grupo_dre": detail["categoria_dre"],
                "valor": round(valor, 2),
            }
        )

    cumulative_cash = 250_000.0
    for index, row in monthly.iterrows():
        periodo = row["periodo"]
        receita = float(row["receita_bruta"])
        cmv_value = float(row["cmv"])
        despesas_value = float(row["despesas_operacionais"])
        lucro_bruto = float(row["lucro_bruto"])
        ebitda = float(row["ebitda"])
        lucro_liquido = float(row["lucro_liquido"])

        summary_items = {
            "receita_bruta": receita,
            "receita_liquida": receita,
            "cmv": -cmv_value,
            "lucro_bruto": lucro_bruto,
            "despesas_operacionais": -despesas_value,
            "ebitda": ebitda,
            "lucro_liquido": lucro_liquido,
        }
        for conta, valor in summary_items.items():
            rows.append(
                {
                    "statement_type": "DRE",
                    "periodo": periodo,
                    "codigo_conta": "",
                    "conta": conta,
                    "grupo_dre": "Resumo Gerencial",
                    "valor": round(float(valor), 2),
                }
            )

        cumulative_cash += lucro_liquido
        ativo_circulante = max(cumulative_cash, 50_000.0)
        passivo_circulante = max(receita * 0.18, 20_000.0)
        passivo_nao_circulante = max(receita * 0.08, 10_000.0)
        patrimonio_liquido = max(ativo_circulante - passivo_circulante - passivo_nao_circulante, 1.0)

        for conta, valor in {
            "ativo_circulante": ativo_circulante,
            "passivo_circulante": passivo_circulante,
            "passivo_nao_circulante": passivo_nao_circulante,
            "patrimonio_liquido": patrimonio_liquido,
        }.items():
            rows.append(
                {
                    "statement_type": "BALANCO",
                    "periodo": periodo,
                    "codigo_conta": "",
                    "conta": conta,
                    "grupo_dre": "Resumo Gerencial",
                    "valor": round(float(valor), 2),
                }
            )

        caixa_investimento = -(receita * 0.025) if index % 3 == 0 else 0.0
        caixa_financiamento = receita * 0.015 if index % 6 == 0 else 0.0
        variacao_caixa = lucro_liquido + caixa_investimento + caixa_financiamento
        for conta, valor in {
            "caixa_operacional": lucro_liquido,
            "caixa_investimento": caixa_investimento,
            "caixa_financiamento": caixa_financiamento,
            "variacao_caixa": variacao_caixa,
            "caixa_final": cumulative_cash,
        }.items():
            rows.append(
                {
                    "statement_type": "DFC",
                    "periodo": periodo,
                    "codigo_conta": "",
                    "conta": conta,
                    "grupo_dre": "Resumo Gerencial",
                    "valor": round(float(valor), 2),
                }
            )

    return pd.DataFrame(
        rows,
        columns=["statement_type", "periodo", "codigo_conta", "conta", "grupo_dre", "valor"],
    )


def main() -> None:
    _require_raw_files()
    OUTPUT_DIR.mkdir(exist_ok=True)

    customers = pd.read_csv(RAW_FILES["customers"])
    products = pd.read_csv(RAW_FILES["products"])
    sales = pd.read_csv(RAW_FILES["sales"])
    production = pd.read_csv(RAW_FILES["production"])
    financial = pd.read_csv(RAW_FILES["financial"])

    outputs = {
        "01_customers_juno.csv": convert_customers(customers),
        "02_products_juno.csv": convert_products(products),
        "03_sales_orders_juno.csv": convert_sales(sales, customers, products),
        "04_production_orders_juno.csv": convert_production(production, products),
        "05_financial_ledger_juno.csv": convert_financial_ledger(financial),
        "06_financial_statements_juno.csv": convert_financial_statements(financial),
    }

    print("Gerando arquivos prontos para upload no JUNO...")
    for filename, dataframe in outputs.items():
        path = OUTPUT_DIR / filename
        dataframe.to_csv(path, index=False)
        print(f"- {filename}: {len(dataframe):,} linhas")

    print(f"\nArquivos gerados em: {OUTPUT_DIR}")
    print("Upload financeiro analitico: 05_financial_ledger_juno.csv")
    print("Upload DRE gerencial/KPIs: 06_financial_statements_juno.csv")


if __name__ == "__main__":
    main()
