"""Executive KPI dashboards by persona."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth import check_company_access, decode_token, get_current_active_user
from app.database import get_db
from app.kpi_catalog import (
    build_all_dashboards,
    build_persona_dashboard,
    build_unified_dashboard,
    get_kpi_catalog,
)
from app.models import User

router = APIRouter(prefix="/kpis", tags=["KPIs Executivos"])


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


@router.get("/catalog")
def kpi_catalog(persona: str | None = None):
    """Return KPI definitions, optionally filtered by persona."""
    return {"persona": persona, "kpis": get_kpi_catalog(persona)}


@router.get("/{company_id}")
def all_dashboards(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(company_id, current_user)
    return build_all_dashboards(db, company_id)


@router.get("/{company_id}/unified")
def unified_dashboard(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(company_id, current_user)
    return build_unified_dashboard(db, company_id)


@router.get("/{company_id}/{persona}")
def persona_dashboard(
    company_id: int,
    persona: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(company_id, current_user)
    try:
        return build_persona_dashboard(db, company_id, persona)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
