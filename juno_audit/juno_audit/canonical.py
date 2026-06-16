"""
JUNO Ledger - Canonicalizacao e hash de eventos.

Regra de ouro: o hash de um evento e calculado sobre a sua forma CANONICA
(JSON com chaves ordenadas, sem espacos, UTF-8). Qualquer mudanca de um
byte muda o hash. Os campos 'hash' e assinaturas sao excluidos do calculo.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Campos que NAO entram no calculo do hash do proprio evento
EXCLUDED_FIELDS = {"hash", "agent_sig", "approver_sig"}


def canonical_json(obj: dict[str, Any]) -> bytes:
    """Serializa em JSON canonico: chaves ordenadas, separadores compactos, UTF-8."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_payload(payload: Any) -> str:
    """Hash de um input/output arbitrario (dict, str, bytes)."""
    if isinstance(payload, bytes):
        return sha256_hex(payload)
    if isinstance(payload, str):
        return sha256_hex(payload.encode("utf-8"))
    return sha256_hex(canonical_json(payload))


def compute_event_hash(event: dict[str, Any]) -> str:
    """Hash do evento, excluindo campos de hash/assinatura."""
    core = {k: v for k, v in event.items() if k not in EXCLUDED_FIELDS}
    return sha256_hex(canonical_json(core))
