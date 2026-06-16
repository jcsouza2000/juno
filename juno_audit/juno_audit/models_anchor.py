"""
JUNO Ledger - Modelo de ancoras (lotes fechados com raiz Merkle).

Ciclo de vida de uma ancora:
  PENDING_SUBMIT  -> lote fechado, raiz calculada, ainda sem recibo externo
  SUBMITTED       -> recibo OTS inicial obtido (atestado de calendario;
                     confirmacao Bitcoin leva algumas horas)
  CONFIRMED       -> recibo atualizado com atestado Bitcoin definitivo
  EXPORTED        -> ancora exportada para o cofre do cliente (Opcao C)

O job reprocessa PENDING_SUBMIT (rede pode ter falhado) e tenta promover
SUBMITTED -> CONFIRMED via upgrade.
"""
from __future__ import annotations

from sqlalchemy import (BigInteger, Column, DateTime, Integer, LargeBinary,
                        Text, func)

from .middleware import Base

PKType = Integer().with_variant(BigInteger(), "postgresql")


class AuditAnchorRow(Base):
    __tablename__ = "audit_anchors"
    id = Column(PKType, primary_key=True, autoincrement=True)
    tenant_id = Column(Text, nullable=False, index=True)
    first_event_id = Column(PKType, nullable=False)
    last_event_id = Column(PKType, nullable=False)
    event_count = Column(Integer, nullable=False)
    merkle_root = Column(Text, nullable=False)
    anchor_type = Column(Text, nullable=False)      # OPENTIMESTAMPS | ICP_BRASIL_TSA | CLIENT_EXPORT
    anchor_receipt = Column(LargeBinary, nullable=True)  # arquivo .ots / carimbo RFC3161
    status = Column(Text, nullable=False, default="PENDING_SUBMIT")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
