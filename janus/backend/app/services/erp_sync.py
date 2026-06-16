"""
Sincronização ERP ao vivo — orquestração de pull incremental por tenant.

Skeleton da ingestão contínua: para cada ERPConnection ativa, cria o conector
via ERPConnectorFactory e dispara sync_entity por entidade, agregando o
resultado. Reaproveita o contrato existente (connect/sync_entity) e o
isolamento multi-tenant por company_id.

Desligado por padrão; habilite com ERP_LIVE_SYNC_ENABLED=true. A factory e a
sessão são injetáveis para teste, sem alterar a arquitetura dos conectores.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.connectors.base import ERPConnectorFactory
from app.models import ERPConnection

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES = ("products", "customers", "sales_orders")


def live_sync_enabled() -> bool:
    """Feature flag via env (config do JUNO e' 100% por env vars)."""
    return os.getenv("ERP_LIVE_SYNC_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


@dataclass
class SyncOutcome:
    """Resultado agregado de uma sincronizacao de conexao."""

    connection_id: int
    company_id: int
    erp_type: str
    records_imported: int = 0
    status: str = "pending"
    errors: list[str] = field(default_factory=list)


def run_connection_sync(
    db: Session,
    connection: ERPConnection,
    *,
    entity_types: tuple[str, ...] = DEFAULT_ENTITIES,
    sync_type: str = "incremental",
    factory: type[ERPConnectorFactory] = ERPConnectorFactory,
) -> SyncOutcome:
    """Executa pull para uma conexao e agrega o resultado por entidade.

    Falha de uma entidade nao derruba as demais: erros sao agregados e a
    conexao termina com status 'failed' se houver qualquer erro.
    """
    outcome = SyncOutcome(
        connection_id=connection.id,
        company_id=connection.company_id,
        erp_type=connection.erp_type,
    )

    available = factory.list_available() or []
    if connection.erp_type not in available:
        outcome.status = "skipped"
        outcome.errors.append(f"Conector '{connection.erp_type}' nao registrado")
        return outcome

    connector = factory.create(connection.erp_type, connection, db)
    if not connector.connect():
        outcome.status = "failed"
        outcome.errors.extend(connector.errors or ["Falha ao conectar"])
        return outcome

    for entity_type in entity_types:
        try:
            result: dict[str, Any] = connector.sync_entity(entity_type, sync_type=sync_type)
            outcome.records_imported += int(result.get("records_imported", 0) or 0)
            if not result.get("success", False):
                outcome.errors.append(f"{entity_type}: {result.get('error', 'falha')}")
        except Exception as exc:  # noqa: BLE001 - isola falha de uma entidade
            logger.exception("Falha no sync %s/%s", connection.erp_type, entity_type)
            outcome.errors.append(f"{entity_type}: {exc}")

    outcome.status = "failed" if outcome.errors else "completed"
    logger.info(
        "Sync ERP conn=%s company=%s registros=%s status=%s",
        outcome.connection_id,
        outcome.company_id,
        outcome.records_imported,
        outcome.status,
    )
    return outcome


def run_due_syncs(
    db: Session,
    *,
    factory: type[ERPConnectorFactory] = ERPConnectorFactory,
) -> list[SyncOutcome]:
    """Job periodico: sincroniza todas as conexoes ativas. No-op se flag off."""
    if not live_sync_enabled():
        logger.debug("ERP live sync desabilitado (ERP_LIVE_SYNC_ENABLED).")
        return []

    connections = (
        db.query(ERPConnection).filter(ERPConnection.is_active == True).all()
    )  # noqa: E712
    return [run_connection_sync(db, conn, factory=factory) for conn in connections]
