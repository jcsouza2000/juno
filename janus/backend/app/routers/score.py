"""
JUNO Score Router — Endpoints do Score JUNO 2.0
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.database import get_db
from app.models import User
from app.schemas.metrics import ScoreResponse
from app.score_v2 import get_score_calculator

router = APIRouter(prefix="/score", tags=["Score JUNO"])


@router.get("/{company_id}", response_model=ScoreResponse)
def get_score(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calcula e retorna o Score JUNO 2.0 completo.
    """
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    calculator = get_score_calculator(db)
    result = calculator.calculate_full_score(company_id)

    return {
        "company_id": result.company_id,
        "company_name": result.company_name,
        "overall_score": result.overall_score,
        "trend": result.trend,
        "trend_delta": result.trend_delta,
        "calculation_date": result.calculation_date.isoformat(),
        "components": [
            {
                "name": c.name,
                "weight": c.weight,
                "raw_value": c.raw_value,
                "normalized_score": c.normalized_score,
                "weighted_score": c.weighted_score,
                "details": c.details,
            }
            for c in result.components
        ],
        "recommendations": result.recommendations,
    }


@router.get("/{company_id}/history")
def get_score_history(
    company_id: int,
    days: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retorna histórico de scores para gráficos.
    """
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    calculator = get_score_calculator(db)
    history = calculator.get_score_history(company_id, days)

    return {"company_id": company_id, "days": days, "data_points": len(history), "history": history}


@router.post("/{company_id}/recalculate")
def recalculate_score(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Força recálculo do score (útil após importação de dados).
    """
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    calculator = get_score_calculator(db)
    result = calculator.calculate_full_score(company_id)

    return {
        "message": "Score recalculado com sucesso",
        "overall_score": result.overall_score,
        "trend": result.trend,
    }
