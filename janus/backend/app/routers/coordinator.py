"""
Router /ai/coordinator - SSE stream do AI Coordinator.

POST /ai/coordinator
  body: {question: str, history: list, user_id?: int}
  resposta: text/event-stream com eventos:
    data: {"type": "tool_call", "tool": str, "label": str}
    data: {"type": "proposed_action", "action": str, ...}
    data: {"type": "text", "content": str}
    data: {"type": "error", "message": str}
    data: [DONE]
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/ai", tags=["ai"])

OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
REQUIRED_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


@router.get("/ollama/health", summary="Status do Ollama local")
def ollama_health():
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        models = [item.get("name", "") for item in payload.get("models", [])]
        model_ready = REQUIRED_MODEL in models
        return {
            "online": True,
            "model": REQUIRED_MODEL,
            "model_ready": model_ready,
            "models_available": models,
            "base_url": OLLAMA_BASE_URL,
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "online": False,
            "model": REQUIRED_MODEL,
            "model_ready": False,
            "models_available": [],
            "base_url": OLLAMA_BASE_URL,
            "error": str(exc),
            "hint": "Inicie o Ollama Desktop ou execute 'ollama serve'. Baixe em https://ollama.com/download",
        }


class CoordinatorRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question: str
    history: list[dict[str, Any]] = []
    company_id: int | None = None
    # Idioma da resposta da IA: 'pt' (padrao) | 'en' | 'es'.
    lang: str | None = None


@router.post("/coordinator", summary="SSE stream do Coordinator")
def coordinator_endpoint(
    payload: CoordinatorRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.ai_coordinator import coordinate
    from app.auth import get_user_company_ids

    # Resolve o tenant AGORA, com a sessao do DB viva. No streaming SSE o objeto
    # `user` desanexa e o lazy-load de user.companies falha dentro do gerador;
    # por isso validamos aqui o company_id contra as empresas reais do usuario.
    try:
        allowed = get_user_company_ids(user)
    except Exception:  # noqa: BLE001
        allowed = []
    requested = payload.company_id
    effective_company_id: int | None
    if requested is not None and requested in allowed:
        effective_company_id = requested
    elif allowed:
        effective_company_id = allowed[0]
    else:
        effective_company_id = requested

    def event_stream():
        try:
            for chunk in coordinate(
                payload.question,
                db,
                history=payload.history,
                user=user,
                company_id=effective_company_id,
                lang=payload.lang,
            ):
                yield f"data: {chunk}\n\n"
        except Exception as e:  # noqa: BLE001
            import json

            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
