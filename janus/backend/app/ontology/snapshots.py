"""
snapshots.py - time-travel de Object Types.

API basica:
  create_snapshot(name, object_type, user, db, registry, company_id=None) -> dict
  list_snapshots(db, object_type=None) -> list[dict]
  fetch_at(snapshot_id, object_id, db) -> dict | None
  list_at(snapshot_id, db) -> list[dict]
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from . import runtime as _rt
from .permissions import UserContext


class SnapshotError(Exception):
    """Erro de operacao em snapshots."""


def create_snapshot(
    name: str,
    object_type: str,
    *,
    user: UserContext,
    db,
    registry,
    description: str | None = None,
    company_id: int | None = None,
) -> dict[str, Any]:
    """Tira snapshot do estado atual do ObjectType. Aplica markings do user."""
    from app.models import DatasetSnapshot

    if not name or len(name) > 255:
        raise SnapshotError("name invalido")

    filters = {}
    if company_id is not None:
        filters["company_id"] = company_id

    res = _rt.list_objects(
        object_type,
        user=user,
        db=db,
        registry=registry,
        filters=filters,
        limit=100000,
    )
    items = res["items"]

    snap = DatasetSnapshot(
        name=name,
        description=description,
        object_type=object_type,
        company_id=company_id,
        created_by=user.user_id or 0,
        created_at=datetime.utcnow(),
        row_count=len(items),
        payload=json.dumps(items, default=str, ensure_ascii=False),
    )
    db.add(snap)
    db.commit()
    return _serialize(snap, include_payload=False)


def list_snapshots(
    db,
    *,
    object_type: str | None = None,
    company_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    from app.models import DatasetSnapshot

    q = db.query(DatasetSnapshot)
    if object_type:
        q = q.filter(DatasetSnapshot.object_type == object_type)
    if company_id is not None:
        q = q.filter(DatasetSnapshot.company_id == company_id)
    q = q.order_by(DatasetSnapshot.id.desc()).limit(limit)
    return [_serialize(r, include_payload=False) for r in q.all()]


def _load_snapshot_items(snapshot_id: int, db) -> tuple[Any, list[dict]]:
    from app.models import DatasetSnapshot

    snap = db.query(DatasetSnapshot).filter(DatasetSnapshot.id == snapshot_id).first()
    if snap is None:
        raise SnapshotError(f"snapshot {snapshot_id} nao existe")
    try:
        items = json.loads(snap.payload)
    except (json.JSONDecodeError, TypeError):
        items = []
    return snap, items


def fetch_at(snapshot_id: int, object_id: int, *, db) -> dict[str, Any] | None:
    """Estado do objeto no momento do snapshot. None se nao estava la'."""
    _, items = _load_snapshot_items(snapshot_id, db)
    for it in items:
        if it.get("id") == object_id:
            return it
    return None


def list_at(snapshot_id: int, *, db, limit: int = 200) -> dict[str, Any]:
    """Lista os objetos contidos no snapshot."""
    snap, items = _load_snapshot_items(snapshot_id, db)
    return {
        "snapshot": _serialize(snap, include_payload=False),
        "items": items[:limit],
        "total": len(items),
    }


def diff_snapshots(snap_a_id: int, snap_b_id: int, *, db) -> dict[str, Any]:
    """
    Diff entre dois snapshots do mesmo ObjectType. Retorna:
      {added: [ids], removed: [ids], changed: {id: {field: {before, after}}}}
    """
    snap_a, items_a = _load_snapshot_items(snap_a_id, db)
    snap_b, items_b = _load_snapshot_items(snap_b_id, db)
    if snap_a.object_type != snap_b.object_type:
        raise SnapshotError("snapshots de ObjectTypes diferentes")

    by_id_a = {it["id"]: it for it in items_a if isinstance(it.get("id"), int)}
    by_id_b = {it["id"]: it for it in items_b if isinstance(it.get("id"), int)}

    added = sorted(set(by_id_b.keys()) - set(by_id_a.keys()))
    removed = sorted(set(by_id_a.keys()) - set(by_id_b.keys()))
    changed: dict[int, dict[str, dict[str, Any]]] = {}
    for oid in sorted(set(by_id_a) & set(by_id_b)):
        a, b = by_id_a[oid], by_id_b[oid]
        field_diffs: dict[str, dict[str, Any]] = {}
        for k in set(a) | set(b):
            if a.get(k) != b.get(k):
                field_diffs[k] = {"before": a.get(k), "after": b.get(k)}
        if field_diffs:
            changed[oid] = field_diffs

    return {
        "object_type": snap_a.object_type,
        "snapshot_a": _serialize(snap_a, include_payload=False),
        "snapshot_b": _serialize(snap_b, include_payload=False),
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed)},
    }


def _serialize(snap, *, include_payload=False) -> dict[str, Any]:
    out = {
        "id": snap.id,
        "name": snap.name,
        "description": snap.description,
        "object_type": snap.object_type,
        "company_id": snap.company_id,
        "created_by": snap.created_by,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
        "row_count": snap.row_count,
    }
    if include_payload:
        try:
            out["items"] = json.loads(snap.payload) if snap.payload else []
        except (json.JSONDecodeError, TypeError):
            out["items"] = []
    return out
