"""
JUNO Ledger - Integracao FastAPI + SQLAlchemy.

Uso tipico no seu backend (v30+):

    from juno_audit.middleware import AuditLedger

    ledger = AuditLedger(session_factory=SessionLocal,
                         agent_private_key=os.environ["JUNO_AGENT_SK"])

    @router.post("/v31/score-industrial/{tenant_id}")
    async def score(tenant_id: str):
        resultado = calcular_score(tenant_id)
        ledger.record(
            tenant_id=tenant_id,
            agent_id="juno-kpi-analyst:v1",
            event_type="AI_DECISION",
            input_payload={"tenant": tenant_id},
            output_payload=resultado,
            model_ref={"provider": "anthropic", "model": "claude-sonnet-4-6"},
            risk_class="BAIXO",
        )
        return resultado
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import BigInteger, Column, DateTime, Integer, Text, func, select
from sqlalchemy.orm import declarative_base

from .chain import GENESIS, build_event

Base = declarative_base()

# Integer no SQLite (autoincrement nativo), BIGINT no Postgres
PKType = Integer().with_variant(BigInteger(), "postgresql")


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id = Column(PKType, primary_key=True, autoincrement=True)
    tenant_id = Column(Text, nullable=False, index=True)
    event_json = Column(Text, nullable=False)   # use JSONB no Postgres real
    hash = Column(Text, nullable=False, unique=True)
    prev_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLedger:
    """Fachada de gravacao. Thread-safe por transacao do banco.

    NOTA DE CONCORRENCIA: em producao, serialize a obtencao do prev_hash
    por tenant com SELECT ... FOR UPDATE numa tabela tenant_chain_head,
    ou um advisory lock (pg_advisory_xact_lock) por tenant_id. O esqueleto
    abaixo usa a consulta simples para clareza.
    """

    def __init__(self, session_factory, agent_private_key: Optional[str] = None):
        self._session_factory = session_factory
        self._agent_sk = agent_private_key

    def _last_hash(self, session, tenant_id: str) -> str:
        row = session.execute(
            select(AuditEventRow.hash)
            .where(AuditEventRow.tenant_id == tenant_id)
            .order_by(AuditEventRow.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        return row or GENESIS

    def record(self, *, tenant_id: str, agent_id: str, event_type: str,
               input_payload: Any = None, output_payload: Any = None,
               model_ref: Optional[dict] = None, risk_class: str = "BAIXO",
               human_in_loop: Optional[dict] = None,
               payload_uri: Optional[str] = None,
               extra: Optional[dict] = None) -> dict:
        with self._session_factory() as session:
            prev = self._last_hash(session, tenant_id)
            event = build_event(
                tenant_id=tenant_id, agent_id=agent_id, event_type=event_type,
                prev_hash=prev, input_payload=input_payload,
                output_payload=output_payload, model_ref=model_ref,
                risk_class=risk_class, human_in_loop=human_in_loop,
                payload_uri=payload_uri, agent_private_key=self._agent_sk,
                extra=extra,
            )
            session.add(AuditEventRow(
                tenant_id=tenant_id,
                event_json=json.dumps(event, ensure_ascii=False),
                hash=event["hash"], prev_hash=event["prev_hash"],
            ))
            session.commit()
            return event

    def export_chain(self, tenant_id: str) -> list[dict]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AuditEventRow.event_json)
                .where(AuditEventRow.tenant_id == tenant_id)
                .order_by(AuditEventRow.id.asc())
            ).scalars().all()
            return [json.loads(r) for r in rows]
