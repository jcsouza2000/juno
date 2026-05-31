"""
JUNO Audit Logger -- Gravacao automatica de acoes do sistema.

Uso:
  1. Decorator: @audit_log(action="import_erp", table="sales_orders")
  2. Manual:    log_audit_action(db, user, "upload", ...)
  3. Helper:    AuditLogger(db).log("acao", ...)
"""

import asyncio
import functools
import json

from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.core.logger import get_logger
from app.models import AuditLog, User

logger = get_logger(__name__)


def _resolve_company_id(user: User | None, details: dict | None) -> int | None:
    if details and isinstance(details.get("company_id"), int):
        return details["company_id"]
    if user and user.companies:
        return user.companies[0].id
    return None


def log_audit_action(
    db: Session,
    user: User | None,
    action: str,
    source_table: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Grava uma acao no log de auditoria."""
    company_id = _resolve_company_id(user, details)
    if company_id is None:
        raise ValueError("company_id e obrigatorio para gravar auditoria")
    entry = AuditLog(
        company_id=company_id,
        user_id=user.id if user else None,
        action=action,
        resource_type=source_table or "system",
        old_values=None,
        new_values=json.dumps(details, default=str, ensure_ascii=False) if details else None,
        ip_address=ip_address,
        success=True,
        severity="info",
        created_at=utcnow_naive(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def audit_log(action: str, table: str | None = None):
    """
    Decorator para endpoints FastAPI.

    Espera que a funcao receba `db`, `current_user` e opcionalmente
    `request` como kwargs (FastAPI Depends os injeta).
    """

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")
            request = kwargs.get("request")

            result = await func(*args, **kwargs)

            if db:
                try:
                    ip = request.client.host if request else None
                    log_audit_action(
                        db=db,
                        user=current_user,
                        action=action,
                        source_table=table,
                        details={"endpoint": func.__name__},
                        ip_address=ip,
                    )
                except Exception as e:
                    logger.warning(f"Falha ao gravar auditoria (async): {e}", exc_info=True)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")
            request = kwargs.get("request")

            result = func(*args, **kwargs)

            if db:
                try:
                    ip = request.client.host if request else None
                    log_audit_action(
                        db=db,
                        user=current_user,
                        action=action,
                        source_table=table,
                        details={"endpoint": func.__name__},
                        ip_address=ip,
                    )
                except Exception as e:
                    logger.warning(f"Falha ao gravar auditoria (sync): {e}", exc_info=True)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class AuditLogger:
    """Helper para logging manual em services e background tasks."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        table: str | None = None,
        details: dict | None = None,
        user: User | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        return log_audit_action(self.db, user, action, table, details, ip_address)

    def log_import(
        self,
        batch_id: int,
        company_id: int,
        data_type: str,
        rows_imported: int,
        user: User | None = None,
    ) -> AuditLog:
        return self.log(
            action="erp_import",
            table="erp_import_batches",
            details={
                "batch_id": batch_id,
                "company_id": company_id,
                "data_type": data_type,
                "rows": rows_imported,
            },
            user=user,
        )

    def log_login(self, user: User, ip_address: str | None = None) -> AuditLog:
        return self.log(
            action="user_login",
            table="users",
            details={"email": user.email},
            user=user,
            ip_address=ip_address,
        )

    def log_ai_query(
        self,
        company_id: int,
        user_id: int | None,
        question: str,
        response: str,
        session_id: int | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            company_id=company_id,
            user_id=user_id,
            action="ai_query",
            resource_type="ai_chat",
            resource_id=session_id,
            new_values=json.dumps(
                {"question": question, "response": response[:1000]},
                default=str,
                ensure_ascii=False,
            ),
            success=True,
            severity="info",
            created_at=utcnow_naive(),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
