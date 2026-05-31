"""
JUNO Multi-Tenancy Service
Gerencia isolamento de dados, permissões e configurações por empresa/tenant
"""

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_user_company_ids, is_platform_admin
from app.models import Company, User, UserCompany


class TenantContext:
    """
    Contexto de tenant para requisições.
    Carrega configurações e permissões do tenant atual.
    """

    def __init__(self, company_id: int, user_id: int, db: Session):
        self.company_id = company_id
        self.user_id = user_id
        self.db = db
        self._company: Company | None = None
        self._permissions: list[str] | None = None

    @property
    def company(self) -> Company | None:
        if self._company is None:
            self._company = self.db.query(Company).filter(Company.id == self.company_id).first()
        return self._company

    @property
    def permissions(self) -> list[str]:
        if self._permissions is None:
            # Buscar permissões do usuário nesta empresa
            user_company = (
                self.db.query(UserCompany)
                .filter(
                    UserCompany.user_id == self.user_id, UserCompany.company_id == self.company_id
                )
                .first()
            )

            if user_company:
                if user_company.role_in_tenant in {"owner", "admin"}:
                    self._permissions = ["read", "write", "delete", "admin"]
                else:
                    self._permissions = ["read", "write"]
            else:
                self._permissions = []

        return self._permissions

    def has_permission(self, permission: str) -> bool:
        """Verifica se usuário tem permissão específica."""
        return permission in self.permissions

    def get_company_config(self) -> dict:
        """Retorna configurações específicas do tenant."""
        if not self.company:
            return {}

        return {
            "company_id": self.company.id,
            "name": self.company.name,
            "sector": self.company.sector,
            "max_users": 10,  # TODO: Virar do plano
            "max_storage_mb": 1000,
            "features_enabled": ["dashboards", "ai_chat", "reports", "integrations"],
        }


class TenantService:
    """
    Serviço central de multi-tenancy.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_tenant(
        self, name: str, sector: str, admin_user_id: int, plan: str = "starter"
    ) -> Company:
        """
        Cria novo tenant (empresa).
        """
        # Criar empresa
        company = Company(name=name, sector=sector, revenue_year=0)
        self.db.add(company)
        self.db.flush()  # Para obter o ID

        # Associar admin à empresa
        user = self.db.query(User).filter(User.id == admin_user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario administrador nao encontrado")

        user_company = UserCompany(
            user_id=admin_user_id,
            company_id=company.id,
            role_in_tenant="owner",
            is_primary=True,
        )
        self.db.add(user_company)
        user.companies.append(company)

        # TODO: Criar configurações do plano
        # TODO: Criar limites de uso

        self.db.commit()
        self.db.refresh(company)

        return company

    def get_user_tenants(self, user_id: int) -> list[dict]:
        """
        Retorna todos os tenants que o usuário pode acessar.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        if is_platform_admin(user):
            # Apenas platform_admin cruza tenants. Admin comum e' admin do tenant.
            companies = self.db.query(Company).all()
        else:
            company_ids = get_user_company_ids(user)
            companies = self.db.query(Company).filter(Company.id.in_(company_ids)).all()

        return [
            {
                "id": c.id,
                "name": c.name,
                "sector": c.sector,
                "role": user.role,
                "is_active": True,
            }
            for c in companies
        ]

    def validate_tenant_access(self, user_id: int, company_id: int) -> bool:
        """
        Valida se usuário tem acesso ao tenant.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        return check_company_access(user, company_id)

    def get_tenant_stats(self, company_id: int) -> dict:
        """
        Retorna estatísticas de uso do tenant.
        """
        # Contar registros por tabela
        stats = {}

        tables = [
            "products",
            "customers",
            "sales_orders",
            "production_orders",
            "inventory",
            "suppliers",
            "chat_sessions",
            "financial_statements",
        ]

        for table in tables:
            result = self.db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE company_id = :company_id"),
                {"company_id": company_id},
            ).scalar()
            stats[table] = result

        # Usuários no tenant
        user_count = self.db.execute(
            text("SELECT COUNT(*) FROM user_companies WHERE company_id = :company_id"),
            {"company_id": company_id},
        ).scalar()
        stats["users"] = user_count

        return stats

    def switch_tenant(self, user_id: int, company_id: int) -> TenantContext:
        """
        Cria contexto de tenant para requisição.
        """
        if not self.validate_tenant_access(user_id, company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado a este tenant"
            )

        return TenantContext(company_id, user_id, self.db)


def require_tenant_access(company_id_param: str = "company_id"):
    """
    Decorator/Dependency para verificar acesso a tenant em endpoints.
    Uso: Depends(require_tenant_access())
    """

    def checker(
        request: Request,
        current_user=None,  # Será injetado pelo FastAPI
    ):
        # Extrair company_id do path ou query
        company_id = request.path_params.get(company_id_param) or request.query_params.get(
            company_id_param
        )

        if not company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="company_id é obrigatório"
            )

        # Verificação será feita no endpoint usando TenantService
        return int(company_id)

    return checker


def get_tenant_service(db: Session) -> TenantService:
    """Factory para injeção de dependência."""
    return TenantService(db)
