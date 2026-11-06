from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.model_loader import get_model_handle

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    handle = get_model_handle()
    model_ready = bool(handle and handle.ready)
    model_error = None if model_ready else (handle.error if handle else "Model not loaded")
    return HealthResponse(
        status="ok" if model_ready else "degraded",
        service="SpeechShield",
        version="0.1.0-layer0",
        application="available",
        checkpoint_loaded=model_ready,
        inference_ready=False,
        model_ready=model_ready,
        model_error=model_error,
    )


@router.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    # Readiness requires application + checkpoint + inference parity.
    # Inference parity is unverified in Layer 1, so ready is always false.
    handle = get_model_handle()
    model_ready = bool(handle and handle.ready)
    return HealthResponse(
        status="not_ready",
        service="SpeechShield",
        version="0.1.0-layer0",
        application="available",
        checkpoint_loaded=model_ready,
        inference_ready=False,
        model_ready=model_ready,
        model_error="Preprocessing parity not verified (Layer 2)",
    )
