"""
pipeline.py - DAG declarativo de transformacoes sobre Object Types.

Permite declarar em YAML uma serie de steps (read + transform + write)
que rodam em ordem topologica e gravam lineage cross-objects em audit_logs.

Spec YAML:

  apiVersion: ontology.juno.gravithy.com.br/v1
  kind: Pipeline
  metadata:
    name: daily_margin_recompute
    description: ...
  spec:
    schedule: "0 4 * * *"          # opcional, cron
    steps:
      - name: load_produtos
        type: read
        object_type: Produto
        filters: { company_id: 1 }
        outputs: produtos              # variavel para steps seguintes
      - name: compute_alerts
        type: transform
        handler: app.ontology.pipelines.margin.alert_critical
        inputs: [produtos]
        outputs: alerts
      - name: emit_audit
        type: write
        action: ...                    # ou handler custom
        from: alerts

Runtime:
  PipelineRunner.run(pipeline_name, user, db, registry) -> dict
"""

from __future__ import annotations

import importlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import runtime as _rt
from .permissions import UserContext

logger = logging.getLogger(__name__)

PIPELINES_DIR = Path(__file__).parent / "pipelines"


# =============================================================================
# Schema
# =============================================================================


class PipelineStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str  # 'read' | 'transform' | 'write'
    object_type: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    handler: str | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: str | None = None
    limit: int = 1000


class PipelineMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)


class PipelineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule: str | None = None
    steps: list[PipelineStep]


class PipelineDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apiVersion: str = "ontology.juno.gravithy.com.br/v1"
    kind: str = "Pipeline"
    metadata: PipelineMetadata
    spec: PipelineSpec


# =============================================================================
# Loader
# =============================================================================


def load_pipelines(directory: Path | None = None) -> dict[str, PipelineDef]:
    """Carrega todos os YAMLs de pipelines/."""
    d = directory or PIPELINES_DIR
    out: dict[str, PipelineDef] = {}
    if not d.exists():
        return out
    for f in sorted(d.glob("*.yaml")):
        raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        if raw is None:
            continue
        pipe = PipelineDef.model_validate(raw)
        out[pipe.metadata.name] = pipe
    return out


# =============================================================================
# Runner
# =============================================================================


class PipelineResult:
    def __init__(
        self,
        *,
        pipeline: str,
        started_at: datetime,
        ended_at: datetime,
        steps: list[dict],
        lineage_id: int | None = None,
        status: str = "ok",
        error: str | None = None,
    ):
        self.pipeline = pipeline
        self.started_at = started_at
        self.ended_at = ended_at
        self.steps = steps
        self.lineage_id = lineage_id
        self.status = status
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline": self.pipeline,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "duration_ms": int((self.ended_at - self.started_at).total_seconds() * 1000),
            "steps": self.steps,
            "lineage_id": self.lineage_id,
            "status": self.status,
            "error": self.error,
        }


def _resolve_handler(dotted: str):
    module_path, _, fn_name = dotted.rpartition(".")
    return getattr(importlib.import_module(module_path), fn_name)


def run_pipeline(
    pipeline_name: str,
    *,
    user: UserContext,
    db,
    registry,
    pipelines: dict[str, PipelineDef] | None = None,
) -> PipelineResult:
    """
    Executa pipeline em ordem topologica simples (steps na ordem declarada).
    Grava lineage em audit_logs com action='pipeline_run:<name>'.
    """
    pipes = pipelines if pipelines is not None else load_pipelines()
    if pipeline_name not in pipes:
        raise KeyError(f"Pipeline '{pipeline_name}' nao encontrado")

    pipe = pipes[pipeline_name]
    started = datetime.utcnow()
    bag: dict[str, Any] = {}
    step_results: list[dict] = []
    error: str | None = None

    try:
        for step in pipe.spec.steps:
            t0 = datetime.utcnow()
            if step.type == "read":
                if not step.object_type:
                    raise ValueError(f"step '{step.name}': read exige object_type")
                res = _rt.list_objects(
                    step.object_type,
                    user=user,
                    db=db,
                    registry=registry,
                    filters=step.filters,
                    limit=step.limit,
                )
                value = res["items"]
                count = len(value)
            elif step.type == "transform":
                if not step.handler:
                    raise ValueError(f"step '{step.name}': transform exige handler")
                fn = _resolve_handler(step.handler)
                args = [bag.get(i) for i in step.inputs]
                value = fn(*args, user=user, db=db)
                count = len(value) if hasattr(value, "__len__") else 1
            elif step.type == "write":
                if not step.handler:
                    raise ValueError(f"step '{step.name}': write exige handler")
                fn = _resolve_handler(step.handler)
                args = [bag.get(i) for i in step.inputs]
                value = fn(*args, user=user, db=db)
                count = len(value) if hasattr(value, "__len__") else 1
            else:
                raise ValueError(f"step '{step.name}': type='{step.type}' invalido")

            if step.outputs:
                bag[step.outputs] = value

            step_results.append(
                {
                    "name": step.name,
                    "type": step.type,
                    "count": count,
                    "duration_ms": int((datetime.utcnow() - t0).total_seconds() * 1000),
                }
            )
    except Exception as e:  # noqa: BLE001
        error = str(e)
        logger.exception("pipeline %s falhou", pipeline_name)

    ended = datetime.utcnow()
    status = "failed" if error else "ok"

    # Grava lineage entry em audit_logs
    lineage_id = _write_lineage(db, user, pipe, step_results, status, error, started, ended)

    return PipelineResult(
        pipeline=pipeline_name,
        started_at=started,
        ended_at=ended,
        steps=step_results,
        lineage_id=lineage_id,
        status=status,
        error=error,
    )


def _write_lineage(db, user, pipe, step_results, status, error, started, ended) -> int | None:
    try:
        from app.models import AuditLog

        details = {
            "pipeline": pipe.metadata.name,
            "steps": step_results,
            "status": status,
            "error": error,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            # Lineage: lista os ObjectTypes tocados (cross-objects)
            "object_types_touched": sorted(
                {s.object_type for s in pipe.spec.steps if s.object_type}
            ),
        }
        row = AuditLog(
            company_id=user.company_ids[0] if getattr(user, "company_ids", None) else None,
            user_id=getattr(user, "user_id", None),
            action=f"pipeline_run:{pipe.metadata.name}",
            resource_type="pipelines",
            new_values=json.dumps(details, default=str, ensure_ascii=False),
            success=status == "ok",
            severity="info" if status == "ok" else "warning",
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        return None


def get_lineage_for_pipeline(pipeline_name: str, *, db, limit: int = 20) -> list[dict]:
    """Lista as ultimas N execucoes do pipeline (timeline)."""
    from app.models import AuditLog

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.action == f"pipeline_run:{pipeline_name}")
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        try:
            details = json.loads(r.details) if r.details else {}
        except (json.JSONDecodeError, TypeError):
            details = {}
        out.append(
            {
                "audit_id": r.id,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
                "status": details.get("status"),
                "duration_ms": details.get("duration_ms"),
                "object_types_touched": details.get("object_types_touched", []),
                "steps": details.get("steps", []),
            }
        )
    return out
