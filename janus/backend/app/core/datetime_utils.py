"""
Helpers de datetime compativeis com Python 3.11/3.12+.

Python 3.12 deprecou `datetime.utcnow()` em favor de
`datetime.now(datetime.UTC)`. Para evitar DeprecationWarning sem quebrar
versoes antigas, use estes helpers em todo o backend.

Uso:
    from app.core.datetime_utils import utcnow_naive

    created_at = Column(DateTime, default=utcnow_naive)  # passe a FUNCAO
    ...
    now = utcnow_naive()                                  # ou chame
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """
    Retorna o instante atual em UTC, timezone-aware.

    Em Python 3.11+ usa `datetime.now(timezone.utc)` (substituto recomendado
    para `datetime.utcnow()` que foi deprecado em 3.12).
    """
    return datetime.now(UTC)


def utcnow_naive() -> datetime:
    """
    Versao timezone-NAIVE (sem tzinfo). Equivalente literal a
    `datetime.utcnow()` da era pre-3.12. Use em colunas SQLAlchemy
    `DateTime` (sem `timezone=True`) que esperam datetime naive em UTC.
    """
    return datetime.now(UTC).replace(tzinfo=None)
