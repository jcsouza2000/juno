"""
test_sem6.py - testes das entregas da Semana 6: metricas, lineage, service migrado.
"""

from __future__ import annotations

import pytest

from app.ontology import metrics, runtime
from app.ontology.lineage import get_lineage

# =============================================================================
# Metrics
# =============================================================================


class TestMetrics:
    def test_time_call_increments_counter_on_success(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        seed_data,
    ):
        # Snapshot pre
        before = _counter_value("op", "fetch_by_id", "type", "Produto", "status", "ok")
        runtime.fetch_by_id(
            "Produto", 10, user=admin_user_ctx, db=db_session, registry=loaded_registry
        )
        after = _counter_value("op", "fetch_by_id", "type", "Produto", "status", "ok")
        assert after == before + 1

    def test_time_call_marks_not_found(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        seed_data,
    ):
        before = _counter_value("op", "fetch_by_id", "type", "Produto", "status", "not_found")
        with pytest.raises(runtime.ObjectNotFound):
            runtime.fetch_by_id(
                "Produto", 99999, user=admin_user_ctx, db=db_session, registry=loaded_registry
            )
        after = _counter_value("op", "fetch_by_id", "type", "Produto", "status", "not_found")
        assert after == before + 1

    def test_time_action_records_action_counter(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        before = _counter_value(
            "action",
            "atualizarPreco",
            "status",
            "ok",
            "dry_run",
            "false",
            counter=metrics.ACTION_CALLS,
        )
        runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 200.0, "motivo": "x"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()
        after = _counter_value(
            "action",
            "atualizarPreco",
            "status",
            "ok",
            "dry_run",
            "false",
            counter=metrics.ACTION_CALLS,
        )
        assert after == before + 1

    def test_action_dry_run_label_separates(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        before = _counter_value(
            "action",
            "atualizarPreco",
            "status",
            "ok",
            "dry_run",
            "true",
            counter=metrics.ACTION_CALLS,
        )
        runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 220.0, "motivo": "preview"},
            user=user,
            db=db_session,
            registry=loaded_registry,
            dry_run=True,
        )
        after = _counter_value(
            "action",
            "atualizarPreco",
            "status",
            "ok",
            "dry_run",
            "true",
            counter=metrics.ACTION_CALLS,
        )
        assert after == before + 1


def _counter_value(*label_pairs, counter=None):
    """
    Le o valor atual do contador para combinacao de labels.
    Os pares vem como ('label1', 'value1', 'label2', 'value2', ...).
    """
    if counter is None:
        counter = metrics.CALLS
    kwargs = dict(zip(label_pairs[::2], label_pairs[1::2], strict=False))
    try:
        return counter.labels(**kwargs)._value.get()
    except AttributeError:
        # NoOp (prometheus nao instalado) — sempre 0
        return 0


# =============================================================================
# Lineage
# =============================================================================


class TestLineage:
    def test_empty_when_no_actions(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        seed_data,
    ):
        result = get_lineage(
            "Produto", 10, db=db_session, user=admin_user_ctx, registry=loaded_registry
        )
        assert result["object_type"] == "Produto"
        assert result["object_id"] == 10
        assert result["total"] == 0
        assert result["events"] == []

    def test_after_action_lineage_has_event(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        admin_user_ctx,
        seed_data,
    ):
        # Executa uma action
        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 200.0, "motivo": "ajuste"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        result = get_lineage(
            "Produto", 10, db=db_session, user=admin_user_ctx, registry=loaded_registry
        )
        assert result["total"] >= 1
        event = result["events"][0]
        assert event["action"] == "atualizarPreco"
        assert event["status"] == "committed"
        assert event["diff"]["sale_price"]["after"] == 200.0
        assert event["inputs"]["motivo"] == "ajuste"

    def test_multiple_actions_ordered_desc(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        admin_user_ctx,
        seed_data,
    ):
        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        for preco in [200.0, 210.0, 220.0]:
            runtime.execute_action(
                "atualizarPreco",
                10,
                {"novo_preco": preco, "motivo": f"step {preco}"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )
            db_session.commit()

        result = get_lineage(
            "Produto", 10, db=db_session, user=admin_user_ctx, registry=loaded_registry
        )
        assert result["total"] == 3
        ids = [e["audit_id"] for e in result["events"]]
        assert ids == sorted(ids, reverse=True)

    def test_lineage_blocked_for_cross_tenant(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        """User do tenant 1 nao consegue ver lineage de produto do tenant 2."""
        # Forca uma action em produto 20 (tenant 2) — preciso de admin pra escrever
        from app.ontology.permissions import UserContext

        admin = UserContext(user_id=1, role="admin", company_ids=[1, 2], markings_granted=["*"])
        runtime.execute_action(
            "atualizarPreco",
            20,
            {"novo_preco": 900.0, "motivo": "ajuste tenant 2"},
            user=admin,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        # User do tenant 1 nao ve nada
        user_t1 = tenant_user_ctx_factory(company_ids=[1])
        result = get_lineage("Produto", 20, db=db_session, user=user_t1, registry=loaded_registry)
        assert result["events"] == []

    def test_unknown_type_returns_empty(self, db_session, admin_user_ctx, loaded_registry):
        result = get_lineage(
            "NaoExiste", 1, db=db_session, user=admin_user_ctx, registry=loaded_registry
        )
        assert result["events"] == []
        assert result["total"] == 0


# =============================================================================
# Service migrado: ontology_dashboards.get_cfo_margin_by_product_v2
# =============================================================================


class TestOntologyDashboard:
    def test_returns_products_with_margin(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        from app.services.ontology_dashboards import get_cfo_margin_by_product_v2

        # User comercial vê preços (tem ConfidencialComercial grant)
        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        result = get_cfo_margin_by_product_v2(db_session, 1, user=user, registry=loaded_registry)

        assert len(result) == 3  # 3 produtos da company 1
        # Garante shape
        for r in result:
            assert "product" in r
            assert "receita_liquida" in r
            assert "margem" in r
            assert "margem_critica" in r

        # Widget Pro tem vendas: id=10, 1 venda de revenue=1800, discount=100
        widget = next(r for r in result if r["product"] == "Widget Pro")
        assert widget["receita_liquida"] == 1700.0
        assert widget["qtd_vendas"] == 1
        # custo_real = standard_cost(100) * qtd(1) = 100
        assert widget["custo_real"] == 100.0
        assert widget["margem"] == 1600.0

    def test_tenant_scoped(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        from app.services.ontology_dashboards import get_cfo_margin_by_product_v2

        user_t1 = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        # Se pedir dados da company 2 mas o user e' do 1 → vazio
        result = get_cfo_margin_by_product_v2(db_session, 2, user=user_t1, registry=loaded_registry)
        assert result == []

    def test_user_without_marking_doesnt_see_cost(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        from app.services.ontology_dashboards import get_cfo_margin_by_product_v2

        # User sem ConfidencialComercial grant → standard_cost vem filtrado
        user = tenant_user_ctx_factory(
            role="user",
            company_ids=[1],
            markings=[],
        )
        result = get_cfo_margin_by_product_v2(db_session, 1, user=user, registry=loaded_registry)
        assert len(result) == 3
        # custo_real e margem ficam None (porque standard_cost foi omitido)
        for r in result:
            assert r["custo_real"] is None
            assert r["margem"] is None
