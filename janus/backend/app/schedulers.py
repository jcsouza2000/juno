"""
JUNO Schedulers — APScheduler para sincronização automática de ERPs
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.connectors.base import ERPConnectorFactory
from app.core.datetime_utils import utcnow_naive
from app.database import SessionLocal
from app.models import ERPConnection

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_all_erp_connections():
    """Sincroniza todos os ERPs ativos."""
    db: Session = SessionLocal()
    try:
        connections = db.query(ERPConnection).filter(ERPConnection.is_active == True).all()
        for conn in connections:
            try:
                connector_class = ERPConnectorFactory.get(conn.erp_type)
                if not connector_class:
                    continue
                connector = connector_class(conn, db)
                if not connector.connect():
                    logger.warning(f"ERP {conn.id} ({conn.erp_type}) falhou ao conectar")
                    continue
                for entity_type in ["products", "customers", "sales_orders"]:
                    try:
                        connector.sync_entity(entity_type, sync_type="incremental")
                    except Exception as e:
                        logger.error(f"Erro sync {entity_type} ERP {conn.id}: {e}")
                conn.last_sync = utcnow_naive()
                db.commit()
                logger.info(f"ERP {conn.id} ({conn.erp_type}) sincronizado com sucesso")
            except Exception as e:
                logger.error(f"Erro geral ERP {conn.id}: {e}")
    finally:
        db.close()


def start_scheduler():
    """Inicia o scheduler com jobs de sincronização."""
    # Sync a cada 60 minutos
    scheduler.add_job(
        sync_all_erp_connections,
        trigger=IntervalTrigger(minutes=60),
        id="erp_sync_all",
        name="ERP Sync All Active Connections",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado — ERP sync a cada 60 minutos")


def stop_scheduler():
    """Para o scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler parado")
