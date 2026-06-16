"""Integracao do juno_audit (Ledger) no backend JUNO."""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _audit_enabled() -> bool:
    return settings.DATABASE_URL.startswith("postgresql")


@lru_cache(maxsize=1)
def get_audit_ledger():
    if not _audit_enabled():
        return None
    try:
        from juno_audit import AuditLedger
    except ImportError as exc:
        logger.warning("juno_audit indisponivel: %s", exc)
        return None

    sk = settings.JUNO_AGENT_SK or None
    return AuditLedger(session_factory=SessionLocal, agent_private_key=sk)


def record_score_industrial(
    *,
    tenant_id: str,
    company_id: int,
    output_payload: dict,
) -> dict | None:
    """Grava decisao de score no ledger (ignora falhas para nao quebrar o endpoint)."""
    ledger = get_audit_ledger()
    if ledger is None:
        return None
    try:
        return ledger.record(
            tenant_id=tenant_id,
            agent_id="juno-kpi-analyst:v1",
            event_type="AI_DECISION",
            input_payload={"company_id": company_id, "tenant_id": tenant_id},
            output_payload=output_payload,
            model_ref={"provider": "juno", "model": "score-v2"},
            risk_class="BAIXO",
        )
    except Exception as exc:
        logger.warning("audit ledger record falhou: %s", exc)
        return None
