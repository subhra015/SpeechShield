"""
SpeechShield backend – FastAPI entry point (Layer 0).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings
from app.db.session import Base, engine
from app.logging_config import configure_logging
from app.middleware import (
    CorrelationIdMiddleware,
    CSRFMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.models import audio_asset as _audio_model  # noqa: F401  (register model)
from app.models import audio_job as _audio_job_model  # noqa: F401  (register model)
from app.models import audit_log as _audit_model  # noqa: F401  (register model)
from app.models import inference_run as _inference_run_model  # noqa: F401  (register model)
from app.models import user as _user_model  # noqa: F401  (register model)
from app.routers.audio import router as audio_router
from app.routers.auth import router as auth_router
from app.routers.inference import router as inference_router
from app.routers.job import router as job_router
from app.services.model_loader import load_v4_model, set_model_handle


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    import logging

    logger = logging.getLogger("speechshield")
    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    Base.metadata.create_all(bind=engine)
    from app.db.session import ensure_schema

    ensure_schema()
    handle = load_v4_model()
    set_model_handle(handle)
    if handle.ready:
        from app.services.inference_service import verify_inference_authorization

        auth = verify_inference_authorization()
        if auth.ok:
            logger.info(
                "V4 model loaded and integrity verified; internal inference ready; production disabled"
            )
        else:
            logger.info(
                "V4 model loaded and integrity verified; internal inference blocked: %s",
                auth.reason,
            )
    else:
        logger.error("V4 model failed to load: %s", handle.error)
    yield
    set_model_handle(None)
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="SpeechShield: deepfake audio detection (Layer 0 foundation)",
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(audio_router)
app.include_router(job_router)
app.include_router(inference_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append(
            {
                "field": field,
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if settings.debug:
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error", "error": str(exc)}
        )
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred"})


app.include_router(api_router)


@app.get("/health", include_in_schema=False)
def health_root():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "layer": "Layer 10",
        "docs": "/docs",
        "health": "/health",
        "api_health": "/api/health",
        "model_info": "/api/model/info",
    }
