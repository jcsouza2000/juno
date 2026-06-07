import os
from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.models import Company, User, UserCompany

# Configuracoes vem de variaveis de ambiente (app.config.Settings).
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    if settings.is_development and not get_user_company_ids(user):
        ensure_dev_tenant_membership(db, user)
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = utcnow_naive() + expires_delta
    else:
        expire = utcnow_naive() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def dev_auth_bypass_enabled() -> bool:
    return settings.is_development and settings.JUNO_DEV_AUTH_BYPASS


def ensure_dev_tenant_membership(db: Session, user: User) -> Company:
    """Ensure local development users always have one tenant for uploads."""
    company = db.query(Company).filter(Company.name == "JUNO Dev Tenant").first()
    if company is None:
        company = Company(name="JUNO Dev Tenant", sector="development", revenue_year=0)
        db.add(company)
        db.flush()

    if company not in (user.companies or []):
        user.companies.append(company)
        db.flush()

    membership = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id, UserCompany.company_id == company.id)
        .first()
    )
    if membership is None:
        db.add(
            UserCompany(
                user_id=user.id,
                company_id=company.id,
                role_in_tenant="owner" if user.role in {"admin", "platform_admin"} else "member",
                is_primary=True,
            )
        )
    db.commit()

    # DEV: vincula tambem a empresa de demonstracao (mesma do dashboard) para que
    # a IA e os endpoints v1 consultem o tenant com dados reais. Controlado por env
    # JUNO_DEV_COMPANY_ID; quando definido, esse tenant vira o primario do dev-user.
    _link_dev_demo_company(db, user)

    db.refresh(user)
    return company


def _link_dev_demo_company(db: Session, user: User) -> None:
    """Vincula o dev-user a JUNO_DEV_COMPANY_ID e marca-a como tenant primario."""
    raw = os.getenv("JUNO_DEV_COMPANY_ID", "").strip()
    if not raw:
        return
    try:
        demo_id = int(raw)
    except ValueError:
        return

    demo = db.query(Company).filter(Company.id == demo_id).first()
    if demo is None:
        return

    if demo not in (user.companies or []):
        user.companies.append(demo)
        db.flush()

    # Demais memberships deixam de ser primarias; a demo passa a ser a primaria.
    memberships = db.query(UserCompany).filter(UserCompany.user_id == user.id).all()
    demo_membership = None
    for m in memberships:
        if m.company_id == demo_id:
            demo_membership = m
        elif m.is_primary:
            m.is_primary = False

    if demo_membership is None:
        db.add(
            UserCompany(
                user_id=user.id,
                company_id=demo_id,
                role_in_tenant="owner" if user.role in {"admin", "platform_admin"} else "member",
                is_primary=True,
            )
        )
    else:
        demo_membership.is_primary = True

    db.commit()


def get_or_create_dev_user(db: Session) -> User:
    """Cria um usuario admin local para desenvolvimento sem senha."""
    company = db.query(Company).filter(Company.name == "JUNO Dev Tenant").first()
    if company is None:
        company = Company(name="JUNO Dev Tenant", sector="development", revenue_year=0)
        db.add(company)
        db.flush()

    user = db.query(User).filter(User.email == "dev@juno.local").first()
    if user is None:
        user = User(
            email="dev@juno.local",
            full_name="JUNO Dev",
            hashed_password=get_password_hash("dev-only"),
            role="admin",
            is_active=True,
        )
        user.companies.append(company)
        db.add(user)
        db.flush()
    ensure_dev_tenant_membership(db, user)
    return user


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        if dev_auth_bypass_enabled():
            return get_or_create_dev_user(db)
        raise credentials_exception
    try:
        payload = decode_token(token)
        email = payload.get("sub")
        if not isinstance(email, str):
            raise credentials_exception
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Usuario inativo")
    return current_user


def require_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in {"admin", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


def is_platform_admin(user: User) -> bool:
    """Platform admins can cross tenant boundaries; tenant admins cannot."""
    return user.role == "platform_admin"


def check_company_access(user: User, company_id: int):
    if is_platform_admin(user):
        return True
    return company_id in get_user_company_ids(user)


def get_user_company_ids(user: User) -> list[int]:
    """Return company ids linked to the current user."""
    company_ids = {c.id for c in (user.companies or [])}
    company_ids.update(m.company_id for m in (user.tenant_memberships or []))
    return sorted(company_ids)


def get_primary_company_id(user: User) -> int:
    """
    Resolve the active company for legacy endpoints that still assume one company.

    The current model is many-to-many. Until the UI sends an explicit company
    selector to every v1 endpoint, use the first linked company and fail clearly
    when the user has no tenant.
    """
    company_ids = get_user_company_ids(user)
    if not company_ids:
        raise HTTPException(status_code=403, detail="Usuario sem empresa vinculada")
    return company_ids[0]
