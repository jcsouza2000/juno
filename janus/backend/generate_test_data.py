"""
Gerador de massa de dados de teste — JUNO Industrial Diagnostic
Gera CSVs realistas e importa via endpoint ERP.

Uso:  python generate_test_data.py
      (backend deve estar rodando em localhost:8000)
"""

import csv
import io
import random
import requests
from datetime import date, timedelta

random.seed(42)
API = "http://localhost:8000"
TODAY = date.today()

def d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d")

def rand_date_range(start_days_ago: int, end_days_ago: int) -> str:
    days = random.randint(end_days_ago, start_days_ago)
    return d(days)

# ─────────────────────────────────────────────────────────────────────────────
# EMPRESA A — Bens de Capital (ID=1)
# Narrativa: fabricante de máquinas CNC e centros de usinagem sob encomenda
# Ciclo de venda longo, alto valor unitário, margens em pressão por desvio de custo
# ─────────────────────────────────────────────────────────────────────────────

EMPRESA_A_PRODUCTS = [
    # name, category, standard_cost, sale_price
    ("Torno CNC G 260",                "Máquinas CNC",       450_000,  640_000),
    ("Torno CNC G 460",                "Máquinas CNC",       680_000,  890_000),
    ("Torno CNC G 660",                "Máquinas CNC",       920_000, 1_190_000),
    ("Centro de Furação D 600",        "Máquinas CNC",       320_000,  415_000),
    ("Centro de Usinagem VMC 850",     "Máquinas CNC",       580_000,  740_000),
    ("Centro de Usinagem VMC 1250",    "Máquinas CNC",       780_000,  980_000),
    ("Peça Customizada HC-2024",       "Componentes",        285_000,  190_000),  # margem negativa
    ("Peça Customizada HC-2025",       "Componentes",        210_000,  145_000),  # margem negativa
    ("Retrofit Industrial Série P",    "Serviços",           185_000,   97_000),  # margem negativa
    ("Retrofit Industrial Série X",    "Serviços",           120_000,  155_000),
    ("Manutenção Preventiva Anual",    "Serviços",            35_000,   58_000),
    ("Manutenção Corretiva",           "Serviços",            22_000,   42_000),
    ("Kit Ferramentas CNC Premium",    "Acessórios",          18_000,   28_500),
    ("Kit Ferramentas CNC Standard",   "Acessórios",           9_800,   15_200),
    ("Cabeçote Fresador Modular",      "Componentes",         95_000,  128_000),
    ("Eixo-Árvore de Alta Rotação",    "Componentes",         62_000,   89_000),
    ("Painel CNC Siemens 840D",        "Componentes",         45_000,   67_500),
    ("Painel CNC Fanuc 0i",            "Componentes",         38_000,   54_000),
    ("Guia Linear Hiwin 35mm",         "Componentes",          8_500,   12_800),
    ("Fuso de Esferas 32mm",           "Componentes",         12_000,   17_500),
]

EMPRESA_A_CUSTOMERS = [
    ("AutoParts SA",           "Automotivo"),
    ("MetalBrasil Ltda",       "Metalurgia"),
    ("AeroFab Indústrias",     "Aeroespacial"),
    ("PetroMaq Serviços",      "Óleo e Gás"),
    ("NavalTec Engenharia",    "Naval"),
    ("Fundição São Paulo",     "Metalurgia"),
    ("Aço Brasil Ltda",        "Metalurgia"),
    ("Turbinas do Sul SA",     "Energia"),
    ("MecPrecision Ltda",      "Automotivo"),
    ("DefesaTec Indústrias",   "Defesa"),
    ("Usina Nova Lima",        "Mineração"),
    ("Ferramental ABC",        "Ferramentaria"),
    ("Indústria Alfa SA",      "Automotivo"),
    ("Grupo Máquinas Beta",    "Multissetorial"),
    ("TechSteel Ltda",         "Metalurgia"),
]


# ─────────────────────────────────────────────────────────────────────────────
# EMPRESA B — Implementos Rodoviários (ID=2)
# Narrativa: fabricante seriada de semirreboques, eixos e suspensão
# Alto volume, margem por unidade menor, gargalo em solda e eixos
# ─────────────────────────────────────────────────────────────────────────────

EMPRESA_B_PRODUCTS = [
    # name, category, standard_cost, sale_price
    ("Semirreboque Carga Seca SR-45",      "Semirreboques",    72_000,   105_000),
    ("Semirreboque Frigorífico SR-RF",     "Semirreboques",   135_000,   185_000),
    ("Semirreboque Graneleiro SR-GR",      "Semirreboques",    68_000,    96_000),
    ("Plataforma Rebaixada SR-PR",         "Semirreboques",   148_000,    78_000),  # margem negativa
    ("Baú Frigorífico 45ft",              "Carrocerias",     145_000,   198_000),
    ("Baú Seco 45ft",                     "Carrocerias",      92_000,   128_000),
    ("Eixo Reforçado HD-22",              "Componentes",      62_000,    31_000),  # margem negativa
    ("Eixo Standard LD-18",               "Componentes",      28_000,    38_500),
    ("Eixo Autodirecionável AD-16",        "Componentes",      42_000,    58_000),
    ("Kit Suspensão Pesada 6x4",          "Componentes",      19_800,    21_000),  # margem fina
    ("Kit Suspensão Standard 4x2",        "Componentes",      12_500,    17_800),
    ("Quinta Roda Holland 2pol",           "Componentes",       8_200,    12_500),
    ("Lona de Freio Premium",             "Manutenção",        1_800,     3_200),
    ("Kit Manutenção 50mil km",           "Manutenção",        4_500,     7_800),
    ("Serviço Alinhamento e Balanceamento","Serviços",          2_200,     4_500),
    ("Reparo Estrutural Chassi",          "Serviços",          18_000,    28_000),
    ("Pintura Eletrostática",             "Serviços",           6_500,    11_000),
    ("Instalação Rastreador GPS",         "Serviços",           1_200,     2_800),
    ("Lanterna LED Traseira",             "Elétrico",             480,       950),
    ("Kit Elétrico Completo",             "Elétrico",           3_800,     6_200),
]

EMPRESA_B_CUSTOMERS = [
    ("TransLog Brasil SA",         "Logística"),
    ("Rodofort Transportes",       "Transporte"),
    ("CargoSul SA",                "Agronegócio"),
    ("Frigorífico Nobre Ltda",     "Frigorífico"),
    ("GrãoMax Transportes",        "Agronegócio"),
    ("Distribuidora Rio Verde",    "Distribuição"),
    ("Rodoviária Paulista SA",     "Transporte"),
    ("Agro Fretes Ltda",           "Agronegócio"),
    ("Carga Pesada Norte",         "Transporte"),
    ("Friolog Serviços",           "Frigorífico"),
    ("SuperFrete Express",         "Logística"),
    ("Vale Verde Agro",            "Agronegócio"),
    ("Transportes Alfa Ltda",      "Transporte"),
    ("Log Express SA",             "Logística"),
    ("CaminhãoMax Ltda",           "Transporte"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Geradores de CSV
# ─────────────────────────────────────────────────────────────────────────────

def gen_products_csv(products: list) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["name", "category", "standard_cost", "sale_price"])
    for name, cat, cost, price in products:
        w.writerow([name, cat, cost, price])
    return out.getvalue()


def gen_customers_csv(customers: list) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["name", "segment"])
    for name, seg in customers:
        w.writerow([name, seg])
    return out.getvalue()


def gen_sales_orders_csv(products: list, customers: list, months: int = 6) -> str:
    """
    Gera pedidos de venda realistas por 6 meses.
    - Produtos de alto valor: 1-3 pedidos/mês
    - Produtos de serviço: 4-8 pedidos/mês
    - Produtos com margem negativa: gerados normalmente (situação real)
    - Sazonalidade: Q4 20% maior, Q1 10% menor
    """
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["customer_name", "product_name", "revenue", "discount", "order_date"])

    customer_names = [c[0] for c in customers]

    for month_ago in range(months, 0, -1):
        month_start = TODAY.replace(day=1) - timedelta(days=30 * month_ago)
        month_end   = month_start + timedelta(days=28)
        month_num   = month_start.month

        # Sazonalidade
        season = 1.2 if month_num in (10, 11, 12) else (0.9 if month_num in (1, 2) else 1.0)

        for name, cat, cost, price in products:
            # Volume por categoria
            if "Serviços" in cat or "Manutenção" in cat or "Acessórios" in cat or "Elétrico" in cat:
                n_orders = random.randint(3, 8)
            elif price > 500_000:
                n_orders = random.randint(1, 2)
            elif price > 100_000:
                n_orders = random.randint(1, 3)
            else:
                n_orders = random.randint(2, 5)

            n_orders = max(1, round(n_orders * season))

            for _ in range(n_orders):
                # Variação de ±5% no preço de venda (negociação)
                variance = random.uniform(0.95, 1.05)
                actual_revenue = round(price * variance)
                discount = round(actual_revenue * random.uniform(0, 0.04))
                order_date = rand_date_range(
                    (TODAY - month_start).days,
                    (TODAY - month_end).days,
                )
                customer = random.choice(customer_names)
                w.writerow([customer, name, actual_revenue, discount, order_date])

    return out.getvalue()


def gen_production_orders_csv(products: list, months: int = 6) -> str:
    """
    Gera ordens de produção com:
    - Desvios de custo realistas (+5% a +25%)
    - Atrasos em ~35% das ordens
    - Produtos problemáticos com overrun maior
    """
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "product_name", "planned_qty", "actual_qty",
        "planned_cost", "actual_cost",
        "planned_date", "actual_date", "status"
    ])

    PROBLEMATIC = {
        "Peça Customizada HC-2024", "Peça Customizada HC-2025",
        "Retrofit Industrial Série P",
        "Plataforma Rebaixada SR-PR", "Eixo Reforçado HD-22",
        "Kit Suspensão Pesada 6x4",
    }

    for month_ago in range(months, 0, -1):
        month_start = TODAY.replace(day=1) - timedelta(days=30 * month_ago)

        for name, cat, cost, price in products:
            # Número de lotes de produção por mês
            if price > 500_000:
                batches = random.randint(1, 2)
                qty = 1
            elif price > 100_000:
                batches = random.randint(1, 3)
                qty = random.randint(1, 3)
            elif "Serviços" in cat or "Manutenção" in cat:
                batches = random.randint(2, 5)
                qty = random.randint(2, 8)
            else:
                batches = random.randint(2, 4)
                qty = random.randint(3, 15)

            for _ in range(batches):
                is_problematic = name in PROBLEMATIC

                # Custo planejado
                planned_cost = round(cost * qty * random.uniform(0.95, 1.05))

                # Desvio de custo real
                if is_problematic:
                    overrun = random.uniform(1.12, 1.28)
                else:
                    overrun = random.uniform(1.00, 1.10)
                actual_cost = round(planned_cost * overrun)

                # Quantidade real (eventual scrap)
                if is_problematic:
                    actual_qty = qty if random.random() > 0.3 else max(1, qty - 1)
                else:
                    actual_qty = qty

                # Datas
                planned_start_day = random.randint(0, 25)
                planned_date = (month_start + timedelta(days=planned_start_day)).strftime("%Y-%m-%d")

                # Atraso
                if is_problematic:
                    delay = random.randint(3, 12) if random.random() < 0.65 else 0
                else:
                    delay = random.randint(1, 7) if random.random() < 0.30 else 0

                actual_date = (
                    month_start + timedelta(days=planned_start_day + delay)
                ).strftime("%Y-%m-%d")

                # Status
                op_date = month_start + timedelta(days=planned_start_day + delay)
                if op_date > TODAY:
                    status = "Em andamento"
                elif delay > 0:
                    status = "Concluído"
                else:
                    status = "Concluído"

                w.writerow([
                    name, qty, actual_qty,
                    planned_cost, actual_cost,
                    planned_date, actual_date, status
                ])

    return out.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Import via API
# ─────────────────────────────────────────────────────────────────────────────

def import_csv(company_id: int, data_type: str, csv_content: str, filename: str) -> dict:
    files = {"file": (filename, csv_content.encode("utf-8"), "text/csv")}
    data  = {"company_id": str(company_id), "data_type": data_type}
    resp  = requests.post(f"{API}/integrations/erp/upload", files=files, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def print_result(label: str, result: dict):
    status = result.get("status", "?")
    icon   = "✅" if status == "success" else ("⚠️" if status == "partial" else "❌")
    print(f"  {icon} {label}: {result['rows_imported']}/{result['rows_received']} importadas  [{status}]")
    for err in result.get("errors", [])[:3]:
        print(f"     └ {err}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("JUNO — Gerador de Massa de Dados de Teste")
    print("=" * 60)

    datasets = [
        # (company_id, label, data_type, csv_fn, filename)
        (1, "Empresa A — Produtos",           "products",
            gen_products_csv(EMPRESA_A_PRODUCTS),
            "empresa_a_products.csv"),
        (1, "Empresa A — Clientes",           "customers",
            gen_customers_csv(EMPRESA_A_CUSTOMERS),
            "empresa_a_customers.csv"),
        (1, "Empresa A — Pedidos de Venda",   "sales_orders",
            gen_sales_orders_csv(EMPRESA_A_PRODUCTS, EMPRESA_A_CUSTOMERS),
            "empresa_a_sales_orders.csv"),
        (1, "Empresa A — Ordens de Produção", "production_orders",
            gen_production_orders_csv(EMPRESA_A_PRODUCTS),
            "empresa_a_production_orders.csv"),
        (2, "Empresa B — Produtos",           "products",
            gen_products_csv(EMPRESA_B_PRODUCTS),
            "empresa_b_products.csv"),
        (2, "Empresa B — Clientes",           "customers",
            gen_customers_csv(EMPRESA_B_CUSTOMERS),
            "empresa_b_customers.csv"),
        (2, "Empresa B — Pedidos de Venda",   "sales_orders",
            gen_sales_orders_csv(EMPRESA_B_PRODUCTS, EMPRESA_B_CUSTOMERS),
            "empresa_b_sales_orders.csv"),
        (2, "Empresa B — Ordens de Produção", "production_orders",
            gen_production_orders_csv(EMPRESA_B_PRODUCTS),
            "empresa_b_production_orders.csv"),
    ]

    # Contagem prévia
    for cid, label, dtype, csv_content, _ in datasets:
        lines = csv_content.strip().count("\n")
        print(f"  📄 {label}: {lines} registros gerados")

    print()
    print("Importando via ERP endpoint...")
    print()

    totals = {"received": 0, "imported": 0}
    for cid, label, dtype, csv_content, filename in datasets:
        try:
            result = import_csv(cid, dtype, csv_content, filename)
            print_result(label, result)
            totals["received"] += result.get("rows_received", 0)
            totals["imported"] += result.get("rows_imported", 0)
        except Exception as exc:
            print(f"  ❌ {label}: ERRO — {exc}")

    print()
    print("=" * 60)
    print(f"TOTAL: {totals['imported']}/{totals['received']} registros importados com sucesso")
    print("=" * 60)


if __name__ == "__main__":
    main()
