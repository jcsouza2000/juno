"""
JUNO Ledger - Construcao de eventos encadeados.

Cadeia POR TENANT: cada cliente tem a sua, isolando auditorias.
O primeiro evento de um tenant usa GENESIS como prev_hash.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .canonical import compute_event_hash, hash_payload
from .signer import sign_event

GENESIS = "sha256:" + "0" * 64

# Tipos de evento reconhecidos pela trilha
EVENT_TYPES = {
    "AI_DECISION",      # agente produziu recomendacao/analise
    "HUMAN_APPROVAL",   # humano aprovou/rejeitou (HITL)
    "ACTION_EXECUTED",  # acao efetivada (escrita, chamada externa)
    "DATA_ACCESS",      # leitura de dado sensivel
    "CONFIG_CHANGE",    # mudanca de prompt/modelo/escopo de agente
}


def build_event(
    *,
    tenant_id: str,
    agent_id: str,
    event_type: str,
    prev_hash: Optional[str],
    input_payload: Any = None,
    output_payload: Any = None,
    model_ref: Optional[dict] = None,
    risk_class: str = "BAIXO",
    human_in_loop: Optional[dict] = None,
    payload_uri: Optional[str] = None,
    agent_private_key: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Monta o evento canonico, encadeia, e (opcionalmente) assina."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type invalido: {event_type}")

    event: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "risk_class": risk_class,
        "input_hash": hash_payload(input_payload) if input_payload is not None else None,
        "output_hash": hash_payload(output_payload) if output_payload is not None else None,
        "model_ref": model_ref,
        "human_in_loop": human_in_loop,
        "payload_uri": payload_uri,
        "prev_hash": prev_hash or GENESIS,
    }
    if extra:
        event["extra"] = extra

    event["hash"] = compute_event_hash(event)

    if agent_private_key:
        event["agent_sig"] = sign_event(event, agent_private_key)

    return event


def verify_chain(events: list[dict]) -> tuple[bool, list[str]]:
    """Verifica integridade de uma cadeia (ordenada do mais antigo ao mais novo).

    Retorna (ok, lista_de_erros). Recalcula cada hash e confere o encadeamento.
    """
    errors: list[str] = []
    expected_prev = GENESIS
    for i, ev in enumerate(events):
        recomputed = compute_event_hash(ev)
        if recomputed != ev.get("hash"):
            errors.append(f"[{i}] hash adulterado: {ev.get('event_id')}")
        if ev.get("prev_hash") != expected_prev:
            errors.append(f"[{i}] quebra de encadeamento: {ev.get('event_id')}")
        expected_prev = ev.get("hash", "")
    return (len(errors) == 0, errors)
