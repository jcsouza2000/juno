"""Business event timeline endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.audit_center import get_events
from app.auth import check_company_access, decode_token, get_current_active_user
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/events", tags=["Eventos"])


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


def _ensure_access(company_id: int, user: User | None) -> None:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais invalidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not check_company_access(user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{company_id}")
def list_events(
    company_id: int,
    event_type: str | None = None,
    days: int | None = Query(default=None, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
    count_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(company_id, current_user)
    return get_events(
        company_id,
        db,
        event_type=event_type,
        days=days,
        limit=limit,
        count_only=count_only,
    )
