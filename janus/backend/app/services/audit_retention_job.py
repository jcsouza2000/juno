"""
audit_retention_job.py - job APScheduler semanal que arquiva audit_logs antigos.

Ativado via env vars:
  AUDIT_RETENTION_ENABLED=true
  AUDIT_RETENTION_KEEP_DAYS=365  (default)
  AUDIT_RETENTION_CRON="0 3 * * 0" (default: domingo 03:00)

Registrado em app/main.py no startup. Idempotente: tabela archive criada on-demand.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_scheduler = None


def start_audit_retention_scheduler() -> None:
    """Inicia job APScheduler se AUDIT_RETENTION_ENABLED=true."""
    global _scheduler

    if os.environ.get("AUDIT_RETENTION_ENABLED", "false").lower() != "true":
        logger.info("audit_retention: feature flag desligada")
        return

    if _scheduler is not None:
        logger.warning("audit_retention: scheduler ja' rodando")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("audit_retention: APScheduler nao instalado, pulando")
        return

    keep_days = int(os.environ.get("AUDIT_RETENTION_KEEP_DAYS", "365"))
    cron_expr = os.environ.get("AUDIT_RETENTION_CRON", "0 3 * * 0")

    _scheduler = BackgroundScheduler(daemon=True)
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
    except ValueError as e:
        logger.error("audit_retention: cron invalido '%s' (%s), usando default", cron_expr, e)
        trigger = CronTrigger.from_crontab("0 3 * * 0")

    _scheduler.add_job(
        _run_archive,
        trigger=trigger,
        args=[keep_days],
        id="audit_retention",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(
        "audit_retention: scheduler iniciado (keep=%d days, cron='%s')",
        keep_days,
        cron_expr,
    )


def _run_archive(keep_days: int) -> None:
    """Executa o archive. Erros sao logados mas nao propagam."""
    try:
        # Reusa o mesmo helper do CLI manual
        import importlib.util
        from pathlib import Path

        from app.database import SessionLocal

        script_path = Path(__file__).resolve().parents[3] / "scripts" / "audit_retention.py"
        spec = importlib.util.spec_from_file_location("audit_retention_cli", script_path)
        if spec is None or spec.loader is None:
            logger.error("audit_retention: script CLI nao encontrado em %s", script_path)
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        db = SessionLocal()
        try:
            result = module.archive_old_audits(db, keep_days, dry_run=False)
            logger.info("audit_retention: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("audit_retention: falha ao executar archive: %s", e, exc_info=True)


def stop_audit_retention_scheduler() -> None:
    """Para o scheduler (uso em shutdown)."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
