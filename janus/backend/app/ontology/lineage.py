"""
lineage.py - rastreamento de linhagem de objetos ontologicos.

Reconstroi o "historico de mudancas" de um objeto a partir da tabela
audit_logs. Cada Action grava um row com:
  - action: nome
  - resource_type: ObjectType
  - new_values (JSON): target_id, before, after, diff, actor_type,
                    confirmed_by, dry_run, status, warnings

Endpoint GET /api/v1/ontology/lineage/{type}/{id} agrega tudo num timeline.

Roadmap:
  - Sem6: timeline simples por (type, id)
  - Sem7+: derived_from cross-objects (ex: pedido.aplicarDesconto referenciou
    produto X) — requer adicionar `derived_from` em audit details
"""

from __future__ import annotations

import json
from typing import Any


def get_lineage(
    object_type: str,
    object_id: int,
    *,
    db,
    user,
    limit: int = 100,
    registry=None,
) -> dict[str, Any]:
    """
    Retorna timeline de Actions executadas sobre (object_type, object_id).

    Aplica TenantScoped: se o user nao tem acesso ao objeto, devolve lista vazia
    (nao vaza nem a existencia).
    """
    from app.models import AuditLog

    from .registry import registry as _default_registry
    from .runtime import _load_row

    reg = registry or _default_registry

    # Verifica acesso ao objeto (sem retornar 404 — apenas vazio)
    try:
        obj_spec = reg.get_object_type(object_type)
    except KeyError:
        return {"object_type": object_type, "object_id": object_id, "events": [], "total": 0}

    row = _load_row(obj_spec, object_id, user=user, db=db)
    if row is None:
        return {"object_type": object_type, "object_id": object_id, "events": [], "total": 0}

    # Busca audit_logs filtrando por resource_type E new_values.target_id
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == object_type)
        .order_by(AuditLog.created_at.desc())
        .limit(limit * 5)  # buffer pra filtrar por target_id em python
        .all()
    )

    events: list[dict[str, Any]] = []
    for r in rows:
        details: dict[str, Any] = {}
        if r.new_values:
            try:
                details = json.loads(r.new_values)
            except (json.JSONDecodeError, TypeError):
                continue
        if details.get("target_id") != object_id:
            continue

        events.append(
            {
                "audit_id": r.id,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
                "action": r.action,
                "actor": {
                    "user_id": r.user_id,
                    "actor_type": details.get("actor_type", "user"),
                    "confirmed_by": details.get("confirmed_by"),
                },
                "status": details.get("status", "committed"),
                "diff": details.get("diff", {}),
                "inputs": details.get("inputs", {}),
                "extra_context": details.get("extra_context", {}),
                "warnings": details.get("warnings", []),
                "dry_run": details.get("dry_run", False),
            }
        )
        if len(events) >= limit:
            break

    return {
        "object_type": object_type,
        "object_id": object_id,
        "total": len(events),
        "events": events,
    }
