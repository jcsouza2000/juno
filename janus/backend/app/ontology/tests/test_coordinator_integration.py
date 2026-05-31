"""
test_coordinator_integration.py - garante que o ai_coordinator integra com a ontologia.

Nao testa o LLM (Ollama) — testa as funcoes deterministicas:
  - _get_ontology_extensions() mescla as 22 tools auto-geradas
  - _run_tool() roteia search_*/get_*/list_*/propose_* para dispatch
  - _run_tool() ainda funciona com tools legadas
  - dispatch retorna proposed_action sem persistir
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _clear_coordinator_cache(loaded_registry):
    """
    O coordinator cacheia ontology tools em variavel global. Antes/depois de
    cada teste:
      1. carrega registry global com loaded_registry
      2. limpa cache do coordinator
    """
    from app import ai_coordinator
    from app.ontology.registry import registry as _global_registry

    # Copia state do registry de teste para o global
    _global_registry.reset()
    for name in loaded_registry.list_object_types():
        _global_registry.register_object_type(loaded_registry.get_object_type(name))
    for name in loaded_registry.list_action_types():
        _global_registry.register_action_type(loaded_registry.get_action_type(name))
    for ms_name, ms in loaded_registry._marking_sets.items():  # noqa: SLF001
        _global_registry.register_marking_set(ms)
    _global_registry.mark_loaded()

    # Limpa cache do coordinator
    ai_coordinator._ONTOLOGY_TOOLS_CACHE = None
    ai_coordinator._ONTOLOGY_PROMPT_CACHE = None
    yield
    ai_coordinator._ONTOLOGY_TOOLS_CACHE = None
    ai_coordinator._ONTOLOGY_PROMPT_CACHE = None
    _global_registry.reset()


# =============================================================================
# Extensions: tools + prompt
# =============================================================================


class TestOntologyExtensions:
    def test_loads_auto_generated_tools(self):
        from app import ai_coordinator

        tools, prompt = ai_coordinator._get_ontology_extensions()
        names = {t["function"]["name"] for t in tools}
        # 5 types * 3 tools + 7 actions = 22
        assert len(tools) == 22
        assert "search_produto" in names
        assert "get_produto_by_id" in names
        assert "list_produto" in names
        assert "propose_atualizarPreco" in names

    def test_prompt_fragment_lists_types(self):
        from app import ai_coordinator

        _, prompt = ai_coordinator._get_ontology_extensions()
        assert "**Produto**" in prompt
        assert "**PedidoVenda**" in prompt
        assert "propose_atualizarPreco" in prompt

    def test_extensions_cached(self):
        from app import ai_coordinator

        a, _ = ai_coordinator._get_ontology_extensions()
        b, _ = ai_coordinator._get_ontology_extensions()
        assert a is b  # mesma lista (cache)


# =============================================================================
# _run_tool: ontology routing
# =============================================================================


class TestRunToolOntology:
    def test_get_by_id_routes_to_dispatch(
        self,
        db_session,
        admin_user_ctx,
        seed_data,
    ):
        from app import ai_coordinator

        result = ai_coordinator._run_tool(
            "get_produto_by_id",
            {"id": 10},
            db_session,
            user=admin_user_ctx,
        )
        data = json.loads(result)
        assert data["kind"] == "object"
        assert data["type"] == "Produto"
        assert data["data"]["id"] == 10
        assert data["data"]["name"] == "Widget Pro"

    def test_search_routes_to_dispatch(
        self,
        db_session,
        admin_user_ctx,
        seed_data,
    ):
        from app import ai_coordinator

        result = ai_coordinator._run_tool(
            "search_produto",
            {"query": "Widget"},
            db_session,
            user=admin_user_ctx,
        )
        data = json.loads(result)
        assert data["kind"] == "search_result"
        assert len(data["items"]) == 1

    def test_propose_returns_proposed_action_payload(
        self,
        db_session,
        tenant_user_ctx_factory,
        seed_data,
    ):
        from app import ai_coordinator

        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        result = ai_coordinator._run_tool(
            "propose_atualizarPreco",
            {"target_id": 10, "novo_preco": 200.0, "motivo": "ai sugeriu"},
            db_session,
            user=user,
        )
        data = json.loads(result)
        assert data["kind"] == "proposed_action"
        assert data["action"] == "atualizarPreco"
        assert data["target_id"] == 10
        assert data["status"] == "awaiting_confirmation"

    def test_propose_does_not_persist(
        self,
        db_session,
        tenant_user_ctx_factory,
        seed_data,
    ):
        from app import ai_coordinator, models

        user = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        original_price = db_session.query(models.Product).filter_by(id=10).one().sale_price
        ai_coordinator._run_tool(
            "propose_atualizarPreco",
            {"target_id": 10, "novo_preco": 999.0, "motivo": "x"},
            db_session,
            user=user,
        )
        db_session.expire_all()
        new_price = db_session.query(models.Product).filter_by(id=10).one().sale_price
        assert new_price == original_price


# =============================================================================
# _run_tool: legacy fallback ainda funciona
# =============================================================================


class TestLegacyTools:
    def test_get_company_overview_falls_back_to_legacy(
        self,
        db_session,
        admin_user_ctx,
        seed_data,
    ):
        """get_company_overview e' tool LEGADA (nao matchea padrao ontology)."""
        from app import ai_coordinator

        # nao explode mesmo sem ollama; deve cair no path legado
        result = ai_coordinator._run_tool(
            "get_company_overview",
            {"company_id": 1},
            db_session,
        )
        # Pode retornar erro se algum modulo legado nao estiver disponivel; o
        # importante e' que o NOME nao foi roteado para dispatch.
        data = json.loads(result)
        # Se chegou aqui sem KeyError de ontology, o fallback funcionou
        assert "kind" not in data  # dispatch retornaria kind=...; legado nao

    def test_unknown_tool_returns_error_json(self, db_session, admin_user_ctx):
        from app import ai_coordinator

        result = ai_coordinator._run_tool(
            "does_not_exist",
            {"company_id": 1},
            db_session,
        )
        data = json.loads(result)
        assert "error" in data
