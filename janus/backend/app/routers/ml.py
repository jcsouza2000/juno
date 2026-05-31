"""
Router ML do JUNO.

VersÃ£o hardening:
- NÃ£o conecta ao MLflow durante import/startup.
- SÃ³ usa MLflow quando endpoint especÃ­fico for chamado.
- Permite desativar MLflow via JUNO_ENABLE_MLFLOW=0.
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ml", tags=["ML"])


def _mlflow_enabled() -> bool:
    return os.getenv("JUNO_ENABLE_MLFLOW", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _get_mlflow():
    if not _mlflow_enabled():
        raise HTTPException(
            status_code=503,
            detail="MLflow desativado. Defina JUNO_ENABLE_MLFLOW=1 para ativar.",
        )

    try:
        import mlflow

        return mlflow
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MLflow indisponÃ­vel: {exc}",
        )


@router.get("/status")
def ml_status() -> dict[str, Any]:
    return {
        "enabled": _mlflow_enabled(),
        "service": "mlflow",
        "tracking_uri": os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
    }


@router.post("/experiment/{experiment_name}")
def set_experiment(experiment_name: str) -> dict[str, Any]:
    mlflow = _get_mlflow()

    try:
        mlflow.set_experiment(experiment_name)
        return {
            "status": "ok",
            "experiment": experiment_name,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao configurar experimento MLflow: {exc}",
        )


@router.get("/health")
def ml_health() -> dict[str, Any]:
    if not _mlflow_enabled():
        return {
            "status": "disabled",
            "message": "MLflow desativado por configuraÃ§Ã£o.",
        }

    mlflow = _get_mlflow()

    try:
        client = mlflow.tracking.MlflowClient()
        experiments = client.search_experiments()
        return {
            "status": "ok",
            "experiments_count": len(experiments),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "error": str(exc),
        }
