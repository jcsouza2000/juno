"""
JUNO RBAC Engine
Sistema de controle de acesso baseado em papeis com permissoes granulares
"""

import json
from datetime import datetime
from enum import Enum

from fastapi import Depends, HTTPException, Request
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.core.logger import get_logger
from app.database import get_db
from app.models import Role, User, UserRole

logger = get_logger(__name__)


class Permission(str, Enum):
    """
    Permissoes granulares do sistema.
    Formato: resource.action (ex: product.read, report.delete)
    """

    # Produtos
    PRODUCT_READ = "product.read"
    PRODUCT_WRITE = "product.write"
    PRODUCT_DELETE = "product.delete"
    PRODUCT_EXPORT = "product.export"

    # Clientes
    CUSTOMER_READ = "customer.read"
    CUSTOMER_WRITE = "customer.write"
    CUSTOMER_DELETE = "customer.delete"
    CUSTOMER_EXPORT = "customer.export"

    # Pedidos/Vendas
    ORDER_READ = "order.read"
    ORDER_WRITE = "order.write"
    ORDER_DELETE = "order.delete"
    ORDER_EXPORT = "order.export"

    # Relatorios/BI
    REPORT_READ = "report.read"
    REPORT_WRITE = "report.write"
    REPORT_DELETE = "report.delete"
    REPORT_EXPORT = "report.export"
    DASHBOARD_READ = "dashboard.read"
    DASHBOARD_WRITE = "dashboard.write"

    # IA/ML
    ML_MODEL_READ = "ml_model.read"
    ML_MODEL_WRITE = "ml_model.write"
    ML_PREDICT = "ml.predict"
    CHATBOT_USE = "chatbot.use"

    # ERP
    ERP_READ = "erp.read"
    ERP_WRITE = "erp.write"
    ERP_SYNC = "erp.sync"

    # Usuarios e Seguranca
    USER_READ = "user.read"
    USER_WRITE = "user.write"
    USER_DELETE = "user.delete"
    ROLE_MANAGE = "role.manage"
    AUDIT_READ = "audit.read"
    SETTINGS_READ = "settings.read"
    SETTINGS_WRITE = "settings.write"

    # LGPD/GDPR
    DSR_MANAGE = "dsr.manage"
    CONSENT_MANAGE = "consent.manage"

    # Admin
    ADMIN_FULL = "admin.full"


class RBACEngine:
    """
    Engine de controle de acesso RBAC.
    """

    SYSTEM_ROLES = {
        "admin": {
            "name": "Administrador",
            "description": "Acesso total ao sistema",
            "permissions": [p.value for p in Permission],
        },
        "manager": {
            "name": "Gerente",
            "description": "Acesso a relatorios, produtos e pedidos",
            "permissions": [
                Permission.PRODUCT_READ.value,
                Permission.PRODUCT_WRITE.value,
                Permission.CUSTOMER_READ.value,
                Permission.CUSTOMER_WRITE.value,
                Permission.ORDER_READ.value,
                Permission.ORDER_WRITE.value,
                Permission.REPORT_READ.value,
                Permission.REPORT_WRITE.value,
                Permission.REPORT_EXPORT.value,
                Permission.DASHBOARD_READ.value,
                Permission.DASHBOARD_WRITE.value,
                Permission.ML_MODEL_READ.value,
                Permission.ML_PREDICT.value,
                Permission.CHATBOT_USE.value,
                Permission.ERP_READ.value,
                Permission.ERP_SYNC.value,
                Permission.USER_READ.value,
                Permission.AUDIT_READ.value,
                Permission.SETTINGS_READ.value,
            ],
        },
        "analyst": {
            "name": "Analista",
            "description": "Acesso a relatorios e dashboards",
            "permissions": [
                Permission.PRODUCT_READ.value,
                Permission.CUSTOMER_READ.value,
                Permission.ORDER_READ.value,
                Permission.REPORT_READ.value,
                Permission.REPORT_WRITE.value,
                Permission.REPORT_EXPORT.value,
                Permission.DASHBOARD_READ.value,
                Permission.DASHBOARD_WRITE.value,
                Permission.ML_MODEL_READ.value,
                Permission.ML_PREDICT.value,
                Permission.CHATBOT_USE.value,
                Permission.ERP_READ.value,
            ],
        },
        "operator": {
            "name": "Operador",
            "description": "Acesso operacional basico",
            "permissions": [
                Permission.PRODUCT_READ.value,
                Permission.PRODUCT_WRITE.value,
                Permission.CUSTOMER_READ.value,
                Permission.CUSTOMER_WRITE.value,
                Permission.ORDER_READ.value,
                Permission.ORDER_WRITE.value,
                Permission.ERP_READ.value,
                Permission.ERP_SYNC.value,
            ],
        },
        "viewer": {
            "name": "Visualizador",
            "description": "Apenas visualizacao",
            "permissions": [
                Permission.PRODUCT_READ.value,
                Permission.CUSTOMER_READ.value,
                Permission.ORDER_READ.value,
                Permission.REPORT_READ.value,
                Permission.DASHBOARD_READ.value,
            ],
        },
    }

    def __init__(self, db: Session):
        self.db = db

    def initialize_company_roles(self, company_id: int) -> None:
        """Cria papeis padrao para uma nova empresa."""
        for _role_key, role_data in self.SYSTEM_ROLES.items():
            existing = (
                self.db.query(Role)
                .filter(and_(Role.company_id == company_id, Role.name == role_data["name"]))
                .first()
            )

            if not existing:
                role = Role(
                    company_id=company_id,
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system_role=True,
                    permissions=json.dumps(role_data["permissions"]),
                )
                self.db.add(role)

        self.db.commit()
        logger.info(f"[RBAC] Papeis inicializados para empresa {company_id}")

    def get_user_permissions(self, user_id: int, company_id: int) -> set[str]:
        """Retorna todas as permissoes efetivas de um usuario."""
        permissions = set()

        user_roles = (
            self.db.query(UserRole)
            .join(Role)
            .filter(and_(UserRole.user_id == user_id, Role.company_id == company_id))
            .all()
        )

        for ur in user_roles:
            if ur.expires_at and ur.expires_at < utcnow_naive():
                continue

            role_perms = json.loads(ur.role.permissions or "[]")
            permissions.update(role_perms)

        return permissions

    def has_permission(self, user_id: int, company_id: int, permission: Permission) -> bool:
        """Verifica se usuario tem uma permissao especifica."""
        perms = self.get_user_permissions(user_id, company_id)
        return permission.value in perms or Permission.ADMIN_FULL.value in perms

    def check_permission(self, user_id: int, company_id: int, permission: Permission) -> None:
        """Verifica permissao e lanca excecao se nao tiver."""
        if not self.has_permission(user_id, company_id, permission):
            raise HTTPException(
                status_code=403, detail=f"Acesso negado: permissao '{permission.value}' necessaria"
            )

    def assign_role(
        self, user_id: int, role_id: int, granted_by: int, expires_at: datetime | None = None
    ) -> UserRole:
        """Atribui um papel a um usuario."""
        existing = (
            self.db.query(UserRole)
            .filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
            .first()
        )

        if existing:
            raise HTTPException(status_code=400, detail="Usuario ja possui este papel")

        assignment = UserRole(
            user_id=user_id, role_id=role_id, granted_by=granted_by, expires_at=expires_at
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def revoke_role(self, user_id: int, role_id: int) -> None:
        """Revoga um papel de um usuario."""
        assignment = (
            self.db.query(UserRole)
            .filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
            .first()
        )

        if assignment:
            self.db.delete(assignment)
            self.db.commit()

    def create_custom_role(
        self, company_id: int, name: str, description: str, permissions: list[str], created_by: int
    ) -> Role:
        """Cria papel customizado."""
        valid_perms = [p.value for p in Permission]
        invalid = [p for p in permissions if p not in valid_perms]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Permissoes invalidas: {invalid}")

        role = Role(
            company_id=company_id,
            name=name,
            description=description,
            is_system_role=False,
            permissions=json.dumps(permissions),
            created_by=created_by,
        )
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)

        return role


def require_permission(permission: Permission):
    """Decorator/Dependency para exigir permissao em endpoints."""

    def checker(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        engine = RBACEngine(db)
        company_id = current_user.companies[0].id if current_user.companies else None
        if company_id is None:
            raise HTTPException(status_code=403, detail="Usuario sem empresa associada")
        engine.check_permission(current_user.id, company_id, permission)
        return current_user

    return checker


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Obtem usuario atual do token JWT."""
    from app.auth import decode_token

    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token nao fornecido")

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario invalido ou inativo")
