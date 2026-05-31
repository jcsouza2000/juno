"""
JUNO Audit Engine
Sistema completo de auditoria, logging e data lineage
"""

import json
import logging
from datetime import datetime
from functools import wraps
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.models import AuditLog

logger = logging.getLogger(__name__)


class AuditEngine:
    """
    Engine de auditoria para rastreamento completo de acoes.
    """

    ACTIONS = {
        "CREATE": "CREATE",
        "READ": "READ",
        "UPDATE": "UPDATE",
        "DELETE": "DELETE",
        "LOGIN": "LOGIN",
        "LOGOUT": "LOGOUT",
        "EXPORT": "EXPORT",
        "IMPORT": "IMPORT",
        "SYNC": "SYNC",
        "APPROVE": "APPROVE",
        "REJECT": "REJECT",
        "DOWNLOAD": "DOWNLOAD",
        "SHARE": "SHARE",
    }

    SEVERITY = {
        "debug": "debug",
        "info": "info",
        "warning": "warning",
        "error": "error",
        "critical": "critical",
    }

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        company_id: int,
        user_id: int | None,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        severity: str = "info",
        compliance_tags: list[str] | None = None,
    ) -> AuditLog:
        """Registra evento de auditoria."""

        old_values = self._sanitize_sensitive_data(old_values)
        new_values = self._sanitize_sensitive_data(new_values)

        log_entry = AuditLog(
            company_id=company_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=json.dumps(old_values, default=str) if old_values else None,
            new_values=json.dumps(new_values, default=str) if new_values else None,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            success=success,
            error_message=error_message,
            severity=severity,
            compliance_tags=json.dumps(compliance_tags) if compliance_tags else None,
        )

        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)

        log_msg = f"[AUDIT] {action} {resource_type}"
        if resource_id:
            log_msg += f" #{resource_id}"
        if user_id:
            log_msg += f" by user #{user_id}"

        if severity == "critical":
            logger.critical(log_msg)
        elif severity == "error":
            logger.error(log_msg)
        elif severity == "warning":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return log_entry

    def log_from_request(
        self,
        request: Request,
        company_id: int,
        user_id: int | None,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        success: bool = True,
        error_message: str | None = None,
        severity: str = "info",
    ) -> AuditLog:
        """Registra auditoria extraindo dados do request HTTP."""
        return self.log(
            company_id=company_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            session_id=request.headers.get("x-session-id"),
            request_id=request.headers.get("x-request-id"),
            success=success,
            error_message=error_message,
            severity=severity,
        )

    def get_audit_trail(
        self,
        company_id: int,
        resource_type: str | None = None,
        resource_id: int | None = None,
        user_id: int | None = None,
        action: str | None = None,
        severity: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Busca trilha de auditoria com filtros."""

        query = self.db.query(AuditLog).filter(AuditLog.company_id == company_id)

        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.filter(AuditLog.resource_id == resource_id)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if severity:
            query = query.filter(AuditLog.severity == severity)
        if date_from:
            query = query.filter(AuditLog.created_at >= date_from)
        if date_to:
            query = query.filter(AuditLog.created_at <= date_to)

        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "old_values": json.loads(log.old_values) if log.old_values else None,
                    "new_values": json.loads(log.new_values) if log.new_values else None,
                    "ip_address": log.ip_address,
                    "success": log.success,
                    "error_message": log.error_message,
                    "severity": log.severity,
                    "compliance_tags": (
                        json.loads(log.compliance_tags) if log.compliance_tags else []
                    ),
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }

    def get_data_lineage(self, resource_type: str, resource_id: int, company_id: int) -> list[dict]:
        """Retorna lineage completa de um recurso."""
        logs = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.company_id == company_id,
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at)
            .all()
        )

        lineage = []
        for log in logs:
            lineage.append(
                {
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                    "action": log.action,
                    "user_id": log.user_id,
                    "changes": self._diff_values(
                        json.loads(log.old_values) if log.old_values else {},
                        json.loads(log.new_values) if log.new_values else {},
                    ),
                    "ip_address": log.ip_address,
                }
            )

        return lineage

    def get_statistics(self, company_id: int, days: int = 30) -> dict[str, Any]:
        """Estatisticas de auditoria."""
        from datetime import timedelta

        from sqlalchemy import func

        date_from = utcnow_naive() - timedelta(days=days)

        action_counts = (
            self.db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
            .filter(AuditLog.company_id == company_id, AuditLog.created_at >= date_from)
            .group_by(AuditLog.action)
            .all()
        )

        severity_counts = (
            self.db.query(AuditLog.severity, func.count(AuditLog.id).label("count"))
            .filter(AuditLog.company_id == company_id, AuditLog.created_at >= date_from)
            .group_by(AuditLog.severity)
            .all()
        )

        failed_logins = (
            self.db.query(func.count(AuditLog.id))
            .filter(
                AuditLog.company_id == company_id,
                AuditLog.action == "LOGIN",
                AuditLog.success == False,
                AuditLog.created_at >= date_from,
            )
            .scalar()
        )

        suspicious = (
            self.db.query(AuditLog.user_id, func.count(AuditLog.ip_address.distinct()))
            .filter(AuditLog.company_id == company_id, AuditLog.created_at >= date_from)
            .group_by(AuditLog.user_id)
            .having(func.count(AuditLog.ip_address.distinct()) > 3)
            .all()
        )

        return {
            "period_days": days,
            "total_events": sum(a.count for a in action_counts),
            "by_action": {a.action: a.count for a in action_counts},
            "by_severity": {s.severity: s.count for s in severity_counts},
            "failed_logins": failed_logins,
            "suspicious_users": [{"user_id": s[0], "ip_count": s[1]} for s in suspicious],
        }

    def _sanitize_sensitive_data(self, data: dict | None) -> dict | None:
        """Remove dados sensiveis antes de armazenar."""
        if not data:
            return data

        sensitive_fields = [
            "password",
            "password_encrypted",
            "api_secret",
            "token",
            "credit_card",
            "ssn",
            "cpf",
        ]
        sanitized = {}

        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_fields):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value

        return sanitized

    def _get_client_ip(self, request: Request) -> str:
        """Extrai IP real do cliente considerando proxies."""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            return x_real_ip

        if hasattr(request, "client") and request.client:
            return request.client.host

        return "unknown"

    def _diff_values(self, old: dict, new: dict) -> list[dict]:
        """Calcula diferenca entre dois dicts."""
        changes = []
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)

            if old_val != new_val:
                changes.append({"field": key, "old": old_val, "new": new_val})

        return changes


def audit_log(
    action: str,
    resource_type: str,
    get_resource_id=None,
    get_old_values=None,
    get_new_values=None,
    severity: str = "info",
):
    """
    Decorator para automacao de auditoria em endpoints.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None
            )
            db = kwargs.get("db") or next((a for a in args if isinstance(a, Session)), None)
            current_user = kwargs.get("current_user")

            try:
                result = await func(*args, **kwargs)
                success = True
                error_msg = None
            except Exception as e:
                success = False
                error_msg = str(e)
                raise

            finally:
                if db and current_user:
                    engine = AuditEngine(db)

                    resource_id = get_resource_id(*args, **kwargs) if get_resource_id else None
                    old_vals = get_old_values(*args, **kwargs) if get_old_values else None
                    new_vals = get_new_values(*args, **kwargs) if get_new_values else None

                    if request:
                        engine.log_from_request(
                            request=request,
                            company_id=current_user.company_id,
                            user_id=current_user.id,
                            action=action,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            old_values=old_vals,
                            new_values=new_vals,
                            success=success,
                            error_message=error_msg,
                            severity=severity if success else "error",
                        )

            return result

        return wrapper

    return decorator
