"""
test_ai_tools.py - testes do builder + dispatcher de tools auto-geradas.

Cobre:
  - build_tools_from_registry produz tools esperadas (read + propose_)
  - JSON schema dos inputs e' valido (types corretos, required, min/max)
  - build_system_prompt_fragment lista todos os tipos
  - dispatch_tool_call roteia search/get/list/propose corretamente
  - propose_* retorna kind=proposed_action sem persistir
  - propose_* devolve preview com diff quando dry_run roda
  - tool desconhecida -> UnknownToolError
"""

from __future__ import annotations

import pytest

from app import models
from app.ontology import ai_tools

# =============================================================================
# build_tools_from_registry
# =============================================================================


class TestBuildTools:
    def test_returns_list_of_dicts(self, loaded_registry):
        tools = ai_tools.build_tools_from_registry(loaded_registry)
        assert isinstance(tools, list)
        assert len(tools) > 0
        for t in tools:
            assert t["type"] == "function"
            assert "name" in t["function"]
            assert "parameters" in t["function"]
            params = t["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_read_tools_per_object_type(self, loaded_registry):
        tools = ai_tools.build_tools_from_registry(loaded_registry)
        names = {t["function"]["name"] for t in tools}

        # 5 ObjectTypes x 3 read tools = 15
        for snake in ("produto", "pedido_venda", "ordem_producao", "empresa", "cliente"):
            assert f"search_{snake}" in names
            assert f"get_{snake}_by_id" in names
            assert f"list_{snake}" in names

    def test_propose_tools_per_action(self, loaded_registry):
        tools = ai_tools.build_tools_from_registry(loaded_registry)
        names = {t["function"]["name"] for t in tools}

        # As 7 actions devem virar 7 propose_*
        expected = {
            "propose_atualizarPreco",
            "propose_desativarProduto",
            "propose_reagendarOrdem",
            "propose_cancelarOrdem",
            "propose_registrarConclusao",
            "propose_aprovarPedido",
            "propose_aplicarDesconto",
        }
        assert expected.issubset(names)

    def test_atualizar_preco_schema(self, loaded_registry):
        tools = ai_tools.build_tools_from_registry(loaded_registry)
        t = next(t for t in tools if t["function"]["name"] == "propose_atualizarPreco")
        params = t["function"]["parameters"]
        props = params["properties"]
        # Inputs declarados no YAML
        assert "target_id" in props
        assert props["target_id"]["type"] == "integer"
        assert "novo_preco" in props
        assert props["novo_preco"]["type"] == "number"
        assert props["novo_preco"]["minimum"] == 0
        assert "motivo" in props
        assert props["motivo"]["type"] == "string"
        assert props["motivo"]["maxLength"] == 500
        # required
        assert "target_id" in params["required"]
        assert "novo_preco" in params["required"]
        assert "motivo" in params["required"]

    def test_search_has_query_required(self, loaded_registry):
        tools = ai_tools.build_tools_from_registry(loaded_registry)
        t = next(t for t in tools if t["function"]["name"] == "search_produto")
        assert "query" in t["function"]["parameters"]["required"]


# =============================================================================
# build_system_prompt_fragment
# =============================================================================


class TestSystemPrompt:
    def test_lists_all_types(self, loaded_registry):
        s = ai_tools.build_system_prompt_fragment(loaded_registry)
        for type_name in ("Produto", "PedidoVenda", "OrdemProducao", "Empresa", "Cliente"):
            assert f"**{type_name}**" in s

    def test_lists_all_propose_actions(self, loaded_registry):
        s = ai_tools.build_system_prompt_fragment(loaded_registry)
        assert "propose_atualizarPreco" in s
        assert "propose_aplicarDesconto" in s
        assert "propose_cancelarOrdem" in s

    def test_contains_rules(self, loaded_registry):
        s = ai_tools.build_system_prompt_fragment(loaded_registry)
        assert "propose_*" in s
        assert "Regras" in s


# =============================================================================
# dispatch_tool_call — leitura
# =============================================================================


class TestDispatchRead:
    def test_get_by_id(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        result = ai_tools.dispatch_tool_call(
            "get_produto_by_id",
            {"id": 10},
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert result["kind"] == "object"
        assert result["type"] == "Produto"
        assert result["data"]["id"] == 10
        assert result["data"]["name"] == "Widget Pro"

    def test_search(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        result = ai_tools.dispatch_tool_call(
            "search_produto",
            {"query": "Widget"},
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert result["kind"] == "search_result"
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Widget Pro"

    def test_list(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        result = ai_tools.dispatch_tool_call(
            "list_produto",
            {"limit": 10},
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert result["kind"] == "list_result"
        assert result["total"] == 5

    def test_list_tenant_scoped(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        user = tenant_user_ctx_factory(company_ids=[1])
        result = ai_tools.dispatch_tool_call(
            "list_produto",
            {},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        assert result["total"] == 3  # so company 1
        for item in result["items"]:
            assert item["company_id"] == 1

    def test_unknown_tool_raises(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        with pytest.raises(ai_tools.UnknownToolError):
            ai_tools.dispatch_tool_call(
                "drop_database",
                {},
                user=admin_user_ctx,
                db=db_session,
                registry=loaded_registry,
            )


# =============================================================================
# dispatch_tool_call — propose
# =============================================================================


class TestDispatchPropose:
    def test_propose_returns_payload_without_persist(
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
        # Snapshot before
        prod_before = db_session.query(models.Product).filter_by(id=10).one()
        original_price = prod_before.sale_price

        result = ai_tools.dispatch_tool_call(
            "propose_atualizarPreco",
            {"target_id": 10, "novo_preco": 220.0, "motivo": "IA propos"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )

        assert result["kind"] == "proposed_action"
        assert result["action"] == "atualizarPreco"
        assert result["target_id"] == 10
        assert result["inputs"]["novo_preco"] == 220.0
        assert result["status"] == "awaiting_confirmation"
        assert "preview" in result

        # NAO persistiu
        db_session.expire_all()
        prod_after = db_session.query(models.Product).filter_by(id=10).one()
        assert prod_after.sale_price == original_price

    def test_propose_preview_has_diff(
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
        result = ai_tools.dispatch_tool_call(
            "propose_atualizarPreco",
            {"target_id": 10, "novo_preco": 220.0, "motivo": "x"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        preview = result["preview"]
        # Preview vem do dry-run -> tem before/after/diff
        assert preview.get("dry_run") is True
        assert "sale_price" in preview["diff"]
        assert preview["diff"]["sale_price"]["before"] == 180.0
        assert preview["diff"]["sale_price"]["after"] == 220.0

    def test_propose_with_validation_error_returns_preview_with_error(
        self,
        db_session,
        loaded_registry,
        tenant_user_ctx_factory,
        seed_data,
    ):
        """Quando o dry-run falha (preco abaixo do custo), preview leva a mensagem."""
        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        result = ai_tools.dispatch_tool_call(
            "propose_atualizarPreco",
            {"target_id": 10, "novo_preco": 5.0, "motivo": "bug"},
            user=user,
            db=db_session,
            registry=loaded_registry,
        )
        assert result["kind"] == "proposed_action"
        # preview carrega o erro do dry-run para o frontend mostrar
        assert "dry_run_error" in result["preview"]

    def test_propose_unknown_action_raises(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        seed_data,
    ):
        with pytest.raises(ai_tools.UnknownToolError):
            ai_tools.dispatch_tool_call(
                "propose_doesNotExist",
                {"target_id": 1},
                user=admin_user_ctx,
                db=db_session,
                registry=loaded_registry,
            )

    def test_propose_missing_target_id_raises(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        seed_data,
    ):
        with pytest.raises(ai_tools.UnknownToolError, match="target_id"):
            ai_tools.dispatch_tool_call(
                "propose_atualizarPreco",
                {"novo_preco": 100, "motivo": "x"},
                user=admin_user_ctx,
                db=db_session,
                registry=loaded_registry,
            )
