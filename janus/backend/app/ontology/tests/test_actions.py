"""
test_actions.py - testes de integracao de execute_action.

Cobre:
  - Caso feliz: produto.atualizarPreco persiste e cria audit_log
  - Dry-run: simula mas nao persiste
  - Validation error: regra asteval reprova
  - Auth deny: user sem role
  - IA actor: require_confirmation bloqueia sem confirmed_by
  - Warnings: severity=warning entra no resultado mas nao bloqueia
  - PedidoVenda.aplicarDesconto: muda discount e recalcula total
  - OrdemProducao.cancelarOrdem: status='cancelled'
  - TenantScoped: user de outra empresa nao consegue
  - Audit: diff/before/after populados
"""

from __future__ import annotations

import json

import pytest

from app import models
from app.ontology import runtime
from app.ontology.permissions import PermissionDenied
from app.ontology.runtime import ValidationFailed

# =============================================================================
# Helpers
# =============================================================================


def _comercial_user(tenant_user_ctx_factory, company_ids=None, markings=None):
    """User com role gerente_comercial + grant para ConfidencialComercial."""
    return tenant_user_ctx_factory(
        role="gerente_comercial",
        company_ids=company_ids if company_ids is not None else [1],
        markings=markings if markings is not None else ["ConfidencialComercial"],
    )


def _pcp_user(tenant_user_ctx_factory, company_ids=None):
    return tenant_user_ctx_factory(
        role="gerente_pcp",
        company_ids=company_ids if company_ids is not None else [1],
        markings=[],
    )


def _read_audit_logs(db_session, action_name=None):
    q = db_session.query(models.AuditLog)
    if action_name:
        q = q.filter(models.AuditLog.action == action_name)
    return q.order_by(models.AuditLog.id.desc()).all()


# =============================================================================
# Produto.atualizarPreco — caso feliz
# =============================================================================


class TestAtualizarPreco:
    def test_happy_path(self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data):
        user = _comercial_user(tenant_user_ctx_factory)
        # Widget Pro: standard_cost=100, sale_price=180. novo_preco=200 valido.
        result = runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 200.0, "motivo": "reajuste"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        assert result.success is True
        assert result.dry_run is False
        assert result.before["sale_price"] == 180.0
        assert result.after["sale_price"] == 200.0
        assert "sale_price" in result.diff
        assert result.diff["sale_price"]["before"] == 180.0
        assert result.diff["sale_price"]["after"] == 200.0
        assert result.audit_id is not None

        # Persistiu mesmo?
        prod = db_session.query(models.Product).filter_by(id=10).one()
        assert prod.sale_price == 200.0

        # Audit log gravou
        logs = _read_audit_logs(db_session, "atualizarPreco")
        assert len(logs) == 1
        details = json.loads(logs[0].details)
        assert details["target_id"] == 10
        assert details["status"] == "committed"
        assert details["before"]["sale_price"] == 180.0
        assert details["after"]["sale_price"] == 200.0
        assert details["diff"]["sale_price"]["after"] == 200.0

    def test_dry_run_no_persist(
        self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data
    ):
        user = _comercial_user(tenant_user_ctx_factory)
        result = runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 200.0, "motivo": "teste"},
            user=user,
            db=db_session,
            registry=loaded_registry,
            dry_run=True,
        )

        assert result.success is True
        assert result.dry_run is True
        assert result.audit_id is None
        assert result.after["sale_price"] == 200.0

        # NAO persistiu
        prod = db_session.query(models.Product).filter_by(id=10).one()
        assert prod.sale_price == 180.0

        # NAO criou audit_log
        logs = _read_audit_logs(db_session, "atualizarPreco")
        assert len(logs) == 0

    def test_validation_error_below_cost(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        """Regra: novo_preco >= standard_cost * 0.8 (Widget: 100*0.8=80)."""
        user = _comercial_user(tenant_user_ctx_factory)
        with pytest.raises(ValidationFailed) as exc:
            runtime.execute_action(
                "atualizarPreco",
                10,
                {"novo_preco": 50.0, "motivo": "muito baixo"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )
        errors = exc.value.errors
        assert any("margem fortemente negativa" in e["message"].lower() for e in errors)

    def test_required_input_missing(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = _comercial_user(tenant_user_ctx_factory)
        with pytest.raises(ValidationFailed) as exc:
            runtime.execute_action(
                "atualizarPreco",
                10,
                {"novo_preco": 200.0},  # falta motivo
                user=user,
                db=db_session,
                registry=loaded_registry,
            )
        assert any(e["rule"] == "required" and e["field"] == "motivo" for e in exc.value.errors)

    def test_warning_does_not_block(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        """Variacao > 50% e' warning, nao error. Acao prossegue e warning entra no result."""
        user = _comercial_user(tenant_user_ctx_factory)
        # Widget sale_price=180. novo_preco=300 => variacao = 120/180 = 66% > 50%
        result = runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 300.0, "motivo": "reajuste agressivo"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()
        assert result.success is True
        assert any("Variação > 50%" in w or "Variacao > 50%" in w for w in result.warnings)

    def test_no_role_denied(self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data):
        """User 'comum' nao pode atualizarPreco."""
        user = tenant_user_ctx_factory(
            role="user", company_ids=[1], markings=["ConfidencialComercial"]
        )
        with pytest.raises(PermissionDenied):
            runtime.execute_action(
                "atualizarPreco",
                10,
                {"novo_preco": 200.0, "motivo": "x"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )

    def test_tenant_scoped_blocks_cross_company(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        """User de tenant 1 nao consegue alterar produto da empresa 2."""
        user = _comercial_user(tenant_user_ctx_factory, company_ids=[1])
        with pytest.raises(runtime.ObjectNotFound):
            runtime.execute_action(
                "atualizarPreco",
                20,
                {"novo_preco": 1000.0, "motivo": "x"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# AI actor — require_confirmation
# =============================================================================


class TestAIConfirmation:
    def test_ai_without_confirmation_denied(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = _comercial_user(tenant_user_ctx_factory)
        with pytest.raises(PermissionDenied):
            runtime.execute_action(
                "atualizarPreco",
                10,
                {"novo_preco": 200.0, "motivo": "IA propos"},
                user=user,
                db=db_session,
                registry=loaded_registry,
                actor_type="ai_coordinator",  # sem confirmed_by
            )

    def test_ai_with_confirmation_allowed(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = _comercial_user(tenant_user_ctx_factory)
        result = runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 200.0, "motivo": "IA propos, humano confirmou"},
            user=user,
            db=db_session,
            registry=loaded_registry,
            actor_type="ai_coordinator",
            confirmed_by=42,
        )
        db_session.commit()
        assert result.success is True

        logs = _read_audit_logs(db_session, "atualizarPreco")
        details = json.loads(logs[0].details)
        assert details["actor_type"] == "ai_coordinator"
        assert details["confirmed_by"] == 42


# =============================================================================
# PedidoVenda.aplicarDesconto
# =============================================================================


class TestAplicarDesconto:
    def test_recalcula_total(self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data):
        user = _comercial_user(tenant_user_ctx_factory)
        # Pedido 101: revenue=3500, discount=0, total=3500
        result = runtime.execute_action(
            "aplicarDesconto",
            101,
            {"valor_desconto": 500.0, "motivo": "fidelizacao"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        assert result.diff["discount"]["after"] == 500.0
        assert result.diff["total"]["after"] == 3000.0

        order = db_session.query(models.SalesOrder).filter_by(id=101).one()
        assert order.discount == 500.0
        assert order.total == 3000.0

    def test_excessivo_bloqueia(
        self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data
    ):
        user = _comercial_user(tenant_user_ctx_factory)
        # 50%+ da receita bloqueado
        with pytest.raises(ValidationFailed):
            runtime.execute_action(
                "aplicarDesconto",
                101,
                {"valor_desconto": 2000.0, "motivo": "absurdo"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# OrdemProducao.cancelarOrdem (via seed extra)
# =============================================================================


class TestCancelarOrdem:
    @pytest.fixture
    def seed_order(self, db_session, seed_data):
        op = models.ProductionOrder(
            id=500,
            company_id=1,
            product_id=10,
            planned_qty=100,
            actual_qty=0,
            planned_cost=10000.0,
            actual_cost=0.0,
            status="in_progress",
        )
        db_session.add(op)
        db_session.commit()
        return op

    def test_cancel_sets_status(
        self, db_session, loaded_registry, tenant_user_ctx_factory, seed_order
    ):
        user = _pcp_user(tenant_user_ctx_factory)
        result = runtime.execute_action(
            "cancelarOrdem",
            500,
            {"motivo": "cliente desistiu"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        assert result.diff["status"]["before"] == "in_progress"
        assert result.diff["status"]["after"] == "cancelled"

        op = db_session.query(models.ProductionOrder).filter_by(id=500).one()
        assert op.status == "cancelled"

    def test_cancel_completed_blocked(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_order,
    ):
        seed_order.status = "completed"
        db_session.commit()
        user = _pcp_user(tenant_user_ctx_factory)
        with pytest.raises(ValidationFailed):
            runtime.execute_action(
                "cancelarOrdem",
                500,
                {"motivo": "tentando"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# Erros estruturais
# =============================================================================


class TestErrorPaths:
    def test_unknown_action(self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data):
        user = _comercial_user(tenant_user_ctx_factory)
        with pytest.raises(KeyError):
            runtime.execute_action(
                "inexistente",
                10,
                {},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )

    def test_target_not_found(
        self, db_session, loaded_registry, tenant_user_ctx_factory, seed_data
    ):
        user = _comercial_user(tenant_user_ctx_factory)
        with pytest.raises(runtime.ObjectNotFound):
            runtime.execute_action(
                "atualizarPreco",
                99999,
                {"novo_preco": 100.0, "motivo": "x"},
                user=user,
                db=db_session,
                registry=loaded_registry,
            )

    def test_failed_action_rolls_back_everything(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        """
        Quando handler explode:
          - Exception sobe para o caller
          - Mutacoes no target sao revertidas (savepoint rollback)
          - Nenhum audit_log e' persistido (rollback total)
        Decisao arquitetural: audit_logs so registra mudancas confirmadas;
        tentativas falhas devem ser observadas via metricas/logs estruturados.
        """
        user = _comercial_user(tenant_user_ctx_factory)
        import app.ontology.actions.product as prod_mod

        original = prod_mod.update_price

        def broken(*a, **kw):
            raise RuntimeError("explosao no handler")

        prod_mod.update_price = broken
        from app.ontology import runtime as rt

        rt._HANDLER_CACHE.pop("app.ontology.actions.product.update_price", None)

        try:
            with pytest.raises(RuntimeError, match="explosao"):
                runtime.execute_action(
                    "atualizarPreco",
                    10,
                    {"novo_preco": 200.0, "motivo": "x"},
                    user=user,
                    db=db_session,
                    registry=loaded_registry,
                )
            # Sessao continua usavel apos o rollback de savepoint
            db_session.commit()

            # Produto inalterado
            prod = db_session.query(models.Product).filter_by(id=10).one()
            assert prod.sale_price == 180.0

            # Nenhum audit gravado (rollback total)
            logs = _read_audit_logs(db_session, "atualizarPreco")
            assert len(logs) == 0
        finally:
            prod_mod.update_price = original
            rt._HANDLER_CACHE.pop("app.ontology.actions.product.update_price", None)
