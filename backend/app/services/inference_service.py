"""Inference service (Layer 8) — controlled, gated behind parity authorization."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from app.config import settings
from app.ml import reference_validation as _rv
from app.ml.preprocessor import THRESHOLD, extract_features
from app.services.model_loader import get_model_handle

CHECKPOINT_SHA = "40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda"
MODEL_ID = "V4"
EXPECTED_SHAPE = (1, 1, 64, 401)
EXPECTED_DTYPE = "torch.float32"


@dataclass
class AuthorizationResult:
    ok: bool
    reason: str | None = None


def verify_inference_authorization() -> AuthorizationResult:
    handle = get_model_handle()
    if handle is None or not handle.ready or handle.model is None:
        return AuthorizationResult(False, "model_not_loaded")
    if handle.config.get("model_architecture") != "CompactCNN":
        return AuthorizationResult(False, "wrong_architecture")
    if handle.parameter_count != 97761:
        return AuthorizationResult(False, "wrong_parameter_count")
    if handle.model.training:
        return AuthorizationResult(False, "model_not_in_eval_mode")
    # gradients disabled
    for p in handle.model.parameters():
        if p.requires_grad:
            return AuthorizationResult(False, "gradients_enabled")
    if not _rv.PREPROCESSING_PARITY_VERIFIED:
        return AuthorizationResult(False, "preprocessing_parity_not_verified")
    if getattr(settings, "preprocessing_device", "cpu") != "cuda":
        return AuthorizationResult(False, "preprocessing_device_not_cuda")
    try:
        import torch as _t

        if not _t.cuda.is_available():
            return AuthorizationResult(False, "cuda_unavailable")
    except Exception:  # noqa: BLE001
        return AuthorizationResult(False, "cuda_check_failed")
    # mel transform must be on cuda
    try:
        from app.ml.preprocessor import MEL_TRANSFORM

        dev = MEL_TRANSFORM.mel_scale.fb.device
        if dev.type != "cuda":
            return AuthorizationResult(False, "mel_transform_not_on_cuda")
    except Exception:  # noqa: BLE001
        return AuthorizationResult(False, "mel_transform_check_failed")
    if handle.checkpoint_sha256.lower() != CHECKPOINT_SHA.lower():
        return AuthorizationResult(False, "checkpoint_sha_mismatch")
    if abs(float(handle.config.get("classification_threshold", 0)) - 0.39499999999999996) > 1e-12:
        return AuthorizationResult(False, "threshold_mismatch")
    if abs(float(handle.config.get("temperature", 0)) - 1.0) > 1e-12:
        return AuthorizationResult(False, "temperature_mismatch")
    return AuthorizationResult(True, None)


@dataclass
class InferenceResult:
    ready: bool
    inference_ready: bool
    blocked: bool
    message: str
    logit: float | None = None
    spoof_probability: float | None = None
    threshold: float | None = None
    predicted_class: int | None = None
    model_id: str = MODEL_ID
    checkpoint_sha256: str = CHECKPOINT_SHA


def run_inference(audio_path: str) -> InferenceResult:
    """Entry point. Blocked unless authorization passes."""
    auth = verify_inference_authorization()
    if not auth.ok:
        return InferenceResult(
            ready=False,
            inference_ready=False,
            blocked=True,
            message=f"Inference blocked: {auth.reason}",
            threshold=THRESHOLD,
        )
    return run_inference_core(audio_path)


def _cuda_preprocessing_ready() -> bool:
    try:
        if getattr(settings, "preprocessing_device", "cpu") != "cuda":
            return False
        if not torch.cuda.is_available():
            return False
        from app.ml.preprocessor import MEL_TRANSFORM

        dev = MEL_TRANSFORM.mel_scale.fb.device
        return dev.type == "cuda"
    except Exception:  # noqa: BLE001
        return False


def run_inference_core(audio_path: str) -> InferenceResult:
    """Trusted core. Enforces parity + CUDA readiness; runs model only if both pass."""
    handle = get_model_handle()
    if handle is None or not handle.ready or handle.model is None:
        return InferenceResult(False, False, True, "Model not loaded", threshold=THRESHOLD)
    if not _rv.PREPROCESSING_PARITY_VERIFIED:
        return InferenceResult(
            True,
            False,
            True,
            "Inference blocked: preprocessing parity not verified",
            threshold=THRESHOLD,
        )
    if not _cuda_preprocessing_ready():
        return InferenceResult(
            True, False, True, "Inference blocked: cuda runtime unavailable", threshold=THRESHOLD
        )
    feat = extract_features(audio_path)
    model_input = feat["model_input"]
    if tuple(model_input.shape) != EXPECTED_SHAPE:
        return InferenceResult(
            False, False, True, f"Bad input shape {tuple(model_input.shape)}", threshold=THRESHOLD
        )
    if str(model_input.dtype) != "torch.float32":
        return InferenceResult(
            False, False, True, f"Bad input dtype {model_input.dtype}", threshold=THRESHOLD
        )
    if not torch.isfinite(model_input).all():
        return InferenceResult(False, False, True, "Non-finite model input", threshold=THRESHOLD)
    cfg = getattr(handle, "config", None) or {}
    temp = float(cfg.get("temperature", 1.0)) if isinstance(cfg, dict) else 1.0
    thr = (
        float(cfg.get("classification_threshold", THRESHOLD))
        if isinstance(cfg, dict)
        else THRESHOLD
    )
    with torch.inference_mode():
        logit = handle.model(model_input).reshape(-1)
        prob = torch.sigmoid(logit / temp)
        logit_v = float(logit.item())
        prob_v = float(prob.item())
        predicted = int(prob_v >= thr)
        return InferenceResult(
            ready=True,
            inference_ready=True,
            blocked=False,
            message="ok",
            logit=logit_v,
            spoof_probability=prob_v,
            threshold=thr,
            predicted_class=predicted,
        )


def is_inference_ready() -> bool:
    return verify_inference_authorization().ok


def get_inference_status_code() -> str:
    auth = verify_inference_authorization()
    if auth.ok:
        return "INTERNAL_INFERENCE_READY"
    if auth.reason == "preprocessing_parity_not_verified":
        return "BLOCKED_PREPROCESSING_PARITY"
    if auth.reason == "preprocessing_device_not_cuda" or auth.reason == "cuda_unavailable":
        return "BLOCKED_VALIDATED_PREPROCESSING_RUNTIME"
    return "BLOCKED_" + (auth.reason or "unknown").upper()
