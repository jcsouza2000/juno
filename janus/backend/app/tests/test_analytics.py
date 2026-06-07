"""
Testes das analises operacionais (concentracao de clientes e curva ABC).
"""

from __future__ import annotations

import pytest

from app.analytics import get_customer_concentration, get_product_abc
from app.models import Company, Customer, Product, SalesOrder


@pytest.fixture()
def seeded(db_session):
    db = db_session
    company = Company(name="Analytics Co", sector="industria")
    db.add(company)
    db.flush()
    cid = company.id

    # 3 clientes com receitas 70 / 20 / 10 (total 100)
    customers = []
    for name, rev in [("Cliente A", 70.0), ("Cliente B", 20.0), ("Cliente C", 10.0)]:
        c = Customer(company_id=cid, name=name)
        db.add(c)
        db.flush()
        customers.append((c, rev))

    # 3 produtos com receitas 70 / 20 / 10
    products = []
    for name, rev in [("Produto A", 70.0), ("Produto B", 20.0), ("Produto C", 10.0)]:
        p = Product(company_id=cid, name=name, standard_cost=1.0)
        db.add(p)
        db.flush()
        products.append((p, rev))

    # Uma venda por cliente e uma por produto, mapeando 1:1.
    for (cust, crev), (prod, _prev) in zip(customers, products, strict=False):
        db.add(
            SalesOrder(
                company_id=cid,
                customer_id=cust.id,
                product_id=prod.id,
                revenue=crev,
                discount=0.0,
                total=crev,
            )
        )
    db.commit()
    return db, cid


def test_customer_concentration_percentuais_e_abc(seeded):
    db, cid = seeded
    out = get_customer_concentration(db, cid)

    assert out["available"] is True
    assert out["total_customers"] == 3
    assert out["receita_total"] == 100.0
    assert out["top_1_pct"] == 70.0
    assert out["top_5_pct"] == 100.0
    # Maior cliente >= 30% -> alerta de risco.
    assert out["risco_concentracao"] is True

    clientes = out["clientes"]
    assert clientes[0]["cliente"] == "Cliente A"
    assert clientes[0]["classe_abc"] == "A"  # acumulado 70%
    assert clientes[1]["classe_abc"] == "B"  # acumulado 90%
    assert clientes[2]["classe_abc"] == "C"  # acumulado 100%


def test_product_abc_classes_e_resumo(seeded):
    db, cid = seeded
    out = get_product_abc(db, cid)

    assert out["available"] is True
    assert out["total_products"] == 3
    assert out["receita_total"] == 100.0

    produtos = out["produtos"]
    assert produtos[0]["produto"] == "Produto A"
    assert produtos[0]["classe_abc"] == "A"

    resumo = out["resumo_classes"]
    assert resumo["A"]["itens"] == 1
    assert resumo["A"]["receita"] == 70.0


def test_sem_vendas_retorna_indisponivel(db_session):
    db = db_session
    company = Company(name="Vazia", sector="x")
    db.add(company)
    db.commit()

    assert get_customer_concentration(db, company.id)["available"] is False
    assert get_product_abc(db, company.id)["available"] is False
