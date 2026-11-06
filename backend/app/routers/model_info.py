from fastapi import APIRouter, HTTPException

from app.schemas.model_info import ModelInfoResponse
from app.services.model_loader import get_model_handle

router = APIRouter(tags=["model"])


@router.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    handle = get_model_handle()
    if handle is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    cfg = handle.config or {}
    return ModelInfoResponse(
        model_version=cfg.get("model_version", "V4"),
        architecture=cfg.get("model_architecture", "CompactCNN"),
        checkpoint_sha256=handle.checkpoint_sha256,
        expected_sha256=handle.expected_sha256,
        sha256_verified=bool(
            handle.checkpoint_sha256
            and handle.expected_sha256
            and handle.checkpoint_sha256.lower() == handle.expected_sha256.lower()
        ),
        parameter_count=handle.parameter_count,
        device=handle.device,
        threshold=cfg.get("classification_threshold"),
        classification_threshold=cfg.get("classification_threshold"),
        uncertain_confidence_threshold=cfg.get("uncertain_confidence_threshold"),
        target_sample_rate=cfg.get("target_sample_rate"),
        target_length_seconds=cfg.get("target_length_seconds"),
        n_mels=cfg.get("n_mels"),
        inference_status=handle.inference_status,
        inference_production_ready=False,
    )
