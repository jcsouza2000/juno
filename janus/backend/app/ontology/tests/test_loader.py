"""
test_loader.py - testes do loader carregando os 4 YAMLs reais de definitions/.

Estes testes garantem que:
  - Cada YAML parseia corretamente
  - O registry fica consistente (validate_consistency retorna [])
  - Os tipos esperados existem (Produto, OrdemProducao, PedidoVenda, Actions)
  - Erros de YAML produzem OntologyLoadError com contexto

Rodar:
    cd janus/backend
    .venv/Scripts/python -m pytest app/ontology/tests/test_loader.py -v
"""

from __future__ import annotations

import pytest

from app.ontology.loader import (
    DEFINITIONS_DIR,
    OntologyLoadError,
    load_all,
    load_file,
)
from app.ontology.registry import Registry


@pytest.fixture
def fresh_registry() -> Registry:
    """Registry vazio por teste — não usa o singleton global."""
    return Registry()


# =============================================================================
# Smoke: os 4 YAMLs reais carregam
# =============================================================================


class TestLoadDefinitions:
    """Carrega o conjunto real de YAMLs e valida estado básico."""

    def test_load_all_returns_summary(self, fresh_registry):
        summary = load_all(fresh_registry)
        assert "_markings.yaml" in summary
        assert "produto.yaml" in summary
        assert "ordem_producao.yaml" in summary
        assert "pedido_venda.yaml" in summary
        # cada YAML tem 1 MarkingSet OU pelo menos 1 ObjectType
        assert all(c >= 1 for c in summary.values())

    def test_object_types_registered(self, fresh_registry):
        load_all(fresh_registry)
        names = fresh_registry.list_object_types()
        assert "Produto" in names
        assert "OrdemProducao" in names
        assert "PedidoVenda" in names

    def test_action_types_registered(self, fresh_registry):
        load_all(fresh_registry)
        actions = fresh_registry.list_action_types()
        # Produto
        assert "atualizarPreco" in actions
        assert "desativarProduto" in actions
        # OrdemProducao
        assert "reagendarOrdem" in actions
        assert "cancelarOrdem" in actions
        assert "registrarConclusao" in actions
        # PedidoVenda
        assert "aprovarPedido" in actions
        assert "aplicarDesconto" in actions

    def test_marking_set_default(self, fresh_registry):
        load_all(fresh_registry)
        # noqa: SLF001 — teste pode olhar privado
        ms = fresh_registry._marking_sets["default"]
        markings = ms.spec.markings
        assert "TenantScoped" in markings
        assert "PII" in markings
        assert "ConfidencialComercial" in markings


# =============================================================================
# Validação cruzada
# =============================================================================


class TestConsistency:
    """validate_consistency() deve passar limpo para os YAMLs entregues."""

    def test_consistency_clean(self, fresh_registry):
        load_all(fresh_registry)
        # skip_models porque os testes podem rodar sem SQLAlchemy bootstrap pleno
        errors = fresh_registry.validate_consistency(check_models=False)
        assert errors == [], "Erros inesperados:\n" + "\n".join(errors)

    def test_actions_for_produto(self, fresh_registry):
        load_all(fresh_registry)
        produto_actions = fresh_registry.list_action_types_for("Produto")
        assert set(produto_actions) == {"atualizarPreco", "desativarProduto"}


# =============================================================================
# Lookup
# =============================================================================


class TestLookup:
    def test_get_object_type(self, fresh_registry):
        load_all(fresh_registry)
        prod = fresh_registry.get_object_type("Produto")
        assert prod.metadata.name == "Produto"
        assert prod.spec.title_property == "name"
        assert "sale_price" in prod.spec.properties
        assert prod.spec.properties["sale_price"].currency == "BRL"

    def test_get_action_type(self, fresh_registry):
        load_all(fresh_registry)
        act = fresh_registry.get_action_type("atualizarPreco")
        assert act.spec.target == "Produto"
        assert "novo_preco" in act.spec.inputs
        assert act.spec.authorization.require_confirmation is True

    def test_computed_property_formula_present(self, fresh_registry):
        load_all(fresh_registry)
        prod = fresh_registry.get_object_type("Produto")
        margem = prod.spec.computed_properties["margem_percentual"]
        assert "sale_price" in margem.formula
        assert "standard_cost" in margem.formula

    def test_links_resolved(self, fresh_registry):
        load_all(fresh_registry)
        ordem = fresh_registry.get_object_type("OrdemProducao")
        assert "produto" in ordem.spec.links
        assert ordem.spec.links["produto"].target == "Produto"

    def test_lookup_unknown_raises(self, fresh_registry):
        load_all(fresh_registry)
        with pytest.raises(KeyError, match="ObjectType 'Foo' não está registrado"):
            fresh_registry.get_object_type("Foo")


# =============================================================================
# Tratamento de erros (com diretórios temporários)
# =============================================================================


class TestErrors:
    """Cenários de erro com diretórios temporários — não tocam definitions/ real."""

    def test_missing_directory(self, fresh_registry, tmp_path):
        nonexistent = tmp_path / "naoexiste"
        with pytest.raises(OntologyLoadError, match="diretorio de definitions"):
            load_all(fresh_registry, definitions_dir=nonexistent)

    def test_invalid_yaml(self, fresh_registry, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("this is: not [valid yaml: ::", encoding="utf-8")
        with pytest.raises(OntologyLoadError, match="YAML invalido"):
            load_file(fresh_registry, bad)

    def test_unknown_kind(self, fresh_registry, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "apiVersion: ontology.juno.gravithy.com.br/v1\n"
            "kind: NaoExiste\n"
            "metadata: {name: Foo}\n"
            "spec: {}\n",
            encoding="utf-8",
        )
        with pytest.raises(OntologyLoadError, match="Unknown ontology kind"):
            load_file(fresh_registry, bad)

    def test_duplicate_object_type(self, fresh_registry, tmp_path):
        # Cria 2 YAMLs com mesmo nome de ObjectType
        valid_template = """\
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ObjectType
metadata:
  name: Foo
spec:
  backing: {type: sqlalchemy, model: app.models.Product}
  title_property: name
  properties:
    id: {type: integer, required: true, readonly: true}
    name: {type: string, required: true}
"""
        f1 = tmp_path / "foo1.yaml"
        f1.write_text(valid_template, encoding="utf-8")
        load_file(fresh_registry, f1)

        f2 = tmp_path / "foo2.yaml"
        f2.write_text(valid_template, encoding="utf-8")
        with pytest.raises(OntologyLoadError, match="já registrado"):
            load_file(fresh_registry, f2)

    def test_multi_doc_yaml_parses(self, fresh_registry, tmp_path):
        """YAMLs como ordem_producao.yaml têm 4 docs separados por ---."""
        multi = tmp_path / "multi.yaml"
        multi.write_text(
            """\
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ObjectType
metadata:
  name: Foo
spec:
  backing: {type: sqlalchemy, model: app.models.Product}
  title_property: name
  properties:
    id: {type: integer, required: true, readonly: true}
    name: {type: string, required: true}
---
apiVersion: ontology.juno.gravithy.com.br/v1
kind: ActionType
metadata:
  name: doFoo
spec:
  target: Foo
  inputs:
    x: {type: integer, required: true}
  authorization: {roles: [admin]}
  effect: {handler: app.ontology.actions.foo.do_foo}
""",
            encoding="utf-8",
        )
        count = load_file(fresh_registry, multi)
        assert count == 2
        assert "Foo" in fresh_registry.list_object_types()
        assert "doFoo" in fresh_registry.list_action_types()


# =============================================================================
# Sanidade do path padrão
# =============================================================================


def test_definitions_dir_exists():
    """Garante que o path padrão aponta para um diretório real com YAMLs."""
    assert DEFINITIONS_DIR.exists(), f"DEFINITIONS_DIR não existe: {DEFINITIONS_DIR}"
    yamls = list(DEFINITIONS_DIR.glob("*.yaml"))
    assert len(yamls) >= 3, "esperava ao menos 3 YAMLs em definitions/"
