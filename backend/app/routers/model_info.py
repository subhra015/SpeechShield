from fastapi import APIRouter, HTTPException

from app.ml import reference_validation
from app.schemas.model_info import ModelInfoResponse
from app.services.inference_service import get_inference_status_code
from app.services.model_loader import get_model_handle

router = APIRouter(tags=["model"])


@router.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    handle = get_model_handle()
    if handle is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    cfg = handle.config or {}
    inference_status = get_inference_status_code()
    inference_ready = inference_status == "INTERNAL_INFERENCE_READY"

    checkpoint_sha = handle.checkpoint_sha256
    expected_sha = handle.expected_sha256

    sha256_verified = bool(
        checkpoint_sha and expected_sha and checkpoint_sha.lower() == expected_sha.lower()
    )

    return ModelInfoResponse(
        model_version=cfg.get("model_version", "V4"),
        architecture=cfg.get("model_architecture", "CompactCNN"),
        checkpoint_sha256=checkpoint_sha,
        expected_sha256=expected_sha,
        sha256_verified=sha256_verified,
        parameter_count=handle.parameter_count,
        device=handle.device,
        threshold=cfg.get("classification_threshold"),
        classification_threshold=cfg.get("classification_threshold"),
        uncertain_confidence_threshold=cfg.get("uncertain_confidence_threshold"),
        target_sample_rate=cfg.get("target_sample_rate"),
        target_length_seconds=cfg.get("target_length_seconds"),
        n_mels=cfg.get("n_mels"),
        inference_status=inference_status,
        preprocessing_parity_verified=(reference_validation.PREPROCESSING_PARITY_VERIFIED),
        inference_ready=inference_ready,
        # Internal readiness does not imply production readiness.
        inference_production_ready=False,
        notes=(
            f"Internal inference status: {inference_status}. "
            "No public prediction endpoint is exposed. "
            "Production readiness remains disabled."
        ),
    )
