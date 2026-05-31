"""
JUNO Health Check API
Endpoints para monitoramento e readiness probes
"""

import time
from typing import Any

import psutil
import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.datetime_utils import utcnow_naive
from app.database import get_db

router = APIRouter(prefix="/api/v1/health", tags=["Health"])

# Startup time
START_TIME = time.time()


@router.get("/")
def health_check():
    """Health check basico — retorna status e uptime."""
    uptime = time.time() - START_TIME
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "timestamp": utcnow_naive().isoformat(),
        "version": settings.APP_VERSION,
    }


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe — verifica banco e dependencias."""
    checks = {}

    # Database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        raise HTTPException(status_code=503, detail={"ready": False, "checks": checks})

    # Redis (se configurado)
    if settings.REDIS_URL:
        try:
            client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            client.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {str(e)}"
            raise HTTPException(status_code=503, detail={"ready": False, "checks": checks})
    else:
        checks["redis"] = "not_configured"

    return {"ready": True, "checks": checks, "timestamp": utcnow_naive().isoformat()}


@router.get("/live")
def liveness_check():
    """Liveness probe — verifica se a aplicacao esta viva."""
    return {"alive": True}


@router.get("/metrics")
def metrics_check():
    """Métricas Prometheus-style para monitoramento."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    # Memoria
    memory = psutil.virtual_memory()
    # Disco
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_mb": memory.available // (1024 * 1024),
        "disk_percent": disk.percent,
        "disk_free_gb": disk.free // (1024 * 1024 * 1024),
        "timestamp": utcnow_naive().isoformat(),
    }


@router.get("/dependencies")
def dependencies_check(db: Session = Depends(get_db)):
    """Verifica todas as dependencias do sistema."""
    results: dict[str, dict[str, Any]] = {}

    # PostgreSQL
    try:
        db.execute(text("SELECT version()"))
        results["postgresql"] = {"status": "ok"}
    except Exception as e:
        results["postgresql"] = {"status": "error", "message": str(e)}

    # Tabelas criticas
    critical_tables = ["users", "companies", "roles", "audit_logs"]
    missing_tables = []
    for table in critical_tables:
        try:
            db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
        except Exception:
            missing_tables.append(table)

    if missing_tables:
        results["tables"] = {"status": "error", "missing": missing_tables}
    else:
        results["tables"] = {"status": "ok"}

    return results
