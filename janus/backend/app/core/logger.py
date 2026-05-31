"""
Logging do JUNO Backend.

- Desenvolvimento: texto plano legivel.
- Producao: tenta usar `structlog` (JSON estruturado). Fallback para
  formatter JSON simples se structlog nao estiver instalado.

Uso:
    from app.core.logger import get_logger
    logger = get_logger(__name__)
"""

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Any

from app.config import settings


_RESERVED_LOG_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    """Small JSON formatter with support for `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_FIELDS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def _use_json_logs() -> bool:
    if settings.LOG_FORMAT.lower() == "json":
        return True
    if settings.LOG_FORMAT.lower() == "text":
        return False
    return settings.is_production


def _try_structlog() -> bool:
    """Configura structlog para producao. Retorna True se conseguiu."""
    try:
        import structlog
    except ImportError:
        return False

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL)

    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("sqlalchemy.engine").setLevel("WARNING")
    return True


def _build_stdlib_config() -> dict:
    """Fallback: logging stdlib com formatter manual."""
    fmt_default = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    fmt_json = (
        '{"ts":"%(asctime)s","level":"%(levelname)s",' '"logger":"%(name)s","msg":"%(message)s"}'
    )
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": fmt_default, "datefmt": "%Y-%m-%d %H:%M:%S"},
            "json_simple": {"format": fmt_json, "datefmt": "%Y-%m-%dT%H:%M:%S"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "json_simple" if settings.is_production else "default",
                "level": settings.LOG_LEVEL,
            }
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console"],
        },
        "loggers": {
            "uvicorn.access": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING"},
        },
    }


_configured = False


def setup_logging() -> None:
    """Aplica a configuracao de logging. Idempotente."""
    global _configured
    if _configured:
        return
    if _use_json_logs() and settings.is_production and _try_structlog():
        pass
    else:
        logging.config.dictConfig(_build_stdlib_config())
        if _use_json_logs():
            root = logging.getLogger()
            for handler in root.handlers:
                handler.setFormatter(JsonFormatter())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Obtem logger nomeado. Configura logging se ainda nao estiver."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name)
