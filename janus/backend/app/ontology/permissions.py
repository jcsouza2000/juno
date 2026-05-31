"""
permissions.py - avaliacao de markings + RBAC para a ontologia.

Conceitos:
  - UserContext: snapshot do user com role + company_ids + markings_granted.
    Independe do model SQLAlchemy User para permitir testar e usar a partir
    de qualquer fonte (token JWT, mock, etc.)

  - row_level: gera filtros aplicados na query SQL (ex: WHERE company_id IN (...))

  - column_level: remove keys do dict apos serializar (ex: 'salary' some se user
    nao e' data_steward).

  - object_level: bloqueia o ObjectType inteiro (raise 403 antes da query).

Markings reconhecidas (case-sensitive, conforme _markings.yaml):
  TenantScoped, PII, ConfidencialComercial, FinanceiroConsolidado, AuditoriaSomente
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class UserContext:
    """Snapshot leve do user para uso pela ontologia."""

    user_id: int | None = None
    role: str = "user"
    company_ids: list[int] = field(default_factory=list)
    markings_granted: list[str] = field(default_factory=list)

    @classmethod
    def from_user(cls, user) -> UserContext:
        """Constroi a partir de um app.models.User. SEM consultar banco (modo legado)."""
        return cls(
            user_id=getattr(user, "id", None),
            role=getattr(user, "role", "user"),
            company_ids=[c.id for c in getattr(user, "companies", [])],
            markings_granted=["*"] if getattr(user, "role", "") == "admin" else [],
        )

    @classmethod
    def from_user_with_grants(cls, user, db) -> UserContext:
        """
        Constroi UserContext consultando user_markings com cache TTL=60s.

        Cache invalidado automaticamente em grant/revoke via
        permissions.invalidate_grant_cache(user_id).
        """
        import time as _time

        ctx = cls.from_user(user)
        if ctx.role == "admin" or ctx.user_id is None:
            return ctx

        # Cache hit?
        cached = _GRANT_CACHE.get(ctx.user_id)
        now_ts = _time.monotonic()
        if cached and (now_ts - cached[0]) < _GRANT_CACHE_TTL:
            ctx.markings_granted = list(cached[1])
            return ctx

        try:
            from datetime import datetime

            from app.models import UserMarking

            now = datetime.utcnow()
            rows = (
                db.query(UserMarking)
                .filter(UserMarking.user_id == ctx.user_id)
                .filter(UserMarking.revoked == False)  # noqa: E712
                .all()
            )
            grants = []
            for r in rows:
                if r.valid_until is not None and r.valid_until < now:
                    continue
                grants.append(r.marking)
            ctx.markings_granted = grants
            _GRANT_CACHE[ctx.user_id] = (now_ts, list(grants))
        except Exception:  # noqa: BLE001
            pass
        return ctx

    def has_marking(self, marking: str) -> bool:
        """User tem grant para a marking? Admin tem '*' que cobre tudo."""
        if "*" in self.markings_granted:
            return True
        return marking in self.markings_granted


# Cache in-memory de grants por user_id (TTL 60s). Reduz ~50x queries em alta carga.
_GRANT_CACHE: dict[int, tuple[float, list[str]]] = {}
_GRANT_CACHE_TTL = 60.0  # segundos


def invalidate_grant_cache(user_id: int | None = None) -> None:
    """Invalida cache. Chame apos grant/revoke. None = limpa tudo."""
    if user_id is None:
        _GRANT_CACHE.clear()
    else:
        _GRANT_CACHE.pop(user_id, None)


class PermissionDenied(Exception):
    """Usuario autenticado mas sem privilegios."""


def can_read(user, object_type, markings_registry=None) -> bool:
    """Pode ler este ObjectType (object-level)?"""
    if user.role == "admin":
        return True

    if markings_registry is None:
        return True

    for marking_name in object_type.spec.markings.inherit:
        marking_def = markings_registry.get(marking_name)
        if marking_def is None:
            continue
        enforcement = getattr(marking_def.enforcement, "value", marking_def.enforcement)
        if enforcement != "object_level":
            continue
        if marking_def.requires_role and user.role not in marking_def.requires_role:
            return False

    return True


def get_row_level_filter(user, object_type) -> dict[str, Any]:
    """
    Retorna filtros SQL-like a aplicar em queries de listagem.

    Hoje suporta TenantScoped traduzido para `company_id IN user.company_ids`.
    Admin nao recebe filtro.
    """
    filters: dict[str, Any] = {}

    if "TenantScoped" in object_type.spec.markings.inherit:
        if "company_id" in object_type.spec.properties:
            if user.role != "admin":
                filters["company_id__in"] = user.company_ids or [-1]

    return filters


def filter_columns(
    user, object_type, row: dict[str, Any], markings_registry=None
) -> dict[str, Any]:
    """Remove de `row` colunas cujas markings o user nao tem acesso."""
    if user.role == "admin":
        return row

    if markings_registry is None:
        return row

    out = dict(row)
    for prop_name, prop_spec in object_type.spec.properties.items():
        marking = prop_spec.marking
        if not marking:
            continue
        marking_def = markings_registry.get(marking)
        if marking_def is None:
            continue

        enforcement = getattr(marking_def.enforcement, "value", marking_def.enforcement)
        if enforcement != "column_level":
            continue

        # requires_role?
        if marking_def.requires_role and user.role not in marking_def.requires_role:
            out.pop(prop_name, None)
            continue

        # requires_marking_grant?
        if marking_def.requires_marking_grant and not user.has_marking(marking):
            out.pop(prop_name, None)
            continue

    return out


def can_execute(user, action_type, *, is_ai_actor=False, confirmed_by=None) -> bool:
    """Pode executar a Action?"""
    auth = action_type.spec.authorization

    if auth.roles and user.role not in auth.roles and user.role != "admin":
        return False

    for m in auth.require_markings:
        if not user.has_marking(m):
            return False

    if is_ai_actor and auth.require_confirmation and confirmed_by is None:
        return False

    return True


def build_markings_index(marking_sets: dict) -> dict[str, Any]:
    """Constroi indice {marking_name: MarkingDef} a partir dos MarkingSets."""
    index: dict[str, Any] = {}
    for ms in marking_sets.values():
        for name, mdef in ms.spec.markings.items():
            index[name] = mdef
    return index
