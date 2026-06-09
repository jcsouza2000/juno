"""
Service de retencao / fechamento mensal (Fase 5).

Congela um snapshot imutavel de KPIs e demonstracoes do tenant para um
(ano, mes). O snapshot reusa o resumo financeiro e o Score JUNO ja existentes.

Nao importa fastapi: erros viram RetentionError (com status_code), convertido
pelo router em HTTPException — mantem o service testavel sem subir o app.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.models import MonthlyClose


class RetentionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _validate_period(year: int, month: int) -> None:
    if not (1 <= month <= 12):
        raise RetentionError("Mes invalido (use 1-12).")
    if not (2000 <= year <= 2100):
        raise RetentionError("Ano invalido.")


def build_snapshot(db: Session, company_id: int) -> dict:
    """Monta o snapshot atual do tenant: resumo financeiro + Score JUNO.

    Robusto: falhas em sub-partes nao derrubam o snapshot — registram null.
    """
    snapshot: dict = {"generated_at": utcnow_naive().isoformat(), "company_id": company_id}

    try:
        from app.financials import get_financial_summary

        snapshot["financial"] = get_financial_summary(company_id, db)
    except Exception as exc:  # noqa: BLE001
        snapshot["financial"] = None
        snapshot["financial_error"] = str(exc)

    try:
        from app.score_v2 import get_score_calculator

        score = get_score_calculator(db).calculate_full_score(company_id, persist=False)
        snapshot["score"] = {
            "overall": getattr(score, "overall_score", None),
        }
    except Exception as exc:  # noqa: BLE001
        snapshot["score"] = None
        snapshot["score_error"] = str(exc)

    return snapshot


def _to_dict(close: MonthlyClose) -> dict:
    return {
        "id": close.id,
        "company_id": close.company_id,
        "year": close.year,
        "month": close.month,
        "status": close.status,
        "closed_at": close.closed_at.isoformat() if close.closed_at else None,
        "closed_by": close.closed_by,
        "snapshot": json.loads(close.snapshot) if close.snapshot else None,
    }


def create_monthly_close(
    db: Session, company_id: int, year: int, month: int, closed_by: int | None = None
) -> dict:
    """Cria o fechamento mensal imutavel do tenant para (year, month).

    Erro 409 se ja existir — fechamentos nao sao sobrescritos.
    """
    _validate_period(year, month)

    existing = (
        db.query(MonthlyClose)
        .filter(
            MonthlyClose.company_id == company_id,
            MonthlyClose.year == year,
            MonthlyClose.month == month,
        )
        .first()
    )
    if existing is not None:
        raise RetentionError(
            f"Fechamento de {year}-{month:02d} ja existe e e imutavel.", status_code=409
        )

    snapshot = build_snapshot(db, company_id)
    close = MonthlyClose(
        company_id=company_id,
        year=year,
        month=month,
        snapshot=json.dumps(snapshot, default=str, ensure_ascii=False),
        status="closed",
        closed_by=closed_by,
        closed_at=utcnow_naive(),
    )
    db.add(close)
    db.commit()
    db.refresh(close)
    return _to_dict(close)


def list_monthly_closes(db: Session, company_id: int) -> list[dict]:
    """Lista fechamentos do tenant (mais recentes primeiro), sem o snapshot."""
    rows = (
        db.query(MonthlyClose)
        .filter(MonthlyClose.company_id == company_id)
        .order_by(MonthlyClose.year.desc(), MonthlyClose.month.desc())
        .all()
    )
    result = []
    for c in rows:
        item = _to_dict(c)
        item.pop("snapshot", None)  # listagem e' enxuta
        result.append(item)
    return result


def get_monthly_close(db: Session, company_id: int, year: int, month: int) -> dict:
    """Retorna um fechamento especifico (com snapshot completo)."""
    close = (
        db.query(MonthlyClose)
        .filter(
            MonthlyClose.company_id == company_id,
            MonthlyClose.year == year,
            MonthlyClose.month == month,
        )
        .first()
    )
    if close is None:
        raise RetentionError("Fechamento nao encontrado.", status_code=404)
    return _to_dict(close)
