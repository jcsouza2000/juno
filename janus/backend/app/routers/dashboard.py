"""Operational dashboard endpoints used by the Minha Empresa view."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.dashboards import get_ceo_kpis, get_cfo_margin_by_product, get_coo_delayed_orders
from app.database import get_db
from app.insights import generate_insights
from app.models import User
from app.schemas.metrics import (
    CeoDashboardResponse,
    CfoMarginItem,
    CooDelayedOrderItem,
    InsightItem,
)

router = APIRouter(tags=["Dashboard"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
insights_router = APIRouter(prefix="/insights", tags=["Insights"])


def _ensure_access(current_user: User, company_id: int) -> None:
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")


@dashboard_router.get("/ceo/{company_id}", response_model=CeoDashboardResponse)
def ceo_dashboard(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(current_user, company_id)
    return get_ceo_kpis(db, company_id)


@dashboard_router.get("/cfo/{company_id}", response_model=list[CfoMarginItem])
def cfo_dashboard(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(current_user, company_id)
    return get_cfo_margin_by_product(db, company_id)


@dashboard_router.get("/coo/{company_id}", response_model=list[CooDelayedOrderItem])
def coo_dashboard(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(current_user, company_id)
    return get_coo_delayed_orders(db, company_id)


@insights_router.get("/{company_id}", response_model=list[InsightItem])
def company_insights(
    company_id: int,
    lang: str = "pt",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_access(current_user, company_id)
    return generate_insights(company_id, db, lang=lang)


router.include_router(dashboard_router)
router.include_router(insights_router)
