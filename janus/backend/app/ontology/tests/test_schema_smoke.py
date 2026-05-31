"""
test_schema_smoke.py — testes mínimos do schema Pydantic da ontologia.

Estes testes não dependem do loader; validam apenas que os modelos Pydantic
aceitam estruturas corretas e rejeitam estruturas inválidas.

Quando o loader for implementado (Semana 1), adicionaremos test_loader.py
que carrega os YAMLs reais de definitions/.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.ontology.schema import (
    ObjectTypeResource,
    parse_resource,
)

VALID_OBJECT_TYPE: dict[str, Any] = {
    "apiVersion": "ontology.juno.gravithy.com.br/v1",
    "kind": "ObjectType",
    "metadata": {"name": "Produto", "description": "Item comercializável"},
    "spec": {
        "backing": {"type": "sqlalchemy", "model": "app.models.Product"},
        "title_property": "name",
        "properties": {
            "id": {"type": "integer", "required": True, "readonly": True},
            "name": {"type": "string", "required": True, "max_length": 255},
            "sale_price": {"type": "money", "currency": "BRL", "min": 0},
        },
    },
}


def test_parse_valid_object_type():
    resource = parse_resource(VALID_OBJECT_TYPE)
    assert isinstance(resource, ObjectTypeResource)
    assert resource.metadata.name == "Produto"
    assert resource.spec.properties["sale_price"].currency == "BRL"


def test_unknown_kind_raises():
    with pytest.raises(ValueError, match="Unknown ontology kind"):
        parse_resource({**VALID_OBJECT_TYPE, "kind": "Foo"})


def test_extra_field_in_property_rejected():
    bad = {
        **VALID_OBJECT_TYPE,
        "spec": {
            **VALID_OBJECT_TYPE["spec"],
            "properties": {
                "id": {"type": "integer", "extra_field": "nope"},
            },
        },
    }
    with pytest.raises(ValidationError):
        parse_resource(bad)
