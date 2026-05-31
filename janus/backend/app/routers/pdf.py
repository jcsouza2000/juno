"""PDF report endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.database import get_db
from app.models import User
from app.pdf_service import get_pdf_service

router = APIRouter(prefix="/reports", tags=["Reports"])
legacy_router = APIRouter(prefix="/report", tags=["Reports"])


@router.get("/pdf/{company_id}")
def generate_pdf_report(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate the executive PDF report."""
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    try:
        pdf_service = get_pdf_service(db)
        pdf_bytes = pdf_service.generate_executive_report(company_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=juno_report_empresa_{company_id}.pdf"
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {exc}") from exc


@router.get("/pdf/{company_id}/preview")
def get_pdf_info(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return report metadata before generating the PDF."""
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    from app.score_v2 import get_score_calculator

    calculator = get_score_calculator(db)
    result = calculator.calculate_full_score(company_id)
    return {
        "company_id": company_id,
        "company_name": result.company_name,
        "score": result.overall_score,
        "trend": result.trend,
        "components_count": len(result.components),
        "recommendations_count": len(result.recommendations),
        "available": True,
    }


legacy_router.add_api_route(
    "/pdf/{company_id}",
    generate_pdf_report,
    methods=["GET"],
    include_in_schema=False,
)
legacy_router.add_api_route(
    "/pdf/{company_id}/preview",
    get_pdf_info,
    methods=["GET"],
    include_in_schema=False,
)
