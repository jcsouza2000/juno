"""
JUNO ERP Connectors API.

CRUD de conexoes, sync, logs, mapeamentos.
Multi-tenancy via User<->Company many-to-many.
Senhas criptografadas com Fernet (`app.core.crypto`).
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

import app.connectors  # noqa: F401 - registra conectores no ERPConnectorFactory
from app.auth import check_company_access, get_current_active_user, require_admin
from app.connectors.base import ERPConnectorFactory
from app.core.crypto import encrypt
from app.core.datetime_utils import utcnow_naive
from app.core.logger import get_logger
from app.database import get_db
from app.models import ERPConnection, ERPSyncLog, User

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/erp", tags=["ERP Connectors"])


# ----- Schemas -----


class ERPConnectionCreate(BaseModel):
    company_id: int
    erp_type: str
    name: str
    host: str
    port: int | None = None
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    database_name: str | None = None
    auth_method: str | None = "basic"
    extra_config: dict[str, Any] | None = None


class ERPConnectionUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    auth_method: str | None = None
    extra_config: dict[str, Any] | None = None
    is_active: bool | None = None


class ERPConnectionOut(BaseModel):
    """Schema de saida -- NUNCA inclui password_encrypted, api_key, etc."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    erp_type: str
    name: str
    host: str | None
    port: int | None
    username: str | None
    auth_method: str | None
    is_active: bool
    status: str | None
    last_sync: datetime | None
    created_at: datetime


class SyncRequest(BaseModel):
    entity_types: list[str] | None = Field(default=None)
    sync_type: str = "incremental"


# ----- Helpers -----


def _ensure_company_access(user: User, company_id: int) -> None:
    if not check_company_access(user, company_id):
        raise HTTPException(status_code=403, detail="Sem acesso a esta empresa")


def _get_connection(db: Session, connection_id: int, user: User) -> ERPConnection:
    conn = db.query(ERPConnection).filter(ERPConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Conexao nao encontrada")
    _ensure_company_access(user, conn.company_id)
    return conn


# ----- Endpoints -----


@router.get("/connectors/available")
def list_available_connectors(_: User = Depends(get_current_active_user)):
    return {
        "connectors": [
            {"type": "totvs_protheus", "name": "TOTVS Protheus", "vendor": "TOTVS"},
            {"type": "totvs_rm", "name": "TOTVS RM", "vendor": "TOTVS"},
            {"type": "sap_ecc", "name": "SAP ECC", "vendor": "SAP"},
            {"type": "sap_s4hana", "name": "SAP S/4HANA", "vendor": "SAP"},
            {"type": "oracle_ebs", "name": "Oracle EBS", "vendor": "Oracle"},
            {"type": "infor_ln", "name": "Infor LN", "vendor": "Infor"},
            {"type": "senior", "name": "Senior Sistemas", "vendor": "Senior"},
            {"type": "sankhya", "name": "Sankhya Omni", "vendor": "Sankhya"},
            {"type": "generic", "name": "Generico REST/JSON", "vendor": "Custom"},
        ]
    }


@router.get("/companies/{company_id}/connections", response_model=list[ERPConnectionOut])
def list_connections(
    company_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_company_access(current_user, company_id)
    return db.query(ERPConnection).filter(ERPConnection.company_id == company_id).all()


@router.post("/connections", response_model=ERPConnectionOut, status_code=201)
def create_connection(
    data: ERPConnectionCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_company_access(current_user, data.company_id)

    available = ERPConnectorFactory.list_available() or []
    if data.erp_type not in available:
        logger.info(f"ERP type '{data.erp_type}' nao registrado na Factory ainda")

    conn = ERPConnection(
        company_id=data.company_id,
        erp_type=data.erp_type,
        name=data.name,
        host=data.host,
        port=data.port,
        username=data.username,
        password_encrypted=encrypt(data.password),
        api_key=encrypt(data.api_key),
        api_secret=encrypt(data.api_secret),
        database_name=data.database_name,
        auth_method=data.auth_method,
        extra_config=json.dumps(data.extra_config) if data.extra_config else None,
        is_active=True,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    logger.info(
        f"ERPConnection criada: id={conn.id} company={data.company_id} type={data.erp_type}"
    )
    return conn


@router.get("/connections/{connection_id}", response_model=ERPConnectionOut)
def get_connection(
    connection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return _get_connection(db, connection_id, current_user)


@router.put("/connections/{connection_id}", response_model=ERPConnectionOut)
def update_connection(
    connection_id: int,
    data: ERPConnectionUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conn = _get_connection(db, connection_id, current_user)
    payload = data.model_dump(exclude_none=True)
    for sensitive in ("password", "api_key", "api_secret"):
        if sensitive in payload:
            val = payload.pop(sensitive)
            attr = "password_encrypted" if sensitive == "password" else sensitive
            setattr(conn, attr, encrypt(val))
    for field, value in payload.items():
        if field == "extra_config":
            setattr(conn, field, json.dumps(value) if value else None)
        else:
            setattr(conn, field, value)
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(
    connection_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conn = _get_connection(db, connection_id, current_user)
    db.delete(conn)
    db.commit()


@router.post("/connections/{connection_id}/test")
def test_connection(
    connection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    conn = _get_connection(db, connection_id, current_user)
    available = ERPConnectorFactory.list_available() or []
    if conn.erp_type not in available:
        return {
            "success": False,
            "error": f"Conector '{conn.erp_type}' nao disponivel. Registrados: {available}",
        }
    connector = ERPConnectorFactory.create(conn.erp_type, conn, db)
    validation = connector.validate_connection()
    if not validation.get("valid", True):
        return {
            "success": False,
            "errors": validation.get("missing_fields", []),
            "detail": validation.get("detail", "Validacao falhou"),
        }
    connected = connector.connect()
    return {
        "success": connected,
        "erp_type": conn.erp_type,
        "errors": connector.errors,
        "warnings": connector.warnings,
    }


def _run_sync_background(connection_id: int, entity_types: list[str], sync_type: str) -> None:
    """Roda em BackgroundTasks com session propria."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        conn = db.query(ERPConnection).filter(ERPConnection.id == connection_id).first()
        if not conn:
            logger.warning(f"Sync abortado: connection {connection_id} nao existe")
            return
        try:
            connector = ERPConnectorFactory.create(conn.erp_type, conn, db)
        except Exception as e:
            logger.error(f"Falha ao criar conector {conn.erp_type}: {e}")
            return
        if not connector.connect():
            logger.error(f"Falha ao conectar ERP id={connection_id}")
            return
        for entity_type in entity_types:
            try:
                result = connector.sync_entity(entity_type, sync_type=sync_type)
                logger.info(f"Sync {entity_type} conn={connection_id}: {result}")
            except Exception as e:
                logger.exception(f"Erro no sync {entity_type}: {e}")
        conn.last_sync = utcnow_naive()
        db.commit()
    finally:
        db.close()


@router.post("/connections/{connection_id}/sync")
def trigger_sync(
    connection_id: int,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conn = _get_connection(db, connection_id, current_user)
    entity_types = request.entity_types or ["products", "customers", "sales_orders"]
    background_tasks.add_task(_run_sync_background, conn.id, entity_types, request.sync_type)
    return {
        "status": "started",
        "connection_id": conn.id,
        "entity_types": entity_types,
        "sync_type": request.sync_type,
    }


@router.get("/connections/{connection_id}/logs")
def get_sync_logs(
    connection_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    conn = _get_connection(db, connection_id, current_user)
    logs = (
        db.query(ERPSyncLog)
        .filter(ERPSyncLog.connection_id == conn.id)
        .order_by(ERPSyncLog.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "logs": [
            {
                "id": log.id,
                "sync_type": log.sync_type,
                "entity_type": log.entity_type,
                "status": log.status,
                "records_found": log.records_found,
                "records_imported": log.records_imported,
                "records_failed": log.records_failed,
                "started_at": log.started_at,
                "completed_at": log.completed_at,
                "error_message": log.error_message,
            }
            for log in logs
        ]
    }
