"""
test_runtime.py - testes de integracao do runtime CRUD da ontologia.

Cobre:
  - fetch_by_id, list_objects, search_objects
  - computed properties (margem_unitaria, margem_percentual, abaixo_minimo)
  - markings: TenantScoped (row-level), ConfidencialComercial (column-level)
  - resolve_link (many_to_one, one_to_many)
  - paginacao + filtros
"""

from __future__ import annotations

import pytest

from app.ontology import runtime

# =============================================================================
# fetch_by_id
# =============================================================================


class TestFetchById:
    def test_admin_fetch_produto(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert prod["id"] == 10
        assert prod["name"] == "Widget Pro"
        assert prod["sale_price"] == 180.0
        assert prod["standard_cost"] == 100.0

    def test_computed_properties_evaluated(
        self, db_session, loaded_registry, admin_user_ctx, seed_data
    ):
        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        # margem_unitaria = sale_price - standard_cost = 180 - 100 = 80
        assert prod["margem_unitaria"] == 80.0
        # margem_percentual = 80/180*100 = 44.44...
        assert prod["margem_percentual"] == pytest.approx(44.44, abs=0.01)
        # abaixo_minimo: 50 < 20 = false
        assert prod["abaixo_minimo"] is False
        # margem_critica: 0.44 < 0.10 = false
        assert prod["margem_critica"] is False

    def test_computed_below_minimum(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        prod = runtime.fetch_by_id(
            "Produto",
            11,  # Gadget Mk2: stock=10, min=15
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert prod["abaixo_minimo"] is True

    def test_object_not_found(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        with pytest.raises(runtime.ObjectNotFound):
            runtime.fetch_by_id(
                "Produto",
                9999,
                user=admin_user_ctx,
                db=db_session,
                registry=loaded_registry,
            )

    def test_unknown_object_type(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        with pytest.raises(KeyError):
            runtime.fetch_by_id(
                "Inexistente",
                1,
                user=admin_user_ctx,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# TenantScoped — row-level
# =============================================================================


class TestTenantScoped:
    def test_user_tenant1_sees_company1_product(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[1])
        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        assert prod["id"] == 10

    def test_user_tenant1_blocked_from_company2(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[1])
        # Produto 20 pertence a company 2 — user de tenant 1 nao deve ver
        with pytest.raises(runtime.ObjectNotFound):
            runtime.fetch_by_id(
                "Produto",
                20,
                user=user,
                db=db_session,
                registry=loaded_registry,
            )

    def test_user_no_companies_sees_nothing(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[])
        with pytest.raises(runtime.ObjectNotFound):
            runtime.fetch_by_id(
                "Produto",
                10,
                user=user,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# Column filtering — ConfidencialComercial
# =============================================================================


class TestColumnFiltering:
    def test_non_admin_no_grant_omits_confidencial(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[1], markings=[])
        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        # sale_price e standard_cost tem marking ConfidencialComercial
        # com requires_marking_grant=true → user sem grant nao ve
        assert "sale_price" not in prod
        assert "standard_cost" not in prod
        # mas v outras props
        assert prod["name"] == "Widget Pro"
        assert prod["stock_quantity"] == 50

    def test_user_with_grant_sees_confidencial(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[1], markings=["ConfidencialComercial"])
        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        assert prod["sale_price"] == 180.0
        assert prod["standard_cost"] == 100.0

    def test_admin_sees_all(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert "sale_price" in prod
        assert "standard_cost" in prod


# =============================================================================
# list_objects
# =============================================================================


class TestListObjects:
    def test_list_with_pagination(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        result = runtime.list_objects(
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            limit=2,
            offset=0,
        )
        assert result["total"] == 5  # 3 c1 + 2 c2
        assert len(result["items"]) == 2
        assert result["limit"] == 2
        assert result["offset"] == 0

    def test_list_tenant_scoped(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[1])
        result = runtime.list_objects(
            "Produto",
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        assert result["total"] == 3  # so produtos da company 1
        company_ids = {item["company_id"] for item in result["items"]}
        assert company_ids == {1}

    def test_list_with_filter(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        result = runtime.list_objects(
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            filters={"category": "servico"},
        )
        assert result["total"] == 2  # so os servicos da company 2
        for item in result["items"]:
            assert item["category"] == "servico"

    def test_list_order_by_desc(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        result = runtime.list_objects(
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            order_by="-id",
        )
        ids = [item["id"] for item in result["items"]]
        assert ids == sorted(ids, reverse=True)


# =============================================================================
# search
# =============================================================================


class TestSearch:
    def test_search_by_name(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        items = runtime.search_objects(
            "Produto",
            "Widget",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert len(items) == 1
        assert items[0]["name"] == "Widget Pro"

    def test_search_partial(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        items = runtime.search_objects(
            "Produto",
            "Servico",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert len(items) == 2


# =============================================================================
# resolve_link
# =============================================================================


class TestResolveLink:
    def test_many_to_one_empresa(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        emp = runtime.resolve_link(
            "Produto",
            10,
            "empresa",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert emp is not None
        assert emp["id"] == 1
        assert emp["name"] == "Empresa Alpha"

    def test_one_to_many_produtos_da_empresa(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        seed_data,
    ):
        produtos = runtime.resolve_link(
            "Empresa",
            1,
            "produtos",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert isinstance(produtos, list)
        assert len(produtos) == 3
        assert all(p["company_id"] == 1 for p in produtos)

    def test_link_unknown_raises(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        with pytest.raises(KeyError, match="link"):
            runtime.resolve_link(
                "Produto",
                10,
                "inexistente",
                user=admin_user_ctx,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# Order com computed: PedidoVenda.desconto_percentual
# =============================================================================


class TestPedidoComputed:
    def test_desconto_percentual(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        order = runtime.fetch_by_id(
            "PedidoVenda",
            100,
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        # discount=100, revenue=1800 → 100/1800*100 = 5.555...
        assert order["desconto_percentual"] == pytest.approx(5.555, abs=0.01)
        assert order["desconto_alto"] is False

    def test_desconto_alto_quando_zero(
        self, db_session, loaded_registry, admin_user_ctx, seed_data
    ):
        order = runtime.fetch_by_id(
            "PedidoVenda",
            101,
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        # discount=0 → desconto_percentual=0
        assert order["desconto_percentual"] == 0
        assert order["desconto_alto"] is False
