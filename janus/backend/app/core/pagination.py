"""
Helpers de paginacao reutilizaveis.

Uso em routers:

    from fastapi import Depends
    from app.core.pagination import PaginationParams, paginate

    @router.get("/items")
    def list_items(
        pagination: PaginationParams = Depends(),
        db: Session = Depends(get_db),
    ):
        return paginate(db.query(Item), pagination)
"""

from typing import Any

from fastapi import Query
from sqlalchemy.orm import Query as SAQuery

MAX_LIMIT = 100
DEFAULT_LIMIT = 20


class PaginationParams:
    """Parametros de paginacao via query string: ?skip=0&limit=20."""

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Offset"),
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description=f"Maximo {MAX_LIMIT}"),
    ):
        self.skip = skip
        self.limit = limit

    def __repr__(self) -> str:
        return f"PaginationParams(skip={self.skip}, limit={self.limit})"


def paginate(query: SAQuery, params: PaginationParams) -> dict[str, Any]:
    """
    Aplica paginacao a uma query SQLAlchemy.
    Retorna: {"items": [...], "total": int, "skip": int, "limit": int}
    """
    total = query.count()
    items: list[Any] = query.offset(params.skip).limit(params.limit).all()
    return {
        "items": items,
        "total": total,
        "skip": params.skip,
        "limit": params.limit,
    }
