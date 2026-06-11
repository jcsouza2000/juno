"""
Versionamento de depositos de dados (Fase B).

Financeiro: cada upload gera uma versao (v1, v2, ...) sem apagar versoes
anteriores. As linhas em financial_statements referenciam upload_batch_id;
o dashboard consulta apenas a versao ativa (is_active=True).

ERP: versionamento de metadados no lote de importacao (historico auditavel).
A troca de versao ativa para ERP registra qual lote foi promovido; os dados
operacionais continuam sendo o conjunto atual do tenant ate Fase B+.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import ERPImportBatch, FinancialStatement, FinancialUploadBatch

Source = str  # "financial" | "erp"


class VersioningError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _batch_model(source: Source):
    if source == "financial":
        return FinancialUploadBatch
    if source == "erp":
        return ERPImportBatch
    raise VersioningError(f"Origem invalida: {source!r}. Use 'financial' ou 'erp'.")


def next_version_number(db: Session, company_id: int, source: Source) -> int:
    model = _batch_model(source)
    current = (
        db.query(model.version_number)
        .filter(model.company_id == company_id)
        .order_by(model.version_number.desc())
        .first()
    )
    return (current[0] if current else 0) + 1


def deactivate_batches(db: Session, company_id: int, source: Source) -> None:
    model = _batch_model(source)
    db.query(model).filter(model.company_id == company_id).update(
        {model.is_active: False}, synchronize_session=False
    )


def get_active_batch_id(db: Session, company_id: int, source: Source) -> int | None:
    model = _batch_model(source)
    row = (
        db.query(model.id)
        .filter(model.company_id == company_id, model.is_active.is_(True))
        .order_by(model.version_number.desc())
        .first()
    )
    return row[0] if row else None


def get_active_financial_batch_id(db: Session, company_id: int) -> int | None:
    return get_active_batch_id(db, company_id, "financial")


def list_versions(db: Session, company_id: int, source: Source) -> list[dict]:
    model = _batch_model(source)
    rows = (
        db.query(model)
        .filter(model.company_id == company_id)
        .order_by(model.version_number.desc())
        .all()
    )
    out: list[dict] = []
    for b in rows:
        item = {
            "id": b.id,
            "source": source,
            "version_number": b.version_number,
            "version_label": f"v{b.version_number}",
            "is_active": bool(b.is_active),
            "file_name": b.file_name,
            "rows": b.rows_imported,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        if source == "financial":
            item["periods"] = b.periods
        else:
            item["data_type"] = b.data_type
        out.append(item)
    return out


def activate_version(db: Session, company_id: int, source: Source, batch_id: int) -> dict:
    model = _batch_model(source)
    batch = db.query(model).filter(model.id == batch_id, model.company_id == company_id).first()
    if batch is None:
        raise VersioningError("Versao nao encontrada para este tenant.", status_code=404)

    deactivate_batches(db, company_id, source)
    batch.is_active = True
    db.commit()
    db.refresh(batch)

    payload = {
        "status": "activated",
        "source": source,
        "batch_id": batch.id,
        "version_number": batch.version_number,
        "version_label": f"v{batch.version_number}",
        "is_active": True,
    }
    if source == "financial":
        payload["rows_visible"] = (
            db.query(FinancialStatement)
            .filter(
                FinancialStatement.company_id == company_id,
                FinancialStatement.upload_batch_id == batch.id,
            )
            .count()
        )
    else:
        payload["note"] = (
            "Versao ERP ativa atualizada (metadados). "
            "Dados operacionais refletem o ultimo import completo."
        )
    return payload


def register_financial_upload_batch(
    db: Session,
    company_id: int,
    file_name: str,
    periods: str,
    rows_imported: int,
) -> FinancialUploadBatch:
    version = next_version_number(db, company_id, "financial")
    deactivate_batches(db, company_id, "financial")
    batch = FinancialUploadBatch(
        company_id=company_id,
        file_name=file_name,
        periods=periods,
        rows_imported=rows_imported,
        status="success",
        version_number=version,
        is_active=True,
    )
    db.add(batch)
    db.flush()
    return batch


def register_erp_import_batch(
    db: Session,
    company_id: int,
    *,
    data_type: str,
    file_name: str | None,
    rows_received: int,
    rows_imported: int,
    rows_rejected: int,
    status: str,
    error_message: str | None = None,
) -> ERPImportBatch:
    version = next_version_number(db, company_id, "erp")
    deactivate_batches(db, company_id, "erp")
    batch = ERPImportBatch(
        company_id=company_id,
        data_type=data_type,
        file_name=file_name,
        rows_received=rows_received,
        rows_imported=rows_imported,
        rows_rejected=rows_rejected,
        status=status,
        error_message=error_message,
        version_number=version,
        is_active=True,
    )
    db.add(batch)
    db.flush()
    return batch
