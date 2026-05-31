"""Testes do Workshop form-builder."""

from __future__ import annotations

import pytest

from app.ontology.workshop import build_form_spec, list_workshop_apps


def test_list_apps(loaded_registry):
    apps = list_workshop_apps(loaded_registry)
    names = {a["object_type"] for a in apps}
    assert "Produto" in names
    assert "OrdemProducao" in names
    for a in apps:
        assert a["fields"] > 0


def test_form_spec_produto(loaded_registry):
    spec = build_form_spec("Produto", loaded_registry)
    assert spec["object_type"] == "Produto"
    assert spec["title_property"] == "name"
    fields = {f["name"]: f for f in spec["fields"]}
    assert "name" in fields
    assert fields["name"]["required"] is True
    assert fields["name"]["widget"] == "text"
    assert fields["sale_price"]["widget"] == "currency"
    assert fields["sale_price"]["currency"] == "BRL"
    assert fields["sale_price"]["marking"] == "ConfidencialComercial"
    # Computed properties
    assert any(c["name"] == "margem_percentual" for c in spec["computed"])


def test_form_spec_includes_actions(loaded_registry):
    spec = build_form_spec("Produto", loaded_registry)
    action_names = [a["name"] for a in spec["actions"]]
    assert "atualizarPreco" in action_names
    upd = next(a for a in spec["actions"] if a["name"] == "atualizarPreco")
    inputs = {i["name"]: i for i in upd["inputs"]}
    assert inputs["novo_preco"]["required"] is True
    assert inputs["novo_preco"]["widget"] == "currency"
    assert upd["require_confirmation"] is True
    assert upd["dry_run_supported"] is True


def test_form_spec_unknown_raises(loaded_registry):
    with pytest.raises(KeyError):
        build_form_spec("Inexistente", loaded_registry)


def test_label_humanizes(loaded_registry):
    spec = build_form_spec("Produto", loaded_registry)
    fields = {f["name"]: f for f in spec["fields"]}
    assert fields["sale_price"]["label"] == "Preço de Venda"
    assert fields["standard_cost"]["label"] == "Custo Padrão"
