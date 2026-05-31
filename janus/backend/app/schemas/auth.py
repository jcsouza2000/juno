"""
Schemas Pydantic para autenticação.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyOut(BaseModel):
    """Empresa exposta na API — campos seguros para listar/retornar."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    """User exposto na API — NUNCA inclui hashed_password."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    role: str
    companies: list[CompanyOut] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserMeResponse(UserOut):
    """Alias para `/auth/me` — retornado quando o usuário consulta a si próprio."""

    pass
