"""PDF report endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.dashboards import get_ceo_kpis
from app.database import get_db
from app.insights import generate_insights
from app.models import User
from app.pdf_service import get_pdf_service
from app.score_v2 import get_score_calculator

router = APIRouter(prefix="/reports", tags=["Reports"])
legacy_router = APIRouter(prefix="/report", tags=["Reports"])


def build_diagnostic(company_id: int, db: Session, lang: str = "pt") -> dict:
    """Diagnostico 360 em JSON: score, receita, insights, recomendacoes e plano.

    Reaproveita score_v2 (score + recomendacoes), generate_insights (riscos) e
    get_ceo_kpis (receita liquida). O plano de acao deriva das acoes dos insights
    com fallback nas recomendacoes do score.
    """
    result = get_score_calculator(db).calculate_full_score(company_id, persist=False, lang=lang)
    insights = generate_insights(company_id, db, lang=lang)
    ceo = get_ceo_kpis(db, company_id)

    action_plan = [i["action"] for i in insights if i.get("action")]
    if not action_plan:
        action_plan = list(result.recommendations)

    return {
        "company_name": result.company_name,
        "score_juno": round(result.overall_score, 1),
        "revenue": float(ceo.get("receita_liquida") or 0),
        "insights": [
            {"message": i.get("message", ""), "impact": i.get("impact", "")} for i in insights
        ],
        "recommendations": list(result.recommendations),
        "action_plan": action_plan,
    }


@router.get("/pdf/{company_id}")
def generate_pdf_report(
    company_id: int,
    lang: str = "pt",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate the executive PDF report. lang: pt|en|es (segue o seletor da UI)."""
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    try:
        pdf_service = get_pdf_service(db)
        pdf_bytes = pdf_service.generate_executive_report(company_id, lang=lang)
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


@router.get("/diagnostic/{company_id}")
def diagnostic_report(
    company_id: int,
    lang: str = "pt",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Diagnostico Operacional 360 em JSON (consumido pela aba Minha Empresa)."""
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return build_diagnostic(company_id, db, lang=lang)


legacy_router.add_api_route(
    "/diagnostic/{company_id}",
    diagnostic_report,
    methods=["GET"],
    include_in_schema=False,
)
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
