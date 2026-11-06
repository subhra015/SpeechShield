"""Inference service (Layer 2).

Inference is intentionally BLOCKED until preprocessing parity is verified.
This service exposes a safe not-ready result and never runs the model on
unverified features.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ml.reference_validation import PREPROCESSING_PARITY_VERIFIED
from app.services.model_loader import get_model_handle


@dataclass
class InferenceResult:
    ready: bool
    inference_ready: bool
    message: str
    spoof_probability: float | None = None
    label: str | None = None


def run_inference(_audio_path: str) -> InferenceResult:
    handle = get_model_handle()
    model_ok = bool(handle and handle.ready)
    if not (model_ok and PREPROCESSING_PARITY_VERIFIED):
        return InferenceResult(
            ready=model_ok,
            inference_ready=False,
            message="Inference blocked: preprocessing parity not verified (Layer 2).",
        )
    # Intentionally unreachable until parity is verified.
    raise RuntimeError("Inference path not enabled")


def is_inference_ready() -> bool:
    handle = get_model_handle()
    return bool(handle and handle.ready and PREPROCESSING_PARITY_VERIFIED)
