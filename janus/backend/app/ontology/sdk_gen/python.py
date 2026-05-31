"""
sdk_gen/python.py - gera SDK Python tipado a partir do Registry.

Cria estrutura:
  out_dir/juno_ontology/
    __init__.py    # gerado
    _base.py       # gerado (mas constante, vem de python_base.py.j2)
    produto.py     # gerado por ObjectType
    pedido_venda.py
    ...

Cada arquivo gerado e' marcado como tal no header. Para regerar:
    python -m app.ontology.cli generate-sdk --lang python --out sdk/python/
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
# Type mapping YAML -> Python
# =============================================================================

_PY_TYPE_MAP = {
    "string": "str | None",
    "integer": "int | None",
    "number": "float | None",
    "boolean": "bool | None",
    "date": "str | None",
    "datetime": "str | None",
    "uuid": "str | None",
    "money": "float | None",  # serializado como number na API
    "percent": "float | None",
    "enum": "str | None",
    "ref": "int | None",
    "array": "list | None",
    "cnpj": "str | None",
    "cpf": "str | None",
}


def _py_type_for_required(prop_type: str, required: bool) -> str:
    base = _PY_TYPE_MAP.get(prop_type, "Any")
    if required and base.endswith(" | None"):
        return base[: -len(" | None")]
    return base


def _snake_case(name: str) -> str:
    """PascalCase -> snake_case."""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
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


def _build_object_context(name: str, spec, registry: Registry) -> dict[str, Any]:
    """Monta o dict que vai pro template python_object.py.j2."""
    s = spec.spec
    properties = {}
    for pname, p in s.properties.items():
        properties[pname] = {
            "py_type": _py_type_for_required(p.type.value, p.required),
            "required": p.required,
        }
    computed = {}
    for cname, c in s.computed_properties.items():
        computed[cname] = {
            "py_type": _py_type_for_required(c.type.value, False),
            "formula": c.formula,
        }
    links = {}
    for lname, link in s.links.items():
        links[lname] = {
            "target": link.target,
            "cardinality": link.cardinality.value,
        }

    actions = {}
    for action_name in s.actions:
        try:
            action_spec = registry.get_action_type(action_name)
        except KeyError:
            continue
        action_inputs = {}
        for iname, iprop in action_spec.spec.inputs.items():
            action_inputs[iname] = {
                "py_type": _py_type_for_required(iprop.type.value, iprop.required),
                "required": iprop.required,
            }
        actions[action_name] = {
            "snake_name": _snake_case(action_name),
            "description": action_spec.metadata.description,
            "inputs": action_inputs,
        }

    return {
        "object_type": name,
        "class_name": name,
        "snake_name": _snake_case(name),
        "description": spec.metadata.description,
        "properties": properties,
        "computed_properties": computed,
        "links": links,
        "actions": actions,
    }


def generate_python_sdk(registry: Registry, out_dir: Path) -> dict[str, Path]:
    """
    Gera SDK Python no diretorio `out_dir/juno_ontology/`.

    Returns:
        dict {arquivo_logico: Path absoluto} dos arquivos gerados.
    """
    out_dir = Path(out_dir)
    pkg_dir = out_dir / "juno_ontology"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    env = _env()
    stamp = _dt.datetime.utcnow().isoformat() + "Z"

    written: dict[str, Path] = {}

    # _base.py
    base_tpl = env.get_template("python_base.py.j2")
    base_path = pkg_dir / "_base.py"
    base_path.write_text(base_tpl.render(stamp=stamp), encoding="utf-8")
    written["_base.py"] = base_path

    # Um arquivo por ObjectType
    object_tpl = env.get_template("python_object.py.j2")
    classes: list[str] = []
    module_map: list[tuple[str, str]] = []
    for name in registry.list_object_types():
        spec = registry.get_object_type(name)
        ctx = _build_object_context(name, spec, registry)
        snake = ctx["snake_name"]
        path = pkg_dir / f"{snake}.py"
        path.write_text(object_tpl.render(stamp=stamp, **ctx), encoding="utf-8")
        written[f"{snake}.py"] = path
        classes.append(name)
        module_map.append((name, snake))

    # __init__.py
    init_tpl = env.get_template("python_init.py.j2")
    init_path = pkg_dir / "__init__.py"
    init_path.write_text(
        init_tpl.render(stamp=stamp, classes=classes, module_map=module_map),
        encoding="utf-8",
    )
    written["__init__.py"] = init_path

    return written
