"""Manual ERP file import endpoints."""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.database import get_db
from app.integrations.erp_importer import import_erp_data
from app.models import ERPImportBatch, User

router = APIRouter(prefix="/integrations/erp", tags=["ERP Imports"])


@router.post("/upload")
async def upload_erp_file(
    company_id: int = Form(...),
    data_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Use arquivos .csv, .xlsx ou .xls")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        return import_erp_data(
            company_id=company_id,
            data_type=data_type,
            file_path=tmp_path,
            file_name=file.filename or "upload",
            db=db,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/history/{company_id}")
def import_history(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    batches = (
        db.query(ERPImportBatch)
        .filter(ERPImportBatch.company_id == company_id)
        .order_by(ERPImportBatch.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": batch.id,
            "data_type": batch.data_type,
            "file_name": batch.file_name,
            "rows_received": batch.rows_received,
            "rows_imported": batch.rows_imported,
            "rows_rejected": batch.rows_rejected,
            "status": batch.status,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
        }
        for batch in batches
    ]
