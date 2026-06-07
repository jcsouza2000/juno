"""
Testes do modulo de gestao de dados do tenant (inventario + purge).

Cobre:
  - contagem de inventario por grupo/tabela e isolamento entre tenants;
  - periodos financeiros e historico de depositos;
  - purge por escopo (financial / erp / all), incluindo tabelas-filho (FK);
  - garantia de que o purge NAO vaza para outro tenant.
"""

from __future__ import annotations

import pytest

from app.data_management import (
    get_company_data_inventory,
    purge_company_data,
)
from app.models import (
    Company,
    Customer,
    ErpFinancial,
    ERPImportBatch,
    FinancialStatement,
    FinancialUploadBatch,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    ScoreHistory,
    Supplier,
    SupplierProduct,
)


def _seed_company(db, name: str) -> int:
    """Cria uma company com um conjunto completo de dados de negocio."""
    company = Company(name=name, sector="industria")
    db.add(company)
    db.flush()
    cid = company.id

    # Financeiro
    db.add(
        FinancialStatement(
            company_id=cid,
            statement_type="DRE",
            period="2026-01",
            line_item="receita_bruta",
            value=1000.0,
        )
    )
    db.add(ErpFinancial(company_id=cid, document_type="invoice", period="2026-02", balance=50.0))
    db.add(
        FinancialUploadBatch(
            company_id=cid, file_name="dre.xlsx", periods="2026-01", rows_imported=1
        )
    )

    # Operacional ERP (com filhos para validar FK)
    product = Product(company_id=cid, name="Peca X")
    supplier = Supplier(company_id=cid, name="Fornecedor Y")
    db.add_all([product, supplier])
    db.flush()

    po = PurchaseOrder(company_id=cid, supplier_id=supplier.id, total_amount=200.0)
    db.add(po)
    db.flush()
    db.add(
        PurchaseOrderItem(
            purchase_order_id=po.id, product_id=product.id, quantity=10, unit_cost=20.0
        )
    )
    db.add(SupplierProduct(supplier_id=supplier.id, product_id=product.id, unit_cost=18.0))
    db.add(Customer(company_id=cid, name="Cliente Z"))
    db.add(ERPImportBatch(company_id=cid, data_type="products", rows_imported=1))

    # KPI derivado
    db.add(ScoreHistory(company_id=cid, overall_score=72.5))

    db.commit()
    return cid


@pytest.fixture()
def two_tenants(db_session):
    cid_a = _seed_company(db_session, "Tenant A")
    cid_b = _seed_company(db_session, "Tenant B")
    return db_session, cid_a, cid_b


# ── Inventario ───────────────────────────────────────────────────────────────


def test_inventory_counts_por_grupo(two_tenants):
    db, cid_a, _ = two_tenants
    inv = get_company_data_inventory(db, cid_a)

    groups = {g["group"]: g for g in inv["groups"]}
    assert groups["financial"]["total_rows"] == 3  # statement + erp_fin + batch
    assert groups["derived"]["total_rows"] == 1  # score_history
    # erp: product, supplier, purchase_order, customer, erp_import_batch = 5
    assert groups["erp"]["total_rows"] == 5
    assert inv["total_rows"] == 9


def test_inventory_periodos_e_depositos(two_tenants):
    db, cid_a, _ = two_tenants
    inv = get_company_data_inventory(db, cid_a)

    assert inv["periods"] == ["2026-01", "2026-02"]
    sources = {d["source"] for d in inv["uploads"]}
    assert sources == {"financial", "erp"}


def test_inventory_isolado_por_tenant(two_tenants):
    db, cid_a, cid_b = two_tenants
    inv_a = get_company_data_inventory(db, cid_a)
    inv_b = get_company_data_inventory(db, cid_b)
    # Cada tenant ve apenas os proprios dados (mesma carga -> mesmos totais).
    assert inv_a["total_rows"] == inv_b["total_rows"] == 9


# ── Purge ────────────────────────────────────────────────────────────────────


def test_purge_financial_remove_so_financeiro_e_kpi(two_tenants):
    db, cid_a, _ = two_tenants
    deleted = purge_company_data(db, cid_a, "financial")

    assert deleted["financial_statements"] == 1
    assert deleted["erp_financials"] == 1
    assert deleted["score_history"] == 1

    inv = get_company_data_inventory(db, cid_a)
    groups = {g["group"]: g for g in inv["groups"]}
    assert groups["financial"]["total_rows"] == 0
    assert groups["derived"]["total_rows"] == 0
    # ERP intacto
    assert groups["erp"]["total_rows"] == 5


def test_purge_erp_remove_filhos_via_fk(two_tenants):
    db, cid_a, _ = two_tenants
    deleted = purge_company_data(db, cid_a, "erp")

    # Filhos (sem company_id) removidos via subconsulta dos pais.
    assert deleted["purchase_order_items"] == 1
    assert deleted["supplier_products"] == 1
    assert deleted["products"] == 1
    assert deleted["suppliers"] == 1

    # Os filhos do Tenant B permanecem (purge isolado por tenant); como sao
    # tabelas globais, sobra exatamente 1 de cada — o do outro tenant.
    assert db.query(PurchaseOrderItem).count() == 1
    assert db.query(SupplierProduct).count() == 1

    inv = get_company_data_inventory(db, cid_a)
    groups = {g["group"]: g for g in inv["groups"]}
    assert groups["erp"]["total_rows"] == 0
    # Financeiro preservado
    assert groups["financial"]["total_rows"] == 3


def test_purge_all_nao_vaza_para_outro_tenant(two_tenants):
    db, cid_a, cid_b = two_tenants
    purge_company_data(db, cid_a, "all")

    inv_a = get_company_data_inventory(db, cid_a)
    inv_b = get_company_data_inventory(db, cid_b)

    assert inv_a["total_rows"] == 0
    # Tenant B permanece intacto.
    assert inv_b["total_rows"] == 9
    # Company A em si nao e' apagada.
    assert db.query(Company).filter(Company.id == cid_a).count() == 1


def test_purge_escopo_invalido(two_tenants):
    db, cid_a, _ = two_tenants
    with pytest.raises(ValueError):
        purge_company_data(db, cid_a, "tudo")
