"""
Router de autenticacao -- /auth/login e /auth/me.

Aplica rate limit (slowapi) em /login para mitigar ataques de forca bruta.
Retorna sempre via schemas Pydantic (app.schemas.auth) -- nunca expoe o
model SQLAlchemy diretamente, evitando vazar campos sensiveis.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth import authenticate_user, create_access_token, get_current_active_user
from app.config import settings
from app.core.logger import get_logger
from app.database import get_db
from app.schemas.auth import CompanyOut, LoginResponse, UserMeResponse, UserOut

logger = get_logger(__name__)

# O limiter e o mesmo singleton registrado em main.py -- slowapi resolve
# pela funcao key_func, entao criar outra instancia aqui e equivalente.
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["Autenticacao"])


def _serialize_user(user) -> UserOut:
    """Converte o model SQLAlchemy para o schema seguro."""
    companies = {c.id: c for c in (user.companies or [])}
    for membership in user.tenant_memberships or []:
        if membership.company:
            companies[membership.company.id] = membership.company
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        companies=[CompanyOut(id=c.id, name=c.name) for c in companies.values()],
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    client_host = request.client.host if request.client else "?"
    if not user:
        logger.warning(f"Login falhou: email={form_data.username} ip={client_host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    logger.info(f"Login OK: user_id={user.id} email={user.email} ip={client_host}")
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=_serialize_user(user),
    )


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user=Depends(get_current_active_user)):
    return _serialize_user(current_user)
