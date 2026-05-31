"""Handlers para pipelines de margem."""

from __future__ import annotations


def detect_critical_margins(produtos: list[dict], *, user, db) -> list[dict]:
    """Filtra produtos com margem_critica=True. Computed property ja' calculada pela ontologia."""
    return [p for p in produtos if p.get("margem_critica") is True]
