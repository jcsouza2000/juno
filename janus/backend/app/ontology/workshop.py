"""
workshop.py - form-builder no-code.

Gera, a partir do schema da ontologia, especificacao de FormSpec que o
frontend renderiza como UI de CRUD/Action sem precisar de PR.

FormSpec:
  {
    "object_type": "Produto",
    "title": "Produto",
    "description": "...",
    "fields": [
      {"name": "name", "label": "Nome", "type": "text", "required": true,
       "marking": null, "readonly": false, "max_length": 255},
      ...
    ],
    "computed": [
      {"name": "margem_percentual", "label": "Margem %", "type": "number"}
    ],
    "actions": [
      {"name": "atualizarPreco", "label": "Atualizar Preço",
       "inputs": [...], "require_confirmation": true}
    ],
    "links": [...]
  }
"""

from __future__ import annotations

from typing import Any

# Mapping property type -> widget type (frontend)
_WIDGET_MAP = {
    "string": "text",
    "integer": "number",
    "number": "number",
    "boolean": "checkbox",
    "date": "date",
    "datetime": "datetime",
    "money": "currency",
    "percent": "percent",
    "enum": "select",
    "uuid": "text",
    "ref": "ref-picker",
    "array": "tags",
    "cnpj": "cnpj",
    "cpf": "cpf",
}


def _label(name: str) -> str:
    """snake_case -> Title Case humano. company_id -> 'Empresa', sale_price -> 'Preço'..."""
    overrides = {
        "id": "ID",
        "company_id": "Empresa",
        "customer_id": "Cliente",
        "product_id": "Produto",
        "name": "Nome",
        "sale_price": "Preço de Venda",
        "standard_cost": "Custo Padrão",
        "stock_quantity": "Estoque",
        "min_stock": "Estoque Mínimo",
        "category": "Categoria",
        "created_at": "Criado em",
        "revenue": "Receita",
        "discount": "Desconto",
        "total": "Total",
        "planned_date": "Data Planejada",
        "actual_date": "Data Real",
        "planned_qty": "Qtd Planejada",
        "actual_qty": "Qtd Real",
        "planned_cost": "Custo Planejado",
        "actual_cost": "Custo Real",
        "status": "Status",
    }
    if name in overrides:
        return overrides[name]
    return name.replace("_", " ").title()


def build_form_spec(object_type_name: str, registry) -> dict[str, Any]:
    """Gera spec do form para o ObjectType. Levanta KeyError se nao existe."""
    obj = registry.get_object_type(object_type_name)
    spec = obj.spec

    fields = []
    for name, prop in spec.properties.items():
        ptype = prop.type.value if hasattr(prop.type, "value") else prop.type
        widget = _WIDGET_MAP.get(ptype, "text")
        f: dict[str, Any] = {
            "name": name,
            "label": _label(name),
            "widget": widget,
            "type": ptype,
            "required": prop.required,
            "readonly": prop.readonly,
            "marking": prop.marking,
        }
        if prop.max_length:
            f["max_length"] = prop.max_length
        if prop.min is not None:
            f["min"] = prop.min
        if prop.max is not None:
            f["max"] = prop.max
        if prop.enum_values:
            f["options"] = prop.enum_values
        if prop.enum_hint:
            f["hint_options"] = prop.enum_hint
        if prop.currency:
            f["currency"] = prop.currency
        if prop.description:
            f["help"] = prop.description
        fields.append(f)

    computed = []
    for name, cp in spec.computed_properties.items():
        ptype = cp.type.value if hasattr(cp.type, "value") else cp.type
        computed.append(
            {
                "name": name,
                "label": _label(name),
                "type": ptype,
                "widget": _WIDGET_MAP.get(ptype, "text"),
                "formula_preview": cp.formula,
            }
        )

    actions = []
    for action_name in spec.actions:
        try:
            act = registry.get_action_type(action_name)
        except KeyError:
            continue
        action_inputs = []
        for iname, iprop in act.spec.inputs.items():
            ptype = iprop.type.value if hasattr(iprop.type, "value") else iprop.type
            inp: dict[str, Any] = {
                "name": iname,
                "label": _label(iname),
                "widget": _WIDGET_MAP.get(ptype, "text"),
                "type": ptype,
                "required": iprop.required,
            }
            if iprop.max_length:
                inp["max_length"] = iprop.max_length
            if iprop.min is not None:
                inp["min"] = iprop.min
            if iprop.enum_hint:
                inp["hint_options"] = iprop.enum_hint
            if iprop.currency:
                inp["currency"] = iprop.currency
            action_inputs.append(inp)
        actions.append(
            {
                "name": action_name,
                "label": _label(action_name),
                "description": act.metadata.description,
                "inputs": action_inputs,
                "require_confirmation": act.spec.authorization.require_confirmation,
                "roles": act.spec.authorization.roles,
                "dry_run_supported": act.spec.dry_run == "supported",
            }
        )

    links = []
    for lname, link in spec.links.items():
        links.append(
            {
                "name": lname,
                "label": _label(lname),
                "target": link.target,
                "cardinality": link.cardinality.value,
            }
        )

    return {
        "object_type": object_type_name,
        "title": _label(object_type_name),
        "description": obj.metadata.description,
        "title_property": spec.title_property,
        "fields": fields,
        "computed": computed,
        "actions": actions,
        "links": links,
        "markings_inherited": spec.markings.inherit,
    }


def list_workshop_apps(registry) -> list[dict[str, Any]]:
    """Lista todos os ObjectTypes como apps potenciais do Workshop."""
    apps = []
    for name in registry.list_object_types():
        obj = registry.get_object_type(name)
        apps.append(
            {
                "object_type": name,
                "title": _label(name),
                "description": (obj.metadata.description or "").strip().split("\n")[0],
                "fields": len(obj.spec.properties),
                "actions": len(obj.spec.actions),
                "links": len(obj.spec.links),
            }
        )
    return apps
