"""
metrics.py - metricas Prometheus do Ontology Engine.

Coleta:
  - juno_ontology_calls_total{op, type, status}     - contador de chamadas
  - juno_ontology_call_seconds{op, type}            - histograma de latencia
  - juno_ontology_action_calls_total{action, status, dry_run}
  - juno_ontology_action_seconds{action, dry_run}

`op` ∈ {fetch_by_id, list_objects, search_objects, resolve_link, dispatch_tool, execute_action}
`status` ∈ {ok, not_found, denied, validation_failed, error}

Se prometheus_client nao estiver disponivel (modo dev minimo), os helpers
viram no-op silencioso.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:
    from prometheus_client import Counter, Histogram

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False


# Buckets em segundos (latencia tipica: 5ms-2s)
_LAT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


if _PROM_AVAILABLE:
    CALLS: Any = Counter(
        "juno_ontology_calls_total",
        "Chamadas ao runtime/dispatcher da ontologia",
        ["op", "type", "status"],
    )
    CALL_SECONDS: Any = Histogram(
        "juno_ontology_call_seconds",
        "Latencia de chamadas ao runtime da ontologia",
        ["op", "type"],
        buckets=_LAT_BUCKETS,
    )
    ACTION_CALLS: Any = Counter(
        "juno_ontology_action_calls_total",
        "Execucoes de Actions",
        ["action", "status", "dry_run"],
    )
    ACTION_SECONDS: Any = Histogram(
        "juno_ontology_action_seconds",
        "Latencia de execucao de Actions",
        ["action", "dry_run"],
        buckets=_LAT_BUCKETS,
    )
else:

    class _NoOp:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    CALLS = _NoOp()
    ACTION_CALLS = CALLS
    CALL_SECONDS = _NoOp()
    ACTION_SECONDS = CALL_SECONDS


# =============================================================================
# Helpers
# =============================================================================


def _status_from_exception(exc: BaseException) -> str:
    from .permissions import PermissionDenied
    from .runtime import ObjectNotFound, ValidationFailed

    if isinstance(exc, ObjectNotFound):
        return "not_found"
    if isinstance(exc, PermissionDenied):
        return "denied"
    if isinstance(exc, ValidationFailed):
        return "validation_failed"
    if isinstance(exc, KeyError):
        return "not_found"
    return "error"


@contextmanager
def time_call(op: str, type_name: str) -> Iterator[None]:
    """
    Cronometra uma operacao de leitura. Status e' derivado da exception
    (ou 'ok' se nenhuma). Re-levanta a exception.
    """
    start = time.monotonic()
    status = "ok"
    try:
        yield
    except BaseException as e:
        status = _status_from_exception(e)
        raise
    finally:
        elapsed = time.monotonic() - start
        CALLS.labels(op=op, type=type_name or "unknown", status=status).inc()
        CALL_SECONDS.labels(op=op, type=type_name or "unknown").observe(elapsed)


@contextmanager
def time_action(action_name: str, dry_run: bool) -> Iterator[None]:
    start = time.monotonic()
    status = "ok"
    dry_label = "true" if dry_run else "false"
    try:
        yield
    except BaseException as e:
        status = _status_from_exception(e)
        raise
    finally:
        elapsed = time.monotonic() - start
        ACTION_CALLS.labels(action=action_name, status=status, dry_run=dry_label).inc()
        ACTION_SECONDS.labels(action=action_name, dry_run=dry_label).observe(elapsed)
