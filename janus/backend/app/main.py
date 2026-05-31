"""
JUNO Industrial Diagnostic API -- entrypoint FastAPI.
Configuracao 100% via env vars (ver app.config.Settings).
"""

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.core.logger import get_logger, setup_logging
from app.database import engine
from app.models import Base as ModelsBase

setup_logging()
logger = get_logger(__name__)

# SEGURANCA (C2): bypass de autenticacao so' pode existir em desenvolvimento.
# Aqui apenas tornamos o estado VISIVEL no startup — nunca silencioso. A logica
# de fato esta em app.auth.dev_auth_bypass_enabled() (exige is_development).
from app.auth import dev_auth_bypass_enabled  # noqa: E402

if dev_auth_bypass_enabled():
    logger.warning(
        "ATENCAO: JUNO_DEV_AUTH_BYPASS ATIVO — login desligado (modo dev). "
        "NUNCA use em staging/producao. Defina JUNO_ENV=production e "
        "JUNO_DEV_AUTH_BYPASS=false antes de expor a API."
    )
elif not settings.is_production and settings.JUNO_DEV_AUTH_BYPASS:
    logger.info("Bypass de auth configurado, porem inativo (JUNO_ENV != development).")

# create_all so' em dev. Em prod, schema e' gerenciado por Alembic exclusivamente.
if not settings.is_production:
    ModelsBase.metadata.create_all(bind=engine)
else:
    logger.info("Producao: schema gerenciado por Alembic (create_all desligado).")

app = FastAPI(
    title="JUNO Industrial Diagnostic API",
    description="API de diagnostico industrial com IA local",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS — mais restritivo em prod
if settings.is_production:
    _cors_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    _cors_headers = ["Authorization", "Content-Type", "Accept", "X-Requested-With"]
else:
    _cors_methods = ["*"]
    _cors_headers = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=_cors_methods,
    allow_headers=_cors_headers,
)

# Rate limiter (slowapi)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": "Muitas requisicoes. Tente novamente em instantes.",
        },
    )


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    logger.info(
        "http_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(elapsed_ms, 2),
            "client_ip": request.client.host if request.client else None,
        },
    )
    return response


# Routers core (sempre incluido)
from app.routers import auth  # noqa: E402

app.include_router(auth.router)


def _try_include(import_path: str, attr: str = "router") -> bool:
    """Inclui router opcional; graceful se faltar dependencia."""
    try:
        module = __import__(import_path, fromlist=[attr])
        app.include_router(getattr(module, attr))
        logger.info(f"Router incluido: {import_path}")
        return True
    except ImportError as e:
        logger.warning(f"Router {import_path} pulado (dep faltando): {e}")
        return False
    except Exception as e:
        logger.error(f"Router {import_path} falhou ao carregar: {e}", exc_info=True)
        return False


# Routers opcionais
_try_include("app.api.erp")
_try_include("app.api.health")
_try_include("app.routers.audit")
_try_include("app.routers.events")
_try_include("app.routers.tenant")
_try_include("app.routers.score")
_try_include("app.routers.kpis")
_try_include("app.routers.dashboard")
_try_include("app.routers.pdf")
_try_include("app.routers.pdf", "legacy_router")
_try_include("app.routers.demo")
_try_include("app.routers.financials")
_try_include("app.routers.integrations")
_try_include("app.routers.chat")
_try_include("app.api.ai")
_try_include("app.routers.coordinator")
_try_include("app.api.reports")
_try_include("app.api.security")
_try_include("app.routers.ml")


# =====================================================================
# Ontology Engine (v0.2.0-dev) — atras de feature flag ONTOLOGY_ENABLED.
# Carrega definitions/, valida consistencia e inclui o router /api/v1/ontology.
# Em modo STRICT, inconsistencia derruba o app (apropriado em producao).
# =====================================================================
if settings.ONTOLOGY_ENABLED:
    try:
        from app.ontology import registry as _onto_registry
        from app.ontology.loader import load_all as _onto_load

        _onto_load(_onto_registry)
        _errors = _onto_registry.validate_consistency(check_models=False)
        if _errors:
            for _e in _errors:
                logger.warning("ontology consistency: %s", _e)
            if settings.ONTOLOGY_STRICT:
                raise RuntimeError(
                    f"Ontology consistency failed ({len(_errors)} erros) e ONTOLOGY_STRICT=true"
                )
        else:
            logger.info(
                "ontology: %d ObjectTypes, %d ActionTypes carregados",
                len(_onto_registry.list_object_types()),
                len(_onto_registry.list_action_types()),
            )
        _try_include("app.ontology.api")
        _try_include("app.ontology.markings_api")
    except RuntimeError:
        raise  # strict mode falha startup
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao carregar ontology engine: %s", e, exc_info=True)
        if settings.ONTOLOGY_STRICT:
            raise


# Audit retention job (semanal). Controlado por AUDIT_RETENTION_ENABLED.
try:
    from app.services.audit_retention_job import start_audit_retention_scheduler

    start_audit_retention_scheduler()
except Exception as _e:  # noqa: BLE001
    logger.warning("audit_retention scheduler nao iniciado: %s", _e)


@app.get("/health", tags=["Sistema"])
def health_check():
    return {
        "status": "online",
        "version": settings.APP_VERSION,
        "environment": settings.JUNO_ENV,
        "features": {"auth": True, "database": True, "rate_limit": True},
    }


@app.get("/", tags=["Sistema"])
def root():
    return {
        "message": "JUNO Industrial Diagnostic API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if not settings.is_production else "disabled",
    }


@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    logger.exception(f"Erro nao-tratado em {request.method} {request.url.path}: {exc}")
    detail = str(exc) if settings.is_development else "Erro interno do servidor"
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": detail},
    )


logger.info(f"JUNO API iniciada (env={settings.JUNO_ENV}, origins={settings.cors_origins})")
