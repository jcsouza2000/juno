"""
JUNO Reports & BI API Routes
Endpoints para relatórios, dashboards e exportação
"""

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_primary_company_id
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.models import DashboardDefinition, ReportDefinition, ReportExecution, ReportFavorite
from app.reports.export_engine import ExportEngine
from app.reports.report_engine import DashboardEngine, ReportEngine
from app.reports.templates import create_from_template, list_templates

router = APIRouter(prefix="/api/v1/reports", tags=["Reports & BI"])


def _company_id(user) -> int:
    return get_primary_company_id(user)


# ============================================================
# SCHEMAS
# ============================================================


class ReportCreate(BaseModel):
    name: str
    description: str | None = None
    report_type: str  # table, chart, pivot, dashboard
    data_source: str  # sql, entity, api
    query_config: dict[str, Any] | None = None
    filter_config: list[dict] | None = None
    column_config: list[dict] | None = None
    chart_config: dict[str, Any] | None = None
    sort_config: list[dict] | None = None
    group_by_config: list[str] | None = None


class ReportUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    query_config: dict[str, Any] | None = None
    filter_config: list[dict] | None = None
    column_config: list[dict] | None = None
    chart_config: dict[str, Any] | None = None
    sort_config: list[dict] | None = None


class DashboardCreate(BaseModel):
    name: str
    description: str | None = None
    layout_config: dict[str, Any] | None = None
    widget_configs: list[dict] | None = None
    refresh_interval_seconds: int | None = 300


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    layout_config: dict[str, Any] | None = None
    widget_configs: list[dict] | None = None


class ExecuteReportRequest(BaseModel):
    parameters: dict[str, Any] | None = None
    page: int = 1
    page_size: int = 1000


class ExportReportRequest(BaseModel):
    format: str  # pdf, excel, csv, json
    parameters: dict[str, Any] | None = None


# ============================================================
# ROTAS — TEMPLATES
# ============================================================


@router.get("/templates")
def list_report_templates(
    category: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Lista templates de relatórios disponíveis."""
    templates = list_templates(category)
    return {
        "templates": [
            {
                "key": k,
                "name": v["name"],
                "description": v["description"],
                "category": v.get("template_category"),
                "type": v["report_type"],
            }
            for k, v in templates.items()
        ]
    }


@router.post("/templates/{template_key}/create")
def create_from_template_endpoint(
    template_key: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Cria relatório a partir de template."""
    try:
        config = create_from_template(template_key, _company_id(user), user.id)

        report = ReportDefinition(**config)
        db.add(report)
        db.commit()
        db.refresh(report)

        return {
            "id": report.id,
            "name": report.name,
            "message": "Relatório criado do template com sucesso",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================
# ROTAS — RELATÓRIOS
# ============================================================


@router.post("/definitions")
def create_report(
    data: ReportCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Cria nova definição de relatório."""
    report = ReportDefinition(company_id=_company_id(user), created_by=user.id, **data.dict())
    db.add(report)
    db.commit()
    db.refresh(report)

    return {"id": report.id, "name": report.name, "message": "Relatório criado com sucesso"}


@router.get("/definitions")
def list_reports(
    report_type: str | None = None,
    data_source: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista relatórios da empresa."""
    query = db.query(ReportDefinition).filter(
        ReportDefinition.company_id == _company_id(user), ReportDefinition.status == "active"
    )

    if report_type:
        query = query.filter(ReportDefinition.report_type == report_type)
    if data_source:
        query = query.filter(ReportDefinition.data_source == data_source)

    reports = query.order_by(ReportDefinition.created_at.desc()).all()

    return {
        "reports": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "report_type": r.report_type,
                "data_source": r.data_source,
                "is_template": r.is_template,
                "template_category": r.template_category,
                "last_executed_at": r.last_executed_at.isoformat() if r.last_executed_at else None,
                "execution_count": r.execution_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
    }


@router.get("/definitions/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Obtém detalhes do relatório."""
    report = (
        db.query(ReportDefinition)
        .filter(ReportDefinition.id == report_id, ReportDefinition.company_id == _company_id(user))
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    return {
        "id": report.id,
        "name": report.name,
        "description": report.description,
        "report_type": report.report_type,
        "data_source": report.data_source,
        "query_config": json.loads(report.query_config) if report.query_config else None,
        "filter_config": json.loads(report.filter_config) if report.filter_config else None,
        "column_config": json.loads(report.column_config) if report.column_config else None,
        "chart_config": json.loads(report.chart_config) if report.chart_config else None,
        "sort_config": json.loads(report.sort_config) if report.sort_config else None,
        "group_by_config": json.loads(report.group_by_config) if report.group_by_config else None,
        "is_scheduled": report.is_scheduled,
        "schedule_cron": report.schedule_cron,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.put("/definitions/{report_id}")
def update_report(
    report_id: int,
    data: ReportUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Atualiza relatório."""
    report = (
        db.query(ReportDefinition)
        .filter(ReportDefinition.id == report_id, ReportDefinition.company_id == _company_id(user))
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, json.dumps(value) if isinstance(value, (dict, list)) else value)

    report.updated_at = utcnow_naive()
    db.commit()

    return {"message": "Relatório atualizado"}


@router.delete("/definitions/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Remove relatório."""
    report = (
        db.query(ReportDefinition)
        .filter(ReportDefinition.id == report_id, ReportDefinition.company_id == _company_id(user))
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    db.delete(report)
    db.commit()
    return {"message": "Relatório removido"}


# ============================================================
# ROTAS — EXECUÇÃO & EXPORTAÇÃO
# ============================================================


@router.post("/definitions/{report_id}/execute")
def execute_report(
    report_id: int,
    request: ExecuteReportRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Executa relatório e retorna dados."""
    report = (
        db.query(ReportDefinition)
        .filter(ReportDefinition.id == report_id, ReportDefinition.company_id == _company_id(user))
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    engine = ReportEngine(db)
    result = engine.execute_report(
        report, parameters=request.parameters, page=request.page, page_size=request.page_size
    )

    # Atualizar estatísticas
    report.execution_count += 1
    report.last_executed_at = utcnow_naive()
    db.commit()

    # Registrar execução
    execution = ReportExecution(
        report_id=report_id,
        company_id=_company_id(user),
        executed_by=user.id,
        status="completed" if result["success"] else "failed",
        parameters=json.dumps(request.parameters) if request.parameters else None,
        row_count=result.get("pagination", {}).get("total_rows"),
        started_at=utcnow_naive(),
        completed_at=utcnow_naive(),
    )
    db.add(execution)
    db.commit()

    return result


@router.post("/definitions/{report_id}/export")
def export_report(
    report_id: int,
    request: ExportReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Exporta relatório para arquivo."""
    report = (
        db.query(ReportDefinition)
        .filter(ReportDefinition.id == report_id, ReportDefinition.company_id == _company_id(user))
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    def do_export():
        engine = ReportEngine(db)
        result = engine.execute_report(report, parameters=request.parameters, page_size=0)

        if not result["success"]:
            return {"error": result.get("error")}

        export_engine = ExportEngine()
        export_result = export_engine.export(
            data=result["data"],
            columns=result["columns"],
            format=request.format,
            title=report.name,
            subtitle=report.description,
        )

        # Registrar execução
        execution = ReportExecution(
            report_id=report_id,
            company_id=_company_id(user),
            executed_by=user.id,
            status="completed",
            parameters=json.dumps(request.parameters) if request.parameters else None,
            row_count=len(result["data"]),
            file_path=export_result["file_path"],
            file_format=request.format,
            file_size_bytes=export_result["file_size"],
            started_at=utcnow_naive(),
            completed_at=utcnow_naive(),
        )
        db.add(execution)
        db.commit()

        return export_result

    background_tasks.add_task(do_export)

    return {
        "message": f"Exportação para {request.format.upper()} iniciada",
        "status": "processing",
        "report_id": report_id,
    }


@router.get("/executions")
def list_executions(
    report_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista histórico de execuções."""
    query = db.query(ReportExecution).filter(ReportExecution.company_id == _company_id(user))
    if report_id:
        query = query.filter(ReportExecution.report_id == report_id)

    executions = query.order_by(ReportExecution.started_at.desc()).limit(limit).all()

    return {
        "executions": [
            {
                "id": e.id,
                "report_id": e.report_id,
                "status": e.status,
                "row_count": e.row_count,
                "file_format": e.file_format,
                "file_size_bytes": e.file_size_bytes,
                "execution_time_ms": e.execution_time_ms,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in executions
        ]
    }


# ============================================================
# ROTAS — DASHBOARDS
# ============================================================


@router.post("/dashboards")
def create_dashboard(
    data: DashboardCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Cria novo dashboard."""
    dashboard = DashboardDefinition(company_id=_company_id(user), created_by=user.id, **data.dict())
    db.add(dashboard)
    db.commit()
    db.refresh(dashboard)

    return {"id": dashboard.id, "name": dashboard.name, "message": "Dashboard criado com sucesso"}


@router.get("/dashboards")
def list_dashboards(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista dashboards."""
    dashboards = (
        db.query(DashboardDefinition)
        .filter(
            DashboardDefinition.company_id == _company_id(user),
            DashboardDefinition.status == "active",
        )
        .order_by(DashboardDefinition.created_at.desc())
        .all()
    )

    return {
        "dashboards": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "is_default": d.is_default,
                "is_public": d.is_public,
                "refresh_interval_seconds": d.refresh_interval_seconds,
                "widget_count": len(json.loads(d.widget_configs or "[]")),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in dashboards
        ]
    }


@router.get("/dashboards/{dashboard_id}")
def get_dashboard(dashboard_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Obtém dashboard com dados renderizados."""
    dashboard = (
        db.query(DashboardDefinition)
        .filter(
            DashboardDefinition.id == dashboard_id,
            DashboardDefinition.company_id == _company_id(user),
        )
        .first()
    )

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard não encontrado")

    engine = DashboardEngine(db)
    rendered = engine.render_dashboard(dashboard)

    return rendered


@router.put("/dashboards/{dashboard_id}")
def update_dashboard(
    dashboard_id: int,
    data: DashboardUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Atualiza dashboard."""
    dashboard = (
        db.query(DashboardDefinition)
        .filter(
            DashboardDefinition.id == dashboard_id,
            DashboardDefinition.company_id == _company_id(user),
        )
        .first()
    )

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard não encontrado")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dashboard, field, json.dumps(value) if isinstance(value, (dict, list)) else value)

    dashboard.updated_at = utcnow_naive()
    db.commit()

    return {"message": "Dashboard atualizado"}


@router.delete("/dashboards/{dashboard_id}")
def delete_dashboard(
    dashboard_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Remove dashboard."""
    dashboard = (
        db.query(DashboardDefinition)
        .filter(
            DashboardDefinition.id == dashboard_id,
            DashboardDefinition.company_id == _company_id(user),
        )
        .first()
    )

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard não encontrado")

    db.delete(dashboard)
    db.commit()
    return {"message": "Dashboard removido"}


# ============================================================
# ROTAS — ENTIDADES DISPONÍVEIS
# ============================================================


@router.get("/entities")
def list_available_entities(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista entidades disponíveis para relatórios."""
    engine = ReportEngine(db)
    entities = engine.get_available_entities()

    return {
        "entities": [
            {"key": k, "name": v, "category": _detect_category(k)} for k, v in entities.items()
        ]
    }


def _detect_category(entity_key: str) -> str:
    """Detecta categoria da entidade."""
    if "sales" in entity_key:
        return "sales"
    elif "inventory" in entity_key or "stock" in entity_key:
        return "inventory"
    elif "financial" in entity_key or "profit" in entity_key:
        return "financial"
    elif "customer" in entity_key:
        return "customers"
    return "general"


# ============================================================
# ROTAS — FAVORITOS
# ============================================================


@router.post("/favorites")
def add_favorite(
    report_id: int | None = None,
    dashboard_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Adiciona relatório ou dashboard aos favoritos."""
    if not report_id and not dashboard_id:
        raise HTTPException(status_code=400, detail="Informe report_id ou dashboard_id")

    favorite = ReportFavorite(user_id=user.id, report_id=report_id, dashboard_id=dashboard_id)
    db.add(favorite)
    db.commit()

    return {"message": "Adicionado aos favoritos"}


@router.get("/favorites")
def list_favorites(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista favoritos do usuário."""
    favorites = db.query(ReportFavorite).filter(ReportFavorite.user_id == user.id).all()

    return {
        "favorites": [
            {
                "id": f.id,
                "report_id": f.report_id,
                "dashboard_id": f.dashboard_id,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in favorites
        ]
    }
