"""
JUNO Audit Router - Endpoints v31 (Agent Registry + Export).

Como integrar no backend (janus/backend/app/main.py):

    from juno_audit.router import build_audit_router

    audit_router = build_audit_router(
        session_factory=SessionLocal,
        juno_private_key=os.environ.get("JUNO_AGENT_SK"),  # assina manifests
    )
    app.include_router(audit_router)

Endpoints:

  POST  /v31/audit/agents              - registra agente (versao nova = id novo)
  GET   /v31/audit/agents              - lista agentes (?only_active=true)
  GET   /v31/audit/agents/{id}/{ver}   - detalhe + manifest
  DELETE /v31/audit/agents/{id}/{ver}  - revoga (eventos historicos seguem validos)
  GET   /v31/audit/export/{tenant_id}  - bundle completo p/ o juno-verify

NOTA DE PROTECAO: em producao, proteja estes endpoints com a auth ja
existente do backend (Depends(get_current_user) ou similar). O export
revela a estrutura de operacao do cliente; o registry permite criar
agentes - ambos devem exigir privilegio adequado.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .export import build_export_bundle
from .registry import (AgentAlreadyExists, AgentNotFound, get_agent,
                       list_agents, register_agent, revoke_agent)


class AgentManifest(BaseModel):
    purpose: str
    model_ref: dict = Field(default_factory=dict)
    system_prompt_hash: Optional[str] = None
    scopes: list[str] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)
    risk_class: str = "BAIXO"
    hitl_required_for: list[str] = Field(default_factory=list)
    owner: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None


class AgentRegisterRequest(BaseModel):
    agent_id: str = Field(..., examples=["juno-kpi-analyst"])
    version: str = Field(..., examples=["1.0.0"])
    public_key: str = Field(..., examples=["ed25519:base64..."])
    manifest: AgentManifest


class AgentResponse(BaseModel):
    agent_id: str
    version: str
    public_key: str
    manifest: dict
    manifest_hash: str
    status: str
    created_at: Optional[str]
    revoked_at: Optional[str]


def _manifest_from_row(row) -> dict:
    import json
    mj = row.manifest_json
    if isinstance(mj, dict):
        return mj
    return json.loads(mj)


def _row_to_response(row) -> AgentResponse:
    return AgentResponse(
        agent_id=row.agent_id, version=row.version,
        public_key=row.public_key, manifest=_manifest_from_row(row),
        manifest_hash=row.manifest_hash, status=row.status,
        created_at=row.created_at.isoformat() if row.created_at else None,
        revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
    )


def build_audit_router(session_factory, juno_private_key: Optional[str] = None,
                        prefix: str = "/v31/audit",
                        dependencies: Optional[list] = None) -> APIRouter:
    """Constroi o router. Passe `dependencies=[Depends(seu_auth)]` em producao."""
    router = APIRouter(prefix=prefix, tags=["audit"],
                       dependencies=dependencies or [])

    def get_session():
        with session_factory() as s:
            yield s

    @router.post("/agents", response_model=AgentResponse, status_code=201)
    def create_agent(req: AgentRegisterRequest, session=Depends(get_session)):
        try:
            row = register_agent(
                session, agent_id=req.agent_id, version=req.version,
                public_key=req.public_key, manifest=req.manifest.model_dump(),
                juno_private_key=juno_private_key,
            )
        except AgentAlreadyExists as exc:
            raise HTTPException(409, str(exc))
        return _row_to_response(row)

    @router.get("/agents", response_model=list[AgentResponse])
    def list_(only_active: bool = Query(False), session=Depends(get_session)):
        return [_row_to_response(r) for r in list_agents(session, only_active=only_active)]

    @router.get("/agents/{agent_id}/{version}", response_model=AgentResponse)
    def get_one(agent_id: str, version: str, session=Depends(get_session)):
        try:
            return _row_to_response(get_agent(session, agent_id, version))
        except AgentNotFound as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/agents/{agent_id}/{version}", response_model=AgentResponse)
    def revoke(agent_id: str, version: str, session=Depends(get_session)):
        try:
            return _row_to_response(revoke_agent(session, agent_id, version))
        except AgentNotFound as exc:
            raise HTTPException(404, str(exc))

    @router.get("/export/{tenant_id}")
    def export_bundle(tenant_id: str,
                      include_pubkeys: bool = Query(True),
                      include_proofs: bool = Query(True),
                      session=Depends(get_session)):
        import json
        bundle = build_export_bundle(
            session, tenant_id,
            include_pubkeys=include_pubkeys, include_proofs=include_proofs)
        # download direto: Content-Disposition para o cliente salvar como arquivo
        return Response(
            content=json.dumps(bundle, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition":
                     f'attachment; filename="juno-audit-{tenant_id}.json"'},
        )

    return router
