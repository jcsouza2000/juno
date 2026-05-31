"""
cli.py - CLI da ontologia.

Uso:
    python -m app.ontology.cli validate
    python -m app.ontology.cli list
    python -m app.ontology.cli describe Produto

Saida amigavel com cores (sem dependencia externa — usa ANSI nativo).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Imports tardios dos geradores (preguicoso para nao quebrar CLI se Jinja2 faltar)

# Cores ANSI
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _supports_color() -> bool:
    """Detecta se o terminal suporta ANSI. Em PowerShell moderno e cmd.exe Win10+ sim."""
    return sys.stdout.isatty()


def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}" if _supports_color() else text


# =============================================================================
# Comandos
# =============================================================================


def cmd_validate(args) -> int:
    """Carrega definitions/ e roda validate_consistency. Retorna exit code."""
    from .loader import OntologyLoadError, load_all
    from .registry import registry

    registry.reset()

    definitions_dir = Path(args.dir) if args.dir else None
    # Em prod, validar models exige imports que podem nao estar disponiveis em CI.
    # Permitir override via flag explicita.
    import os as _os

    if _os.environ.get("JUNO_ENV", "").lower() == "production":
        check_models = False
    else:
        check_models = not args.skip_models

    print(_c(CYAN, "→ Carregando definicoes..."))

    try:
        summary = load_all(registry, definitions_dir=definitions_dir)
    except OntologyLoadError as e:
        print(_c(RED, f"✗ Erro de carregamento: {e}"))
        return 1

    for filename, count in summary.items():
        print(f"  {_c(GREEN, '✓')} {filename} ({count} recurso{'s' if count != 1 else ''})")

    print()
    print(_c(CYAN, "→ Validando consistencia..."))

    errors = registry.validate_consistency(check_models=check_models)

    if not errors:
        print(_c(GREEN, "✓ Todas as validacoes passaram"))
        print()
        print(_c(BOLD, "Resumo:"))
        print(f"  ObjectTypes: {len(registry.list_object_types())}")
        print(f"  ActionTypes: {len(registry.list_action_types())}")
        print(f"  MarkingSets: {len(registry._marking_sets)}")  # noqa: SLF001
        return 0

    print(_c(RED, f"✗ {len(errors)} erro(s) de consistencia:"))
    for err in errors:
        print(f"  {_c(RED, '•')} {err}")
    return 1


def cmd_list(args) -> int:
    """Lista ObjectTypes e ActionTypes registrados."""
    from .loader import OntologyLoadError, load_all
    from .registry import registry

    registry.reset()
    try:
        load_all(registry)
    except OntologyLoadError as e:
        print(_c(RED, f"✗ {e}"))
        return 1

    print(_c(BOLD, "Object Types:"))
    for name in registry.list_object_types():
        obj = registry.get_object_type(name)
        actions = registry.list_action_types_for(name)
        tags = ", ".join(obj.metadata.tags) if obj.metadata.tags else "—"
        print(
            f"  {_c(CYAN, name):24}  {len(obj.spec.properties)} props · "
            f"{len(obj.spec.links)} links · {len(actions)} actions  "
            f"{_c(DIM, '[' + tags + ']')}"
        )

    print()
    print(_c(BOLD, "Action Types:"))
    for name in registry.list_action_types():
        action = registry.get_action_type(name)
        target = action.spec.target
        roles = ", ".join(action.spec.authorization.roles) or "—"
        print(f"  {_c(CYAN, name):28}  target={target}  " f"{_c(DIM, 'roles=[' + roles + ']')}")

    return 0


def cmd_describe(args) -> int:
    """Mostra detalhe de um ObjectType ou ActionType."""
    from .loader import OntologyLoadError, load_all
    from .registry import registry

    registry.reset()
    try:
        load_all(registry)
    except OntologyLoadError as e:
        print(_c(RED, f"✗ {e}"))
        return 1

    name = args.name

    # Tenta ObjectType primeiro
    if name in registry.list_object_types():
        obj = registry.get_object_type(name)
        spec = obj.spec
        print(_c(BOLD + CYAN, f"ObjectType: {name}"))
        if obj.metadata.description:
            print(_c(DIM, obj.metadata.description.strip()))
        print()
        print(_c(BOLD, "  Backing:"), f"{spec.backing.type} → {spec.backing.model}")
        print(_c(BOLD, "  Title:"), spec.title_property)
        print()
        print(_c(BOLD, f"  Properties ({len(spec.properties)}):"))
        for pname, p in spec.properties.items():
            req = _c(YELLOW, "*") if p.required else " "
            mark = _c(DIM, f" [{p.marking}]") if p.marking else ""
            print(f"    {req} {pname}: {p.type.value}{mark}")
        if spec.computed_properties:
            print()
            print(_c(BOLD, f"  Computed ({len(spec.computed_properties)}):"))
            for cname, c in spec.computed_properties.items():
                print(f"    · {cname}: {c.type.value} = {_c(DIM, c.formula)}")
        if spec.links:
            print()
            print(_c(BOLD, f"  Links ({len(spec.links)}):"))
            for lname, link in spec.links.items():
                print(f"    → {lname}: {link.cardinality.value} {link.target}")
        if spec.actions:
            print()
            print(_c(BOLD, "  Actions:"), ", ".join(spec.actions))
        return 0

    # Tenta ActionType
    if name in registry.list_action_types():
        action = registry.get_action_type(name)
        action_spec = action.spec
        print(_c(BOLD + CYAN, f"ActionType: {name}"))
        if action.metadata.description:
            print(_c(DIM, action.metadata.description.strip()))
        print()
        print(_c(BOLD, "  Target:"), action_spec.target)
        print(_c(BOLD, "  Roles:"), ", ".join(action_spec.authorization.roles) or "—")
        print(_c(BOLD, "  Confirmação humana:"), action_spec.authorization.require_confirmation)
        print(_c(BOLD, "  Dry-run:"), action_spec.dry_run)
        print()
        print(_c(BOLD, f"  Inputs ({len(action_spec.inputs)}):"))
        for iname, i in action_spec.inputs.items():
            req = _c(YELLOW, "*") if i.required else " "
            print(f"    {req} {iname}: {i.type.value}")
        if action_spec.validation:
            print()
            print(_c(BOLD, f"  Validations ({len(action_spec.validation)}):"))
            for v in action_spec.validation:
                sev = _c(RED if v.severity.value == "error" else YELLOW, v.severity.value)
                print(f"    · [{sev}] {v.rule}")
        print()
        print(_c(BOLD, "  Handler:"), action_spec.effect.handler)
        return 0

    print(_c(RED, f"✗ '{name}' não é um ObjectType nem um ActionType registrado"))
    return 1


def cmd_generate_sdk(args) -> int:
    """Gera SDK Python ou TypeScript para os tipos carregados."""
    from .loader import OntologyLoadError, load_all
    from .registry import registry

    registry.reset()
    try:
        load_all(registry)
    except OntologyLoadError as e:
        print(_c(RED, f"✗ Erro: {e}"))
        return 1

    out_dir = Path(args.out).resolve()
    lang = args.lang.lower()

    print(_c(CYAN, f"→ Gerando SDK {lang} em {out_dir}"))

    if lang == "python":
        try:
            from .sdk_gen.python import generate_python_sdk
        except ImportError as e:
            print(_c(RED, f"✗ Jinja2 nao instalado: {e}"))
            return 1
        written = generate_python_sdk(registry, out_dir)
    elif lang in ("typescript", "ts"):
        try:
            from .sdk_gen.typescript import generate_typescript_sdk
        except ImportError as e:
            print(_c(RED, f"✗ Jinja2 nao instalado: {e}"))
            return 1
        written = generate_typescript_sdk(registry, out_dir)
    else:
        print(_c(RED, f"✗ Lang nao suportado: {lang} (use python | typescript)"))
        return 1

    print(_c(GREEN, f"✓ {len(written)} arquivos gerados:"))
    for name, path in written.items():
        size_kb = path.stat().st_size / 1024
        print(f"  {_c(GREEN, '✓')} {name:30s} ({size_kb:.1f} KB)")

    return 0


# =============================================================================
# Entry point
# =============================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="juno ontology",
        description="CLI da ontologia JUNO",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Valida YAMLs em definitions/")
    p_validate.add_argument("--dir", help="Override do diretorio de definitions")
    p_validate.add_argument(
        "--skip-models",
        action="store_true",
        help="Nao valida que backing.model resolve (mais rapido em CI)",
    )
    p_validate.set_defaults(func=cmd_validate)

    p_list = sub.add_parser("list", help="Lista ObjectTypes e ActionTypes")
    p_list.set_defaults(func=cmd_list)

    p_describe = sub.add_parser("describe", help="Detalha um ObjectType/ActionType")
    p_describe.add_argument("name", help="Nome do tipo")
    p_describe.set_defaults(func=cmd_describe)

    p_gen = sub.add_parser("generate-sdk", help="Gera SDK Python ou TypeScript")
    p_gen.add_argument("--lang", choices=["python", "typescript", "ts"], required=True)
    p_gen.add_argument("--out", required=True, help="Diretorio de saida")
    p_gen.set_defaults(func=cmd_generate_sdk)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
