"""
JUNO Agent Registry - Identidade de agentes versionada (Camada 2 do blueprint).

Regra de ouro: versao nova = identidade nova. NUNCA sobrescrever um agente
existente. Cada (agent_id, version) e unico e imutavel. Qualquer mudanca de
prompt/modelo/escopo cria uma nova versao - e o ledger registra a transicao
como evento CONFIG_CHANGE.

Status do agente:
  ACTIVE   -> em operacao
  REVOKED  -> chave comprometida ou desautorizada; eventos historicos seguem
              verificaveis (a chave publica permanece), mas novos eventos
              assinados por ela devem ser rejeitados
  EXPIRED  -> valid_until passou; comportamento igual a REVOKED

Estrutura do manifest (exemplo):

    {
      "purpose": "Analise de KPIs e geracao do Score Industrial",
      "model_ref": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
      "system_prompt_hash": "sha256:...",
      "scopes": ["read:erp.financeiro", "read:erp.estoque"],
      "denied": ["write:erp.*", "exec:pagamentos"],
      "risk_class": "MODERADO",
      "hitl_required_for": ["recomendacao_compra > R$ 50.000"],
      "owner": "humano-responsavel@cliente.com",
      "valid_from": "2026-06-01",
      "valid_until": "2026-12-01"
    }
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (BigInteger, Column, DateTime, Integer, Text,
                        UniqueConstraint, func, select)

from .canonical import canonical_json, sha256_hex
from .middleware import Base
from .signer import sign_event, verify_event_signature

PKType = Integer().with_variant(BigInteger(), "postgresql")


class AgentRow(Base):
    __tablename__ = "juno_agents"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_version"),
    )
    id = Column(PKType, primary_key=True, autoincrement=True)
    agent_id = Column(Text, nullable=False, index=True)
    version = Column(Text, nullable=False)
    public_key = Column(Text, nullable=False)        # ed25519:...
    manifest_json = Column(Text, nullable=False)     # JSONB no Postgres real
    manifest_hash = Column(Text, nullable=False)     # sha256 do manifest canonico
    manifest_sig = Column(Text, nullable=True)       # assinatura JUNO sobre o manifest
    status = Column(Text, nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Operacoes
# --------------------------------------------------------------------------
class AgentAlreadyExists(Exception):
    pass


class AgentNotFound(Exception):
    pass


def register_agent(
    session,
    *,
    agent_id: str,
    version: str,
    public_key: str,
    manifest: dict,
    juno_private_key: Optional[str] = None,
) -> AgentRow:
    """Registra (agent_id, version). Lanca AgentAlreadyExists se ja existir."""
    existing = session.execute(
        select(AgentRow).where(AgentRow.agent_id == agent_id,
                                AgentRow.version == version)
    ).scalar_one_or_none()
    if existing is not None:
        raise AgentAlreadyExists(f"{agent_id}:{version} ja registrado")

    manifest_bytes = canonical_json(manifest)
    manifest_hash = sha256_hex(manifest_bytes)
    sig = None
    if juno_private_key:
        # assina o manifest canonico (sem campos espurios)
        sig = sign_event({"manifest_hash": manifest_hash}, juno_private_key)

    row = AgentRow(
        agent_id=agent_id, version=version, public_key=public_key,
        manifest_json=json.dumps(manifest, ensure_ascii=False,
                                  sort_keys=True, separators=(",", ":")),
        manifest_hash=manifest_hash, manifest_sig=sig, status="ACTIVE",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_agent(session, agent_id: str, version: str) -> AgentRow:
    row = session.execute(
        select(AgentRow).where(AgentRow.agent_id == agent_id,
                                AgentRow.version == version)
    ).scalar_one_or_none()
    if row is None:
        raise AgentNotFound(f"{agent_id}:{version}")
    return row


def list_agents(session, *, only_active: bool = False) -> list[AgentRow]:
    stmt = select(AgentRow).order_by(AgentRow.agent_id, AgentRow.version)
    if only_active:
        stmt = stmt.where(AgentRow.status == "ACTIVE")
    return list(session.execute(stmt).scalars().all())


def revoke_agent(session, agent_id: str, version: str) -> AgentRow:
    row = get_agent(session, agent_id, version)
    if row.status == "REVOKED":
        return row
    row.status = "REVOKED"
    row.revoked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(row)
    return row


def pubkeys_snapshot(session) -> dict:
    """Snapshot {<agent_id>:<version>: public_key} para o juno-verify."""
    rows = list_agents(session)
    out: dict[str, str] = {}
    for r in rows:
        out[f"{r.agent_id}:{r.version}"] = r.public_key
        # tambem aceita o agent_id "puro" se o evento omitiu :version
        out.setdefault(r.agent_id, r.public_key)
    return out


def verify_manifest_signature(row: AgentRow, juno_public_key: str) -> bool:
    """Verifica que o manifest foi mesmo assinado pela JUNO (cadeia de delegacao)."""
    if not row.manifest_sig:
        return False
    return verify_event_signature(
        {"manifest_hash": row.manifest_hash}, row.manifest_sig, juno_public_key)
