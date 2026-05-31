"""
Schemas reutilizáveis (paginação, erros).
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope padrão para listagens paginadas."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    skip: int
    limit: int


class ErrorResponse(BaseModel):
    """Forma padrão de erros da API."""

    error: str
    detail: str | None = None
