"""Financial statement upload and summary endpoints."""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.database import get_db
from app.financials import (
    get_financial_summary,
    get_statements,
    get_upload_history,
    parse_financial_file,
    save_financial_statements,
)
from app.models import User
from app.valuation_scenario import run_valuation_scenario
from app.comparativos_cenario import build_comparativos_cenario

router = APIRouter(prefix="/financials", tags=["Financials"])


@router.post("/upload")
async def upload_financials(
    company_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(status_code=400, detail="Use arquivos .xlsx, .xls ou .csv")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        rows = parse_financial_file(tmp_path)
        return save_financial_statements(
            company_id=company_id,
            rows=rows,
            file_name=file.filename or "upload",
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/{company_id}")
def list_financial_statements(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return get_statements(company_id, db)


@router.get("/{company_id}/summary")
def financial_summary(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return get_financial_summary(company_id, db)


@router.get("/{company_id}/history")
def financial_upload_history(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return get_upload_history(company_id, db)


@router.get("/{company_id}/valuation/scenario")
def valuation_scenario(
    company_id: int,
    anos: int = 5,
    crescimento_receita_pct: float = 10.0,
    crescimento_custos_fixos_pct: float = 5.0,
    taxa_desconto_pct: float = 10.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    try:
        return run_valuation_scenario(
            company_id,
            db,
            anos=anos,
            crescimento_receita=crescimento_receita_pct / 100.0,
            crescimento_custos_fixos=crescimento_custos_fixos_pct / 100.0,
            taxa_desconto=taxa_desconto_pct / 100.0,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{company_id}/comparativos/cenario")
def comparativos_cenario(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    try:
        return build_comparativos_cenario(company_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
