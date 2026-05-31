"""
ai_tools.py - tools auto-geradas a partir do Registry para o Coordinator.

Para cada ObjectType registrado gera:
  - search_<snake>(query, limit)
  - get_<snake>_by_id(id)
  - list_<snake>(limit, offset, order_by, filter_*)

Para cada ActionType gera:
  - propose_<action_name>(target_id, <inputs>) → retorna payload de confirmacao,
    NAO executa. Usuario humano confirma via UI.

Formato compativel com OpenAI/Anthropic function calling. O Coordinator do JUNO
hoje usa Ollama (qwen3:8b) que aceita o mesmo schema.

Dispatcher:
  dispatch_tool_call(name, args, user, db, registry) -> dict
    Roteia 'search_produto' -> runtime.search_objects, etc.
    'propose_*' nao toca o banco — devolve PROPOSED_ACTION dict para o frontend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import runtime

if TYPE_CHECKING:
    from .registry import Registry


# =============================================================================
# Helpers
# =============================================================================


def _snake(name: str) -> str:
    """PascalCase -> snake_case."""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


_JSON_SCHEMA_TYPE = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "datetime": "string",
    "uuid": "string",
    "money": "number",
    "percent": "number",
    "enum": "string",
    "ref": "integer",
    "array": "array",
    "cnpj": "string",
    "cpf": "string",
}


def _prop_to_schema(prop) -> dict[str, Any]:
    """PropertySpec -> JSON Schema fragment."""
    raw = getattr(prop.type, "value", prop.type)
    schema: dict[str, Any] = {"type": _JSON_SCHEMA_TYPE.get(raw, "string")}
    if prop.description:
        schema["description"] = prop.description
    if prop.min is not None:
        if schema["type"] in ("number", "integer"):
            schema["minimum"] = prop.min
        elif schema["type"] == "string":
            schema["minLength"] = int(prop.min)
    if prop.max is not None:
        if schema["type"] in ("number", "integer"):
            schema["maximum"] = prop.max
    if prop.max_length is not None and schema["type"] == "string":
        schema["maxLength"] = prop.max_length
    if prop.enum_values:
        schema["enum"] = prop.enum_values
    return schema


def _function_tool(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    """Constroi um spec de tool no formato OpenAI/Anthropic function calling."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# =============================================================================
# Builder principal
# =============================================================================


def build_tools_from_registry(registry: Registry) -> list[dict[str, Any]]:
    """
    Gera todas as tools a partir do Registry.

    Retorna lista de tool specs prontos para enviar ao Coordinator.
    """
    tools: list[dict[str, Any]] = []

    for type_name in registry.list_object_types():
        obj = registry.get_object_type(type_name)
        snake = _snake(type_name)
        desc_short = (obj.metadata.description or f"ObjectType {type_name}").strip().split("\n")[0]

        # search_<snake>
        tools.append(
            _function_tool(
                f"search_{snake}",
                f"Busca textual em '{type_name}' ({desc_short}). Procura no campo '{obj.spec.title_property}'.",
                {
                    "query": {"type": "string", "description": "Texto a buscar"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
                ["query"],
            )
        )

        # get_<snake>_by_id
        tools.append(
            _function_tool(
                f"get_{snake}_by_id",
                f"Busca um '{type_name}' especifico pelo id.",
                {"id": {"type": "integer", "description": f"id do {type_name}"}},
                ["id"],
            )
        )

        # list_<snake>
        tools.append(
            _function_tool(
                f"list_{snake}",
                f"Lista paginada de '{type_name}'.",
                {
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
                    "offset": {"type": "integer", "default": 0, "minimum": 0},
                    "order_by": {
                        "type": "string",
                        "description": "campo a ordenar (prefixo '-' para desc)",
                    },
                },
                [],
            )
        )

    # propose_<action> por ActionType
    for action_name in registry.list_action_types():
        action = registry.get_action_type(action_name)
        target = action.spec.target
        properties: dict[str, Any] = {
            "target_id": {"type": "integer", "description": f"id do {target} alvo"},
        }
        required = ["target_id"]
        for iname, iprop in action.spec.inputs.items():
            properties[iname] = _prop_to_schema(iprop)
            if iprop.required:
                required.append(iname)

        desc = (action.metadata.description or f"Action {action_name}").strip().split("\n")[0]
        tools.append(
            _function_tool(
                f"propose_{action_name}",
                f"PROPOE (nao executa) a action '{action_name}' sobre {target}. "
                f"{desc} Retorna preview para confirmacao humana.",
                properties,
                required,
            )
        )

    return tools


# =============================================================================
# System prompt fragment
# =============================================================================


def build_system_prompt_fragment(registry: Registry) -> str:
    """
    Markdown listando ObjectTypes e Actions disponiveis para o Coordinator.
    Anexado ao SYSTEM_PROMPT no startup.
    """
    lines = ["## Object Types disponiveis", ""]
    for type_name in registry.list_object_types():
        obj = registry.get_object_type(type_name)
        tags = ", ".join(obj.metadata.tags) if obj.metadata.tags else ""
        desc = (obj.metadata.description or "").strip().split("\n")[0]
        props_count = len(obj.spec.properties) + len(obj.spec.computed_properties)
        actions_count = len(registry.list_action_types_for(type_name))
        lines.append(
            f"- **{type_name}**{' (' + tags + ')' if tags else ''}: "
            f"{desc} [{props_count} props, {actions_count} actions]"
        )

    lines.extend(["", "## Actions disponiveis (sempre via propose_*)", ""])
    for action_name in registry.list_action_types():
        action = registry.get_action_type(action_name)
        roles = ", ".join(action.spec.authorization.roles) or "qualquer"
        desc = (action.metadata.description or "").strip().split("\n")[0]
        lines.append(f"- `propose_{action_name}` ({action.spec.target}): {desc} [roles: {roles}]")

    lines.extend(
        [
            "",
            "## Regras",
            "1. Use *_by_id/list_*/search_* para LER dados reais antes de responder.",
            "2. Para acoes que mudam estado, sempre `propose_*` — usuario humano confirma na UI.",
            "3. Nunca invente IDs nem valores. Se nao tem dado, diga.",
            "",
        ]
    )
    return "\n".join(lines)


# =============================================================================
# Proposed Action payload (sem persistir)
# =============================================================================


def build_proposed_action_payload(
    action_name: str,
    target_id: int,
    inputs: dict[str, Any],
    *,
    proposed_by: str = "ai_coordinator",
    preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Quando a IA chama propose_*, retorna um dict que o frontend transforma
    em card de confirmacao. NAO persiste no banco — eh ephemero por turno.
    """
    return {
        "kind": "proposed_action",
        "action": action_name,
        "target_id": target_id,
        "inputs": inputs,
        "proposed_by": proposed_by,
        "status": "awaiting_confirmation",
        "preview": preview,
        "next_step": f"POST /api/v1/ontology/{{target_type}}/{target_id}/actions/{action_name}",
    }


# =============================================================================
# Dispatcher
# =============================================================================


class UnknownToolError(Exception):
    """Nome de tool nao bate com nenhum spec gerado."""


def dispatch_tool_call(
    tool_name: str,
    args: dict[str, Any],
    *,
    user,
    db,
    registry: Registry,
) -> dict[str, Any]:
    """
    Roteia uma chamada de tool para a implementacao correta.

    Comportamento:
      - search_<snake>     -> runtime.search_objects
      - get_<snake>_by_id  -> runtime.fetch_by_id
      - list_<snake>       -> runtime.list_objects
      - propose_<action>   -> build_proposed_action_payload (com preview dry-run se possivel)
    """
    # Mapa de snake -> tipo (case-insensitive)
    type_by_snake = {_snake(t): t for t in registry.list_object_types()}

    # propose_<action>
    if tool_name.startswith("propose_"):
        action_name = tool_name[len("propose_") :]
        try:
            action_spec = registry.get_action_type(action_name)
        except KeyError:
            raise UnknownToolError(f"action '{action_name}' nao registrada")
        target_id = args.get("target_id")
        if target_id is None:
            raise UnknownToolError(f"propose_{action_name}: target_id obrigatorio")
        inputs = {k: v for k, v in args.items() if k != "target_id"}

        # Tenta dry-run para gerar preview, mas falha silencioso (preview opcional)
        preview = None
        rejection_error: str | None = None
        try:
            result = runtime.execute_action(
                action_name,
                target_id,
                inputs,
                user=user,
                db=db,
                registry=registry,
                dry_run=True,
                actor_type="ai_coordinator",
                confirmed_by=0,
            )
            preview = result.to_dict()
        except Exception as e:  # noqa: BLE001
            preview = {"dry_run_error": str(e)}
            rejection_error = str(e)

        # Sem6+: persistir tentativa rejeitada em audit_logs (compliance)
        if rejection_error is not None:
            try:
                import json

                from app.models import AuditLog

                company_ids = getattr(user, "company_ids", None)
                log = AuditLog(
                    company_id=company_ids[0] if company_ids else None,
                    user_id=getattr(user, "user_id", None),
                    action=f"propose_rejected:{action_name}",
                    resource_type=action_spec.spec.target,
                    new_values=json.dumps(
                        {
                            "status": "rejected",
                            "target_id": target_id,
                            "inputs": inputs,
                            "rejection_error": rejection_error,
                            "actor_type": "ai_coordinator",
                        },
                        default=str,
                        ensure_ascii=False,
                    ),
                    success=False,
                    severity="warning",
                )
                db.add(log)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()

        return build_proposed_action_payload(action_name, target_id, inputs, preview=preview)

    # Read tools: descobre prefixo + tipo
    for prefix, fn_name in (
        ("search_", "search_objects"),
        ("get_", "fetch_by_id"),
        ("list_", "list_objects"),
    ):
        if not tool_name.startswith(prefix):
            continue
        suffix = tool_name[len(prefix) :]
        # get_*_by_id tem sufixo "_by_id"
        if fn_name == "fetch_by_id" and suffix.endswith("_by_id"):
            suffix = suffix[: -len("_by_id")]
        type_name = type_by_snake.get(suffix)
        if type_name is None:
            continue

        if fn_name == "search_objects":
            items = runtime.search_objects(
                type_name,
                args["query"],
                user=user,
                db=db,
                registry=registry,
                limit=args.get("limit", 20),
            )
            return {"kind": "search_result", "type": type_name, "items": items}

        if fn_name == "fetch_by_id":
            data = runtime.fetch_by_id(
                type_name,
                args["id"],
                user=user,
                db=db,
                registry=registry,
            )
            return {"kind": "object", "type": type_name, "data": data}

        if fn_name == "list_objects":
            res = runtime.list_objects(
                type_name,
                user=user,
                db=db,
                registry=registry,
                limit=args.get("limit", 50),
                offset=args.get("offset", 0),
                order_by=args.get("order_by"),
            )
            res["kind"] = "list_result"
            res["type"] = type_name
            return res

    raise UnknownToolError(f"tool '{tool_name}' nao reconhecida")
