"""
api.py - FastAPI router que expoe a ontologia por HTTP.

Rotas (Sem2 + Sem3):
  GET    /api/v1/ontology/types
  GET    /api/v1/ontology/types/{name}
  GET    /api/v1/ontology/{type}                    list paginado
  GET    /api/v1/ontology/{type}/{id}               fetch_by_id
  GET    /api/v1/ontology/{type}/search?q=...       search textual
  GET    /api/v1/ontology/{type}/{id}/links/{link}  resolve_link
  POST   /api/v1/ontology/{type}/{id}/actions/{action_name}   execute_action
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db

from . import runtime
from .permissions import PermissionDenied, UserContext
from .registry import registry as _global_registry

router = APIRouter(prefix="/api/v1/ontology", tags=["ontology"])


# =============================================================================
# Schemas de request
# =============================================================================


class ActionRequest(BaseModel):
    """Payload de execute_action. inputs e' livre — validado contra YAML."""

    model_config = ConfigDict(extra="forbid")
    inputs: dict[str, Any] = {}
    actor_type: str = "user"  # 'user' | 'ai_coordinator' | 'system'
    confirmed_by: int | None = None  # quando actor_type=ai_coordinator


# =============================================================================
# Metadata
# =============================================================================


@router.get("/types", summary="Lista tipos registrados")
def list_types() -> dict[str, list[str]]:
    return {
        "object_types": _global_registry.list_object_types(),
        "action_types": _global_registry.list_action_types(),
    }


@router.get("/types/{name}", summary="Schema de um ObjectType")
def describe_type(name: str) -> dict:
    try:
        obj = _global_registry.get_object_type(name)
    except KeyError:
        raise HTTPException(404, f"ObjectType '{name}' nao encontrado")
    return obj.model_dump(mode="json")


# =============================================================================
# Leitura
# =============================================================================


@router.get("/{object_type}/search", summary="Busca textual sobre title_property")
def api_search(
    object_type: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        return runtime.search_objects(
            object_type,
            q,
            user=user_ctx,
            db=db,
            registry=_global_registry,
            limit=limit,
        )
    except KeyError:
        raise HTTPException(404, f"ObjectType '{object_type}' nao encontrado")
    except PermissionDenied as e:
        raise HTTPException(403, str(e))


@router.get("/{object_type}/{object_id}/links/{link_name}", summary="Navega um link")
def api_resolve_link(
    object_type: str,
    object_id: int,
    link_name: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        return runtime.resolve_link(
            object_type,
            object_id,
            link_name,
            user=user_ctx,
            db=db,
            registry=_global_registry,
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except runtime.ObjectNotFound:
        raise HTTPException(404, f"{object_type} #{object_id} nao encontrado")
    except PermissionDenied as e:
        raise HTTPException(403, str(e))


@router.get("/{object_type}/{object_id}", summary="Fetch por ID")
def api_fetch_by_id(
    object_type: str,
    object_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        return runtime.fetch_by_id(
            object_type,
            object_id,
            user=user_ctx,
            db=db,
            registry=_global_registry,
        )
    except KeyError:
        raise HTTPException(404, f"ObjectType '{object_type}' nao encontrado")
    except runtime.ObjectNotFound:
        raise HTTPException(404, f"{object_type} #{object_id} nao encontrado")
    except PermissionDenied as e:
        raise HTTPException(403, str(e))


@router.get("/{object_type}", summary="Listagem paginada")
def api_list(
    object_type: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        return runtime.list_objects(
            object_type,
            user=user_ctx,
            db=db,
            registry=_global_registry,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
    except KeyError:
        raise HTTPException(404, f"ObjectType '{object_type}' nao encontrado")
    except PermissionDenied as e:
        raise HTTPException(403, str(e))


# =============================================================================
# Actions
# =============================================================================


@router.post(
    "/{object_type}/{object_id}/actions/{action_name}",
    summary="Executa uma Action sobre o objeto",
)
def api_execute_action(
    object_type: str,
    object_id: int,
    action_name: str,
    payload: ActionRequest = Body(default_factory=ActionRequest),
    dry_run: bool = Query(False, description="Se true, valida + simula sem persistir"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Executa uma Action. Valida que `object_type` bate com o target da Action
    (defensivo contra payloads errados).

    Em caso de erro:
      - 404: Action ou objeto nao encontrado
      - 403: sem permissao
      - 400: validacao falhou (corpo lista os erros)
    """
    user_ctx = UserContext.from_user_with_grants(user, db)

    # Confere que a Action existe e tem o target esperado
    try:
        action_spec = _global_registry.get_action_type(action_name)
    except KeyError:
        raise HTTPException(404, f"Action '{action_name}' nao encontrada")

    if action_spec.spec.target != object_type:
        raise HTTPException(
            400,
            f"Action '{action_name}' opera sobre '{action_spec.spec.target}', "
            f"nao '{object_type}'",
        )

    try:
        result = runtime.execute_action(
            action_name,
            object_id,
            payload.inputs,
            user=user_ctx,
            db=db,
            registry=_global_registry,
            dry_run=dry_run,
            actor_type=payload.actor_type,
            confirmed_by=payload.confirmed_by,
        )
    except runtime.ObjectNotFound:
        raise HTTPException(404, f"{object_type} #{object_id} nao encontrado")
    except PermissionDenied as e:
        raise HTTPException(403, str(e))
    except runtime.ValidationFailed as e:
        raise HTTPException(400, {"validation_errors": e.errors})

    if not dry_run:
        db.commit()

    return result.to_dict()


# =============================================================================
# AI Tools (Sem5)
# =============================================================================


class ToolDispatchRequest(BaseModel):
    """Payload de chamada de tool pelo Coordinator."""

    model_config = ConfigDict(extra="forbid")
    name: str
    args: dict[str, Any] = {}


@router.get("/tools", summary="Lista tools auto-geradas do Registry")
def api_list_tools() -> dict[str, Any]:
    """
    Retorna lista de tool specs (formato function-calling) + system prompt
    fragment para uso pelo Coordinator de IA.
    """
    from . import ai_tools

    return {
        "tools": ai_tools.build_tools_from_registry(_global_registry),
        "system_prompt_fragment": ai_tools.build_system_prompt_fragment(_global_registry),
    }


@router.post("/tools/dispatch", summary="Executa uma tool gerada do Registry")
def api_dispatch_tool(
    payload: ToolDispatchRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Despacha chamada de tool. Tools de leitura executam direto; `propose_*`
    NAO persiste — retorna preview de dry-run para o frontend exibir card
    de confirmacao.

    Erros:
      - 404: tool desconhecida
      - 403: sem permissao em leitura ou no dry-run de proposta
    """
    from . import ai_tools

    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        return ai_tools.dispatch_tool_call(
            payload.name,
            payload.args,
            user=user_ctx,
            db=db,
            registry=_global_registry,
        )
    except ai_tools.UnknownToolError as e:
        raise HTTPException(404, str(e))
    except runtime.ObjectNotFound as e:
        raise HTTPException(404, str(e))
    except PermissionDenied as e:
        raise HTTPException(403, str(e))


# =============================================================================
# Lineage (Sem6)
# =============================================================================


@router.get(
    "/lineage/{object_type}/{object_id}",
    summary="Timeline de Actions executadas sobre o objeto",
)
def api_lineage(
    object_type: str,
    object_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Retorna o historico de Actions que tocaram este objeto, com timestamps,
    autores (humano/IA), diff before/after e warnings.

    Aplica TenantScoped — se o user nao tem acesso ao objeto, retorna events
    vazio (nao distingue 404 de 403 por seguranca).
    """
    from .lineage import get_lineage

    user_ctx = UserContext.from_user_with_grants(user, db)
    return get_lineage(
        object_type, object_id, db=db, user=user_ctx, limit=limit, registry=_global_registry
    )


# =============================================================================
# Pipelines (Foundry.1)
# =============================================================================


@router.get("/pipelines", summary="Lista pipelines declaradas")
def list_pipelines() -> dict[str, Any]:
    from .pipeline import load_pipelines

    pipes = load_pipelines()
    return {
        "pipelines": [
            {
                "name": p.metadata.name,
                "description": p.metadata.description,
                "schedule": p.spec.schedule,
                "steps": len(p.spec.steps),
                "tags": p.metadata.tags,
            }
            for p in pipes.values()
        ]
    }


@router.post("/pipelines/{name}/run", summary="Executa pipeline + grava lineage")
def run_pipeline_endpoint(
    name: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    from .pipeline import run_pipeline

    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        result = run_pipeline(name, user=user_ctx, db=db, registry=_global_registry)
        return result.to_dict()
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/pipelines/{name}/lineage", summary="Timeline de execucoes")
def pipeline_lineage(
    name: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    from .pipeline import get_lineage_for_pipeline

    return get_lineage_for_pipeline(name, db=db, limit=limit)


# =============================================================================
# Workshop (Foundry.2)
# =============================================================================


@router.get("/workshop/apps", summary="Lista ObjectTypes como apps no-code")
def workshop_list_apps() -> dict[str, Any]:
    from .workshop import list_workshop_apps

    return {"apps": list_workshop_apps(_global_registry)}


@router.get("/workshop/forms/{object_type}", summary="FormSpec auto-gerada do schema")
def workshop_form_spec(object_type: str) -> dict[str, Any]:
    from .workshop import build_form_spec

    try:
        return build_form_spec(object_type, _global_registry)
    except KeyError:
        raise HTTPException(404, f"ObjectType '{object_type}' nao encontrado")


# =============================================================================
# Snapshots / Time-travel (Foundry.3)
# =============================================================================


class SnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    object_type: str
    description: str | None = None
    company_id: int | None = None


@router.post("/snapshots", summary="Cria snapshot de um ObjectType", status_code=201)
def api_create_snapshot(
    payload: SnapshotCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    from .snapshots import SnapshotError, create_snapshot

    user_ctx = UserContext.from_user_with_grants(user, db)
    try:
        return create_snapshot(
            payload.name,
            payload.object_type,
            user=user_ctx,
            db=db,
            registry=_global_registry,
            description=payload.description,
            company_id=payload.company_id,
        )
    except SnapshotError as e:
        raise HTTPException(400, str(e))


@router.get("/snapshots", summary="Lista snapshots")
def api_list_snapshots(
    object_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    from .snapshots import list_snapshots

    return list_snapshots(db, object_type=object_type, limit=limit)


@router.get("/snapshots/{snapshot_id}/objects/{object_id}", summary="Fetch time-travel")
def api_fetch_at(
    snapshot_id: int,
    object_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    from .snapshots import SnapshotError, fetch_at

    try:
        result = fetch_at(snapshot_id, object_id, db=db)
    except SnapshotError as e:
        raise HTTPException(404, str(e))
    if result is None:
        raise HTTPException(404, f"objeto {object_id} nao estava no snapshot {snapshot_id}")
    return result


@router.get("/snapshots/{snapshot_id}/items", summary="Lista objetos do snapshot")
def api_list_at(
    snapshot_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    from .snapshots import SnapshotError, list_at

    try:
        return list_at(snapshot_id, db=db, limit=limit)
    except SnapshotError as e:
        raise HTTPException(404, str(e))


@router.get("/snapshots/diff", summary="Diff entre dois snapshots")
def api_snapshot_diff(
    a: int = Query(..., description="ID snapshot anterior"),
    b: int = Query(..., description="ID snapshot atual"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    from .snapshots import SnapshotError, diff_snapshots

    try:
        return diff_snapshots(a, b, db=db)
    except SnapshotError as e:
        raise HTTPException(400, str(e))
