"""
Schemas Pydantic para gestao de membros de um tenant (Fase 1 — multi-usuario).

Papeis no tenant (role_in_tenant), independentes do papel global do usuario:
  owner  — controle total, inclui gerir outros membros e o proprio tenant.
  admin  — gere membros (exceto owners) e dados do tenant.
  member — uso operacional (leitura/escrita de dados).
  viewer — somente leitura.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

VALID_TENANT_ROLES = ("owner", "admin", "member", "viewer")


class TenantMemberOut(BaseModel):
    """Membro de um tenant exposto na API."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    # str (nao EmailStr): schema de saida nao deve re-validar emails ja
    # armazenados — enderecos internos como dev@juno.local sao rejeitados
    # pelo validador de EmailStr (TLD .local reservado) e quebrariam a listagem.
    email: str
    full_name: str | None = None
    role_in_tenant: str
    is_primary: bool = False
    global_role: str
    is_active: bool = True
    joined_at: str | None = None


class TenantMemberCreate(BaseModel):
    """Convite/criacao de membro. Se o email ja existe, apenas vincula."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    full_name: str | None = None
    # Senha inicial opcional; se ausente, o backend gera uma temporaria e a
    # devolve uma unica vez para o admin repassar ao usuario.
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role_in_tenant: str = "member"


class TenantMemberUpdate(BaseModel):
    """Alteracao do papel de um membro dentro do tenant."""

    model_config = ConfigDict(extra="ignore")

    role_in_tenant: str


class TenantMemberCreateResponse(BaseModel):
    """Resposta da criacao: o membro e, se gerada, a senha temporaria."""

    member: TenantMemberOut
    created_user: bool
    temp_password: str | None = None
