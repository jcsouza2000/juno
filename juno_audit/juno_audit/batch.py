"""
JUNO Ledger - Fechamento de lotes (batch closer).

Regras:
- Por tenant: seleciona eventos com id > ultimo last_event_id ancorado.
- Fecha lote se houver >= min_batch_size eventos OU se o evento mais antigo
  pendente tiver mais de max_age_minutes (garante que tenant de baixo volume
  tambem e ancorado).
- Calcula a raiz Merkle (ordem da cadeia), grava em audit_anchors e chama
  o backend de ancoragem. Falha de rede NAO perde o lote: a ancora fica
  PENDING_SUBMIT e o proximo ciclo tenta de novo (retry_pending).
- Idempotente: rodar duas vezes seguidas nao cria lote duplicado.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select

from .anchors import AnchorBackend
from .merkle import merkle_root
from .middleware import AuditEventRow
from .models_anchor import AuditAnchorRow

log = logging.getLogger("juno_audit.batch")


def _tenants_with_events(session) -> list[str]:
    return list(session.execute(
        select(AuditEventRow.tenant_id).distinct()).scalars().all())


def _last_anchored_id(session, tenant_id: str) -> int:
    val = session.execute(
        select(func.max(AuditAnchorRow.last_event_id))
        .where(AuditAnchorRow.tenant_id == tenant_id)
    ).scalar_one_or_none()
    return val or 0


def close_open_batches(
    session_factory,
    backend: AnchorBackend,
    *,
    min_batch_size: int = 50,
    max_age_minutes: int = 60,
    max_batch_size: int = 5000,
) -> list[dict]:
    """Fecha lotes pendentes de todos os tenants. Retorna resumo por lote."""
    results: list[dict] = []
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        for tenant_id in _tenants_with_events(session):
            last_id = _last_anchored_id(session, tenant_id)
            rows = session.execute(
                select(AuditEventRow)
                .where(AuditEventRow.tenant_id == tenant_id,
                       AuditEventRow.id > last_id)
                .order_by(AuditEventRow.id.asc())
                .limit(max_batch_size)
            ).scalars().all()

            if not rows:
                continue

            oldest = rows[0].created_at
            if oldest is not None and oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            old_enough = oldest is not None and \
                (now - oldest) > timedelta(minutes=max_age_minutes)

            if len(rows) < min_batch_size and not old_enough:
                continue  # lote ainda nao maduro

            root = merkle_root([json.loads(r.event_json)["hash"] for r in rows])
            receipt, status = _safe_submit(backend, root)

            anchor = AuditAnchorRow(
                tenant_id=tenant_id,
                first_event_id=rows[0].id,
                last_event_id=rows[-1].id,
                event_count=len(rows),
                merkle_root=root,
                anchor_type=backend.anchor_type,
                anchor_receipt=receipt,
                status=status,
                confirmed_at=now if status == "CONFIRMED" else None,
            )
            session.add(anchor)
            session.commit()
            log.info("lote fechado tenant=%s eventos=%d root=%s status=%s",
                     tenant_id, len(rows), root[:23], status)
            results.append({"tenant_id": tenant_id, "events": len(rows),
                            "merkle_root": root, "status": status})
    return results


def retry_pending(session_factory, backend: AnchorBackend) -> int:
    """Reenvia ancoras PENDING_SUBMIT (falha de rede anterior)."""
    n = 0
    with session_factory() as session:
        rows = session.execute(
            select(AuditAnchorRow)
            .where(AuditAnchorRow.status == "PENDING_SUBMIT",
                   AuditAnchorRow.anchor_type == backend.anchor_type)
        ).scalars().all()
        for a in rows:
            receipt, status = _safe_submit(backend, a.merkle_root)
            if receipt is not None:
                a.anchor_receipt = receipt
                a.status = status
                n += 1
        session.commit()
    return n


def upgrade_submitted(session_factory, backend: AnchorBackend) -> int:
    """Promove SUBMITTED -> CONFIRMED quando o atestado definitivo sair."""
    n = 0
    with session_factory() as session:
        rows = session.execute(
            select(AuditAnchorRow)
            .where(AuditAnchorRow.status == "SUBMITTED",
                   AuditAnchorRow.anchor_type == backend.anchor_type)
        ).scalars().all()
        for a in rows:
            try:
                receipt, status = backend.upgrade(a.merkle_root, a.anchor_receipt)
            except Exception:
                continue
            if receipt is not None and status == "CONFIRMED":
                a.anchor_receipt = receipt
                a.status = "CONFIRMED"
                a.confirmed_at = datetime.now(timezone.utc)
                n += 1
        session.commit()
    return n


def _safe_submit(backend: AnchorBackend, root: str):
    try:
        return backend.submit(root)
    except NotImplementedError:
        raise
    except Exception as exc:  # rede, timeout, API errada, etc: lote fica pendente
        # exc_info=True e ESSENCIAL: ja perdemos tempo com bug de assinatura
        # da RemoteCalendar (timeout no construtor) sendo mascarado como "rede".
        log.warning("submit falhou; ancora fica PENDING_SUBMIT", exc_info=True)
        return None, "PENDING_SUBMIT"
