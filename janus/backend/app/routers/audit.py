"""
JUNO Audit Router — Endpoints para consulta de auditoria
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.audit_center import get_data_quality_center
from app.auth import (
    check_company_access,
    decode_token,
    get_current_active_user,
    get_user_company_ids,
    is_platform_admin,
    require_admin,
)
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["Auditoria"])


def _optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    email = payload.get("sub")
    if not isinstance(email, str):
        return None
    return db.query(User).filter(User.email == email).first()


def _ensure_company_access(company_id: int, user: User | None) -> None:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais invalidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not check_company_access(user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")


# ============================================================
# SCHEMAS
# ============================================================


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str | None
    resource_id: int | None
    details: str | None
    ip_address: str | None
    success: bool
    severity: str
    created_at: str

    class Config:
        from_attributes = True


class AuditStats(BaseModel):
    total_records: int
    today_records: int
    week_records: int
    top_actions: list[dict]
    top_users: list[dict]


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/data-quality/{company_id}")
def get_data_quality_report(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Consolidated trust center used by the Audit UI."""
    _ensure_company_access(company_id, current_user)
    return get_data_quality_center(company_id, db)


@router.get("/logs", response_model=list[AuditLogResponse])
def get_logs(
    company_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    table: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lista logs de auditoria com filtros.
    Platform admin pode cruzar tenants; tenant admin fica restrito às empresas vinculadas.
    """
    query = db.query(AuditLog)

    # Filtro de permissão
    if company_id is not None:
        _ensure_company_access(company_id, current_user)
        query = query.filter(AuditLog.company_id == company_id)
    elif not is_platform_admin(current_user):
        company_ids = get_user_company_ids(current_user)
        if not company_ids:
            raise HTTPException(status_code=403, detail="Usuario sem empresa vinculada")
        query = query.filter(AuditLog.company_id.in_(company_ids))

    if current_user.role == "user":
        query = query.filter(AuditLog.user_id == current_user.id)

    # Filtros opcionais
    if user_id and current_user.role == "admin":
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if table:
        query = query.filter(AuditLog.resource_type == table)

    # Filtro de data
    since = utcnow_naive() - timedelta(days=days)
    query = query.filter(AuditLog.created_at >= since)

    logs = query.order_by(desc(AuditLog.created_at)).limit(limit).all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.new_values,
            "ip_address": log.ip_address,
            "success": log.success,
            "severity": log.severity,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/logs/stats", response_model=AuditStats)
def get_stats(
    company_id: int | None = None,
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Estatísticas de auditoria (apenas admin).
    """
    since = utcnow_naive() - timedelta(days=days)
    if company_id is not None:
        _ensure_company_access(company_id, current_user)
        base_query = db.query(AuditLog).filter(AuditLog.company_id == company_id)
    elif is_platform_admin(current_user):
        base_query = db.query(AuditLog)
    else:
        company_ids = get_user_company_ids(current_user)
        if not company_ids:
            raise HTTPException(status_code=403, detail="Usuario sem empresa vinculada")
        base_query = db.query(AuditLog).filter(AuditLog.company_id.in_(company_ids))

    total = base_query.count()
    today = base_query.filter(AuditLog.created_at >= utcnow_naive() - timedelta(days=1)).count()
    week = base_query.filter(AuditLog.created_at >= since).count()

    # Top ações
    from sqlalchemy import func

    top_actions = (
        base_query.with_entities(AuditLog.action, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= since)
        .group_by(AuditLog.action)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    # Top usuários
    top_users = (
        base_query.with_entities(AuditLog.user_id, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= since)
        .group_by(AuditLog.user_id)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    return {
        "total_records": total,
        "today_records": today,
        "week_records": week,
        "top_actions": [{"action": a.action, "count": a.count} for a in top_actions],
        "top_users": [{"user_id": u.user_id, "count": u.count} for u in top_users],
    }


@router.get("/logs/my")
def get_my_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Logs do usuário logado (conveniência).
    """
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.new_values,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
