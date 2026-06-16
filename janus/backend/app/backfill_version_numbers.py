"""Renumerar lotes legados (pre-Fase B) como v1, v2, ... por ordem de id."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ERPImportBatch, FinancialUploadBatch


def backfill_batch_version_numbers(db: Session) -> dict:
    stats = {"financial": 0, "erp": 0}
    for model, key in ((FinancialUploadBatch, "financial"), (ERPImportBatch, "erp")):
        company_ids = [
            row[0] for row in db.query(model.company_id).distinct().order_by(model.company_id).all()
        ]
        for company_id in company_ids:
            rows = db.query(model).filter(model.company_id == company_id).order_by(model.id).all()
            for idx, batch in enumerate(rows, start=1):
                batch.version_number = idx  # type: ignore[attr-defined]
                batch.is_active = idx == len(rows)  # type: ignore[attr-defined]
                stats[key] += 1
    db.commit()
    return stats


if __name__ == "__main__":
    from app.database import SessionLocal

    with SessionLocal() as db:
        print(backfill_batch_version_numbers(db))
