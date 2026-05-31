"""Testes do Pipeline declarativo."""

from __future__ import annotations

import pytest

from app.ontology import pipeline as pl


def test_load_pipelines():
    pipes = pl.load_pipelines()
    assert "daily_margin_recompute" in pipes
    spec = pipes["daily_margin_recompute"].spec
    assert len(spec.steps) == 2
    assert spec.steps[0].type == "read"
    assert spec.steps[0].object_type == "Produto"


def test_run_pipeline_happy(db_session, loaded_registry, admin_user_ctx, seed_data):
    result = pl.run_pipeline(
        "daily_margin_recompute",
        user=admin_user_ctx,
        db=db_session,
        registry=loaded_registry,
    )
    assert result.status == "ok"
    assert result.error is None
    assert len(result.steps) == 2
    assert result.steps[0]["count"] >= 1
    assert result.lineage_id is not None


def test_run_pipeline_unknown_raises(db_session, loaded_registry, admin_user_ctx):
    with pytest.raises(KeyError):
        pl.run_pipeline("nao_existe", user=admin_user_ctx, db=db_session, registry=loaded_registry)


def test_lineage_returns_history(db_session, loaded_registry, admin_user_ctx, seed_data):
    pl.run_pipeline(
        "daily_margin_recompute", user=admin_user_ctx, db=db_session, registry=loaded_registry
    )
    pl.run_pipeline(
        "daily_margin_recompute", user=admin_user_ctx, db=db_session, registry=loaded_registry
    )
    hist = pl.get_lineage_for_pipeline("daily_margin_recompute", db=db_session)
    assert len(hist) >= 2
    # mais recente primeiro
    assert hist[0]["status"] == "ok"
    assert "Produto" in hist[0]["object_types_touched"]
