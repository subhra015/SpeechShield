"""Internal V4 inference service.

Inference is blocked until preprocessing parity is explicitly authorized and
the validated CUDA preprocessing runtime is available.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from app.ml import reference_validation
from app.ml.preprocessor import (
    MEL_TRANSFORM,
    PREPROCESSING_DEVICE,
    TEMPERATURE,
    THRESHOLD,
    extract_features,
)
from app.services.model_loader import get_model_handle


@dataclass
class InferenceResult:
    ready: bool
    inference_ready: bool
    message: str
    logit: float | None = None
    spoof_probability: float | None = None
    threshold: float | None = None
    predicted_class: int | None = None


def _cuda_preprocessing_ready() -> bool:
    """Confirm that the actual preprocessing transform is using CUDA."""
    if PREPROCESSING_DEVICE.type != "cuda" or not torch.cuda.is_available():
        return False

    buffers = tuple(MEL_TRANSFORM.buffers())

    return bool(buffers) and all(buffer.device.type == "cuda" for buffer in buffers)


def _readiness_check(handle) -> tuple[str | None, str | None]:
    """Return a blocking status code and message, or (None, None)."""
    if handle is None or not handle.ready or handle.model is None:
        return "MODEL_NOT_READY", "Inference blocked: model is not loaded."

    if getattr(handle.model, "training", False):
        return (
            "BLOCKED_MODEL_EVALUATION_MODE",
            "Inference blocked: model is not in evaluation mode.",
        )

    if not reference_validation.PREPROCESSING_PARITY_VERIFIED:
        return (
            "BLOCKED_PREPROCESSING_PARITY",
            "Inference blocked: preprocessing parity has not been explicitly authorized.",
        )

    if not _cuda_preprocessing_ready():
        return (
            "BLOCKED_VALIDATED_PREPROCESSING_RUNTIME",
            "Inference blocked: validated CUDA preprocessing is unavailable. "
            "Configure PREPROCESSING_DEVICE=cuda and restart the backend.",
        )

    return None, None


def get_inference_status_code() -> str:
    """Return the current internal inference readiness status."""
    handle = get_model_handle()
    code, _ = _readiness_check(handle)
    return code or "INTERNAL_INFERENCE_READY"


def run_inference(audio_path: str) -> InferenceResult:
    """Public service entry point. The core enforces all readiness checks."""
    return run_inference_core(audio_path)


def run_inference_core(audio_path: str) -> InferenceResult:
    """Run internal inference only after all safety checks pass."""
    handle = get_model_handle()
    code, message = _readiness_check(handle)

    if code is not None:
        model_ok = bool(handle and handle.ready and handle.model is not None)
        return InferenceResult(
            ready=model_ok,
            inference_ready=False,
            message=message or "Inference blocked.",
            threshold=THRESHOLD,
        )

    feat = extract_features(audio_path)
    model_input = feat["model_input"]

    with torch.inference_mode():
        logit = handle.model(model_input).reshape(-1)
        prob = torch.sigmoid(logit / TEMPERATURE)

    logit_v = float(logit.item())
    prob_v = float(prob.item())
    predicted = int(prob_v >= THRESHOLD)

    return InferenceResult(
        ready=True,
        inference_ready=True,
        message="ok",
        logit=logit_v,
        spoof_probability=prob_v,
        threshold=THRESHOLD,
        predicted_class=predicted,
    )


def is_inference_ready() -> bool:
    return get_inference_status_code() == "INTERNAL_INFERENCE_READY"
