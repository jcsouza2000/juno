"""
JUNO Security & Compliance API Routes
Endpoints para RBAC, auditoria, LGPD/GDPR e configuracoes de seguranca
"""

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_primary_company_id, is_platform_admin
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.models import (
    AuditLog,
    ConsentRecord,
    DataSubjectRequest,
    LoginAttempt,
    Role,
    SecuritySettings,
    UserCompany,
)
from app.security.audit_engine import AuditEngine
from app.security.gdpr_engine import GDPREngine
from app.security.rbac_engine import Permission, RBACEngine

router = APIRouter(prefix="/api/v1/security", tags=["Security & Compliance"])


def _company_id(user) -> int:
    return get_primary_company_id(user)


def _is_tenant_admin(db: Session, user, company_id: int) -> bool:
    if is_platform_admin(user):
        return True
    if user.role == "admin":
        return True
    membership = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id, UserCompany.company_id == company_id)
        .first()
    )
    return bool(membership and membership.role_in_tenant in {"owner", "admin"})


def _require_tenant_admin(db: Session, user, company_id: int) -> None:
    if not _is_tenant_admin(db, user, company_id):
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador do tenant")


def _require_permission(db: Session, user, permission: Permission) -> None:
    company_id = _company_id(user)
    if _is_tenant_admin(db, user, company_id):
        return
    engine = RBACEngine(db)
    permissions = engine.get_user_permissions(user.id, company_id)
    if permission.value not in permissions and Permission.ADMIN_FULL.value not in permissions:
        raise HTTPException(status_code=403, detail=f"Permissao requerida: {permission.value}")


# ============================================================
# SCHEMAS
# ============================================================


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    permissions: list[str]


class RoleAssign(BaseModel):
    user_id: int
    role_id: int
    expires_at: datetime | None = None


class AuditQuery(BaseModel):
    action: str | None = None
    resource_type: str | None = None
    resource_id: int | None = None
    user_id: int | None = None
    severity: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 100
    offset: int = 0


class DSRCreate(BaseModel):
    request_type: str
    data_subject_email: str
    data_subject_name: str | None = None
    data_subject_type: str = "customer"
    request_details: str | None = None
    legal_basis: str | None = None


class DSRProcess(BaseModel):
    approve: bool = True
    response_data: dict[str, Any] | None = None
    rejection_reason: str | None = None


class ConsentRecordCreate(BaseModel):
    data_subject_email: str
    consent_type: str
    consent_given: bool
    consent_text: str
    consent_version: str = "1.0"


class SecuritySettingsUpdate(BaseModel):
    mfa_required: bool | None = None
    session_timeout_minutes: int | None = None
    max_login_attempts: int | None = None
    lockout_duration_minutes: int | None = None
    require_password_change_days: int | None = None
    data_retention_days: int | None = None


# ============================================================
# ROTAS — ROLES & PERMISSIONS (RBAC)
# ============================================================


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista papeis da empresa."""
    _require_permission(db, user, Permission.ROLE_MANAGE)
    engine = RBACEngine(db)
    engine.initialize_company_roles(_company_id(user))

    roles = (
        db.query(Role)
        .filter(Role.company_id == _company_id(user))
        .order_by(Role.is_system_role.desc(), Role.name)
        .all()
    )

    return {
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "is_system_role": r.is_system_role,
                "permissions": json.loads(r.permissions) if r.permissions else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in roles
        ]
    }


@router.post("/roles")
def create_role(data: RoleCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Cria papel customizado."""
    _require_tenant_admin(db, user, _company_id(user))
    engine = RBACEngine(db)
    role = engine.create_custom_role(
        company_id=_company_id(user),
        name=data.name,
        description=data.description or "",
        permissions=data.permissions,
        created_by=user.id,
    )

    return {"id": role.id, "name": role.name, "message": "Papel criado com sucesso"}


@router.post("/roles/assign")
def assign_role(data: RoleAssign, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Atribui papel a usuario."""
    _require_tenant_admin(db, user, _company_id(user))
    engine = RBACEngine(db)
    assignment = engine.assign_role(
        user_id=data.user_id, role_id=data.role_id, granted_by=user.id, expires_at=data.expires_at
    )

    audit = AuditEngine(db)
    audit.log(
        company_id=_company_id(user),
        user_id=user.id,
        action="ROLE_ASSIGNED",
        resource_type="user_role",
        resource_id=assignment.id,
        new_values={"user_id": data.user_id, "role_id": data.role_id},
        severity="info",
    )

    return {"message": "Papel atribuido com sucesso"}


@router.delete("/roles/assign/{user_id}/{role_id}")
def revoke_role(
    user_id: int, role_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Revoga papel de usuario."""
    _require_tenant_admin(db, user, _company_id(user))
    engine = RBACEngine(db)
    engine.revoke_role(user_id, role_id)

    audit = AuditEngine(db)
    audit.log(
        company_id=_company_id(user),
        user_id=user.id,
        action="ROLE_REVOKED",
        resource_type="user_role",
        new_values={"user_id": user_id, "role_id": role_id},
        severity="warning",
    )

    return {"message": "Papel revogado com sucesso"}


@router.get("/users/{user_id}/permissions")
def get_user_permissions(
    user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Lista permissoes efetivas de um usuario."""
    _require_permission(db, user, Permission.USER_READ)
    engine = RBACEngine(db)
    perms = engine.get_user_permissions(user_id, _company_id(user))

    return {
        "user_id": user_id,
        "permissions": list(perms),
        "is_admin": Permission.ADMIN_FULL.value in perms,
    }


@router.get("/permissions/available")
def list_available_permissions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista todas as permissoes disponiveis no sistema."""
    return {
        "permissions": [
            {
                "code": p.value,
                "resource": p.value.split(".")[0],
                "action": p.value.split(".")[1] if "." in p.value else "full",
            }
            for p in Permission
        ]
    }


# ============================================================
# ROTAS — AUDITORIA
# ============================================================


@router.post("/audit/query")
def query_audit(query: AuditQuery, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Consulta logs de auditoria com filtros."""
    _require_permission(db, user, Permission.AUDIT_READ)
    engine = AuditEngine(db)
    result = engine.get_audit_trail(
        company_id=_company_id(user),
        resource_type=query.resource_type,
        resource_id=query.resource_id,
        user_id=query.user_id,
        action=query.action,
        severity=query.severity,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset,
    )
    return result


@router.get("/audit/resource/{resource_type}/{resource_id}")
def get_resource_lineage(
    resource_type: str,
    resource_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Retorna lineage completa de um recurso."""
    _require_permission(db, user, Permission.AUDIT_READ)
    engine = AuditEngine(db)
    lineage = engine.get_data_lineage(resource_type, resource_id, _company_id(user))
    return {"resource_type": resource_type, "resource_id": resource_id, "lineage": lineage}


@router.get("/audit/statistics")
def audit_statistics(days: int = 30, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Estatisticas de auditoria."""
    _require_permission(db, user, Permission.AUDIT_READ)
    engine = AuditEngine(db)
    stats = engine.get_statistics(_company_id(user), days)
    return stats


# ============================================================
# ROTAS — LGPD/GDPR (Data Subject Requests)
# ============================================================


@router.post("/dsr")
def create_dsr(data: DSRCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Cria requisicao do titular de dados."""
    engine = GDPREngine(db)
    dsr = engine.create_data_subject_request(
        company_id=_company_id(user),
        request_type=data.request_type,
        data_subject_email=data.data_subject_email,
        data_subject_name=data.data_subject_name,
        data_subject_type=data.data_subject_type,
        request_details=data.request_details,
        legal_basis=data.legal_basis,
    )

    return {
        "id": dsr.id,
        "request_type": dsr.request_type,
        "status": dsr.status,
        "deadline_at": dsr.deadline_at.isoformat() if dsr.deadline_at else None,
        "message": "Requisicao registrada. Prazo: 15 dias.",
    }


@router.get("/dsr")
def list_dsr(
    status: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Lista requisicoes do titular."""
    _require_permission(db, user, Permission.DSR_MANAGE)
    query = db.query(DataSubjectRequest).filter(DataSubjectRequest.company_id == _company_id(user))
    if status:
        query = query.filter(DataSubjectRequest.status == status)

    dsrs = query.order_by(DataSubjectRequest.deadline_at).all()

    return {
        "dsrs": [
            {
                "id": d.id,
                "request_type": d.request_type,
                "status": d.status,
                "data_subject_email": d.data_subject_email,
                "requested_at": d.requested_at.isoformat() if d.requested_at else None,
                "deadline_at": d.deadline_at.isoformat() if d.deadline_at else None,
                "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                "days_remaining": (
                    max(0, (d.deadline_at - utcnow_naive()).days) if d.deadline_at else None
                ),
            }
            for d in dsrs
        ]
    }


@router.post("/dsr/{dsr_id}/process")
def process_dsr(
    dsr_id: int, data: DSRProcess, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Processa requisicao do titular."""
    company_id = _company_id(user)
    _require_permission(db, user, Permission.DSR_MANAGE)
    dsr_exists = (
        db.query(DataSubjectRequest)
        .filter(DataSubjectRequest.id == dsr_id, DataSubjectRequest.company_id == company_id)
        .first()
    )
    if not dsr_exists:
        raise HTTPException(status_code=404, detail="Requisicao do titular nao encontrada")
    engine = GDPREngine(db)
    dsr = engine.process_data_subject_request(
        dsr_id=dsr_id,
        processed_by=user.id,
        approve=data.approve,
        response_data=data.response_data,
        rejection_reason=data.rejection_reason,
    )

    return {
        "id": dsr.id,
        "status": dsr.status,
        "completed_at": dsr.completed_at.isoformat() if dsr.completed_at else None,
    }


# ============================================================
# ROTAS — CONSENTIMENTOS
# ============================================================


@router.post("/consent")
def record_consent(
    data: ConsentRecordCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Registra consentimento."""
    _require_permission(db, user, Permission.CONSENT_MANAGE)
    engine = GDPREngine(db)
    consent = engine.record_consent(
        company_id=_company_id(user),
        data_subject_email=data.data_subject_email,
        consent_type=data.consent_type,
        consent_given=data.consent_given,
        consent_text=data.consent_text,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        consent_version=data.consent_version,
    )

    return {
        "id": consent.id,
        "consent_given": consent.consent_given,
        "message": "Consentimento registrado",
    }


@router.get("/consent/{email}")
def check_consent(
    email: str, consent_type: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Verifica status de consentimento."""
    _require_permission(db, user, Permission.CONSENT_MANAGE)
    engine = GDPREngine(db)
    has_consent = engine.check_consent(_company_id(user), email, consent_type)

    return {"email": email, "consent_type": consent_type, "has_valid_consent": has_consent}


@router.post("/consent/{consent_id}/withdraw")
def withdraw_consent(
    consent_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Revoga consentimento."""
    company_id = _company_id(user)
    _require_permission(db, user, Permission.CONSENT_MANAGE)
    consent_exists = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.id == consent_id, ConsentRecord.company_id == company_id)
        .first()
    )
    if not consent_exists:
        raise HTTPException(status_code=404, detail="Consentimento nao encontrado")
    engine = GDPREngine(db)
    consent = engine.withdraw_consent(consent_id, user.id)

    return {
        "id": consent.id,
        "withdrawn": True,
        "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
    }


# ============================================================
# ROTAS — COMPLIANCE & CONFIGURACOES
# ============================================================


@router.get("/compliance/report")
def compliance_report(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Relatorio de conformidade LGPD/GDPR."""
    _require_permission(db, user, Permission.SETTINGS_READ)
    engine = GDPREngine(db)
    report = engine.get_compliance_report(_company_id(user))
    return report


@router.get("/settings")
def get_security_settings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Obtem configuracoes de seguranca da empresa."""
    _require_permission(db, user, Permission.SETTINGS_READ)
    settings = (
        db.query(SecuritySettings).filter(SecuritySettings.company_id == _company_id(user)).first()
    )

    if not settings:
        settings = SecuritySettings(company_id=_company_id(user))
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "mfa_required": settings.mfa_required,
        "session_timeout_minutes": settings.session_timeout_minutes,
        "max_login_attempts": settings.max_login_attempts,
        "lockout_duration_minutes": settings.lockout_duration_minutes,
        "require_password_change_days": settings.require_password_change_days,
        "data_retention_days": settings.data_retention_days,
        "encryption_at_rest": settings.encryption_at_rest,
        "encryption_in_transit": settings.encryption_in_transit,
        "gdpr_enabled": settings.gdpr_enabled,
        "lgpd_enabled": settings.lgpd_enabled,
    }


@router.get("/trust/posture")
def trust_posture(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Resumo executivo da postura de confianca do tenant atual."""
    company_id = _company_id(user)
    _require_permission(db, user, Permission.SETTINGS_READ)

    settings = db.query(SecuritySettings).filter(SecuritySettings.company_id == company_id).first()
    if not settings:
        settings = SecuritySettings(company_id=company_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    since_24h = utcnow_naive() - timedelta(hours=24)
    audit_events_24h = (
        db.query(AuditLog)
        .filter(AuditLog.company_id == company_id, AuditLog.created_at >= since_24h)
        .count()
    )
    open_dsrs = (
        db.query(DataSubjectRequest)
        .filter(DataSubjectRequest.company_id == company_id, DataSubjectRequest.status != "completed")
        .count()
    )

    controls = [
        {
            "id": "tenant_isolation",
            "label": "Isolamento por tenant",
            "status": "active",
            "evidence": "Rotas sensiveis exigem usuario autenticado e company_id validado.",
        },
        {
            "id": "rbac",
            "label": "RBAC e administracao por tenant",
            "status": "active",
            "evidence": "Acoes administrativas exigem admin do tenant ou platform_admin.",
        },
        {
            "id": "lgpd",
            "label": "LGPD/GDPR",
            "status": "active" if settings.lgpd_enabled else "planned",
            "evidence": "DSR, consentimentos e retencao registrados por company_id.",
        },
        {
            "id": "encryption",
            "label": "Criptografia",
            "status": "active" if settings.encryption_at_rest else "planned",
            "evidence": "Segredos ERP persistidos com Fernet e usados descriptografados apenas em runtime.",
        },
        {
            "id": "mfa",
            "label": "MFA",
            "status": "planned" if not settings.mfa_required else "active",
            "evidence": "Configuracao pronta; fluxo de autenticacao multifator ainda deve ser integrado.",
        },
        {
            "id": "auditability",
            "label": "Auditoria",
            "status": "active",
            "evidence": f"{audit_events_24h} eventos de auditoria nas ultimas 24h.",
        },
    ]

    return {
        "company_id": company_id,
        "generated_at": utcnow_naive().isoformat(),
        "trust_level": "controlled",
        "summary": {
            "audit_events_24h": audit_events_24h,
            "open_data_subject_requests": open_dsrs,
            "mfa_required": settings.mfa_required,
            "session_timeout_minutes": settings.session_timeout_minutes,
            "data_retention_days": settings.data_retention_days,
        },
        "controls": controls,
        "next_certification_targets": ["LGPD-ready", "ISO 27001 readiness", "SOC 2 readiness"],
    }


@router.put("/settings")
def update_security_settings(
    data: SecuritySettingsUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Atualiza configuracoes de seguranca."""
    _require_tenant_admin(db, user, _company_id(user))
    settings = (
        db.query(SecuritySettings).filter(SecuritySettings.company_id == _company_id(user)).first()
    )

    if not settings:
        settings = SecuritySettings(company_id=_company_id(user))
        db.add(settings)

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_at = utcnow_naive()
    db.commit()

    audit = AuditEngine(db)
    audit.log(
        company_id=_company_id(user),
        user_id=user.id,
        action="SETTINGS_UPDATED",
        resource_type="security_settings",
        new_values=update_data,
        severity="warning",
    )

    return {"message": "Configuracoes atualizadas"}


# ============================================================
# ROTAS — LOGIN ATTEMPTS & BRUTE FORCE
# ============================================================


@router.get("/login-attempts")
def get_login_attempts(
    limit: int = 100, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Lista tentativas de login recentes."""
    _require_tenant_admin(db, user, _company_id(user))
    since = utcnow_naive() - timedelta(hours=24)

    attempts = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.created_at >= since)
        .order_by(LoginAttempt.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "attempts": [
            {
                "id": a.id,
                "username": a.username,
                "ip_address": a.ip_address,
                "success": a.success,
                "failure_reason": a.failure_reason,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attempts
        ]
    }


@router.get("/login-attempts/stats")
def login_attempts_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Estatisticas de tentativas de login."""
    _require_tenant_admin(db, user, _company_id(user))
    since = utcnow_naive() - timedelta(hours=24)

    total = db.query(LoginAttempt).filter(LoginAttempt.created_at >= since).count()
    failed = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.created_at >= since, LoginAttempt.success == False)
        .count()
    )
    blocked_ips = (
        db.query(LoginAttempt.ip_address)
        .filter(LoginAttempt.created_at >= since, LoginAttempt.success == False)
        .distinct()
        .count()
    )

    return {
        "period_hours": 24,
        "total_attempts": total,
        "failed_attempts": failed,
        "success_rate": ((total - failed) / total * 100) if total > 0 else 0,
        "unique_blocked_ips": blocked_ips,
    }
