"""
sdk_gen/typescript.py - gera SDK TypeScript a partir do Registry.

Cria estrutura:
  out_dir/
    index.ts        # re-exports
    _base.ts        # cliente HTTP + tipos
    produto.ts      # 1 por ObjectType
    pedido_venda.ts
    ...
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from ..registry import Registry

_TEMPLATE_DIR = Path(__file__).parent / "templates"


# =============================================================================
# Type mapping YAML -> TypeScript
# =============================================================================

_TS_TYPE_MAP = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "date": "string",  # ISO date
    "datetime": "string",
    "uuid": "string",
    "money": "number",
    "percent": "number",
    "enum": "string",
    "ref": "number",
    "array": "unknown[]",
    "cnpj": "string",
    "cpf": "string",
}


def _ts_type(prop_type: str) -> str:
    return _TS_TYPE_MAP.get(prop_type, "unknown")


def _camel_case(name: str) -> str:
    """PascalCase ou snake_case -> camelCase (primeira letra minuscula)."""
    if not name:
        return name
    # Se ja' PascalCase
    if name[0].isupper():
        return name[0].lower() + name[1:]
    # snake_case
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _pascal_case(name: str) -> str:
    if not name:
        return name
    if "_" in name:
        return "".join(p.capitalize() for p in name.split("_"))
    return name[0].upper() + name[1:]


def _file_name(class_name: str) -> str:
    """ObjectType -> nome do arquivo TS (kebab-case ou snake-case do disco)."""
    out = []
    for i, ch in enumerate(class_name):
        if ch.isupper() and i > 0 and not class_name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


# =============================================================================
# Generator
# =============================================================================


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _build_context(name: str, spec, registry: Registry) -> dict[str, Any]:
    s = spec.spec
    properties = {}
    for pname, p in s.properties.items():
        properties[pname] = {"ts_type": _ts_type(p.type.value), "required": p.required}

    computed = {}
    for cname, c in s.computed_properties.items():
        computed[cname] = {"ts_type": _ts_type(c.type.value), "formula": c.formula}

    links = {}
    for lname, link in s.links.items():
        links[lname] = {"target": link.target, "camel": _pascal_case(lname)}

    actions = {}
    for action_name in s.actions:
        try:
            action_spec = registry.get_action_type(action_name)
        except KeyError:
            continue
        action_inputs = {}
        for iname, iprop in action_spec.spec.inputs.items():
            action_inputs[iname] = {
                "ts_type": _ts_type(iprop.type.value),
                "required": iprop.required,
            }
        actions[action_name] = {
            "camel_name": _camel_case(action_name),
            "input_iface": f"{_pascal_case(action_name)}Inputs",
            "description": action_spec.metadata.description,
            "inputs": action_inputs,
        }

    return {
        "object_type": name,
        "class_name": name,
        "camel_name": _camel_case(name),
        "description": spec.metadata.description,
        "properties": properties,
        "computed_properties": computed,
        "links": links,
        "actions": actions,
    }


def generate_typescript_sdk(registry: Registry, out_dir: Path) -> dict[str, Path]:
    """Gera SDK TypeScript em out_dir/. Retorna dict {nome: Path}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = _env()
    stamp = _dt.datetime.utcnow().isoformat() + "Z"

    written: dict[str, Path] = {}

    # _base.ts
    base_tpl = env.get_template("ts_base.ts.j2")
    p = out_dir / "_base.ts"
    p.write_text(base_tpl.render(stamp=stamp), encoding="utf-8")
    written["_base.ts"] = p

    obj_tpl = env.get_template("ts_object.ts.j2")
    modules: list[str] = []
    for name in registry.list_object_types():
        spec = registry.get_object_type(name)
        ctx = _build_context(name, spec, registry)
        file_stem = _file_name(name)
        path = out_dir / f"{file_stem}.ts"
        path.write_text(obj_tpl.render(stamp=stamp, **ctx), encoding="utf-8")
        written[f"{file_stem}.ts"] = path
        modules.append(file_stem)

    # index.ts
    idx_tpl = env.get_template("ts_index.ts.j2")
    p = out_dir / "index.ts"
    p.write_text(idx_tpl.render(stamp=stamp, modules=modules), encoding="utf-8")
    written["index.ts"] = p

    return written
