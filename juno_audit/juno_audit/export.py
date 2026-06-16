"""
JUNO Ledger - Pacote de Export para auditoria independente.

Gera um JSON unico contendo TUDO que o cliente (ou auditor dele) precisa
para verificar a trilha sem depender do JUNO:

  - eventos do tenant (cadeia inteira ou recorte por janela)
  - ancoras do periodo, com merkle_root, anchor_type, status e recibo .ots
    (em base64) quando OPENTIMESTAMPS, ou o JSON assinado quando CLIENT_EXPORT
  - snapshot das chaves publicas de todos os agentes referenciados
  - provas de inclusao de Merkle por evento (cada evento aponta para a sua
    ancora e leva a proof para verificacao independente)
  - metadados do pacote (versao do schema, timestamp, hash do bundle)

O cliente roda:
    python -m juno_audit.verify export.json

E recebe veredito completo sem precisar de rede (exceto se quiser confirmar
o atestado Bitcoin do .ots contra os calendarios publicos).
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from .canonical import canonical_json
from .merkle import merkle_proof
from .middleware import AuditEventRow
from .models_anchor import AuditAnchorRow
from .registry import pubkeys_snapshot

EXPORT_SCHEMA_VERSION = "juno-audit-export/1"


def build_export_bundle(
    session,
    tenant_id: str,
    *,
    include_pubkeys: bool = True,
    include_proofs: bool = True,
) -> dict:
    """Monta o bundle de export para um tenant."""
    # 1. eventos
    event_rows = session.execute(
        select(AuditEventRow).where(AuditEventRow.tenant_id == tenant_id)
        .order_by(AuditEventRow.id.asc())
    ).scalars().all()
    events = [json.loads(r.event_json) for r in event_rows]
    event_db_ids = [r.id for r in event_rows]

    # 2. ancoras do tenant
    anchor_rows = session.execute(
        select(AuditAnchorRow).where(AuditAnchorRow.tenant_id == tenant_id)
        .order_by(AuditAnchorRow.id.asc())
    ).scalars().all()

    anchors_out = []
    # mapa: event_db_id -> (anchor_index, index_no_lote)
    event_to_anchor: dict[int, tuple[int, int]] = {}

    for a_idx, a in enumerate(anchor_rows):
        anchor_event_ids = [eid for eid in event_db_ids
                            if a.first_event_id <= eid <= a.last_event_id]
        anchor_event_hashes = [
            events[event_db_ids.index(eid)]["hash"] for eid in anchor_event_ids]

        receipt_b64 = None
        if a.anchor_receipt is not None:
            receipt_b64 = base64.b64encode(a.anchor_receipt).decode()

        anchors_out.append({
            "anchor_index": a_idx,
            "first_event_id": a.first_event_id,
            "last_event_id": a.last_event_id,
            "event_count": a.event_count,
            "event_hashes": anchor_event_hashes,
            "merkle_root": a.merkle_root,
            "anchor_type": a.anchor_type,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "confirmed_at": a.confirmed_at.isoformat() if a.confirmed_at else None,
            "receipt_b64": receipt_b64,
        })

        for pos, eid in enumerate(anchor_event_ids):
            event_to_anchor[eid] = (a_idx, pos)

    # 3. provas de inclusao por evento (so para eventos que ja estao em ancora)
    proofs = []
    if include_proofs:
        for eid, ev in zip(event_db_ids, events):
            if eid not in event_to_anchor:
                continue  # evento ainda nao foi para um lote fechado
            a_idx, pos = event_to_anchor[eid]
            anchor_hashes = anchors_out[a_idx]["event_hashes"]
            proof = merkle_proof(anchor_hashes, pos)
            proofs.append({
                "event_id": ev["event_id"],
                "event_hash": ev["hash"],
                "anchor_index": a_idx,
                "leaf_index": pos,
                "merkle_root": anchors_out[a_idx]["merkle_root"],
                "proof": [{"side": side, "hash": h} for side, h in proof],
            })

    # 4. snapshot de chaves publicas
    pubkeys = pubkeys_snapshot(session) if include_pubkeys else {}

    # 5. monta bundle e calcula hash do conteudo (sem o campo bundle_hash)
    bundle = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "summary": {
            "event_count": len(events),
            "anchor_count": len(anchors_out),
            "events_in_open_batch": sum(
                1 for eid in event_db_ids if eid not in event_to_anchor),
            "confirmed_anchors": sum(
                1 for a in anchors_out if a["status"] == "CONFIRMED"),
        },
        "pubkeys": pubkeys,
        "events": events,
        "anchors": anchors_out,
        "proofs": proofs,
    }
    bundle["bundle_hash"] = "sha256:" + hashlib.sha256(
        canonical_json(bundle)).hexdigest()
    return bundle
