"""Lightweight API contracts for critical metrics.

These schemas are intentionally small: enough to freeze pilot-facing payloads
without introducing enterprise API governance before the first customer pilot.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class CeoDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receita_total: float
    receita_liquida: float
    score_juno: float


class CfoMarginItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    receita_liquida: float
    custo_real: float
    margem: float


class CooDelayedOrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    product: str
    planned_date: str | None
    actual_date: str | None
    status: str


class InsightItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    impact: str
    action: str


class ScoreComponentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    weight: float
    raw_value: float
    normalized_score: float
    weighted_score: float
    details: dict[str, Any]


class ScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int
    company_name: str
    overall_score: float
    trend: str
    trend_delta: float
    calculation_date: str
    components: list[ScoreComponentResponse]
    recommendations: list[str]
