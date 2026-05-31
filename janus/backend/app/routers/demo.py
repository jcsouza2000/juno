"""Demo endpoints used by the executive demo UI."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.database import get_db
from app.demo import get_demo_summary
from app.models import User

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/summary/{company_id}")
def demo_summary(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return get_demo_summary(company_id, db)
