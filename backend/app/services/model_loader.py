"""
V4 model loader (Layer 0).

Loads and validates the verified V4 checkpoint without exposing it.
Does NOT perform inference; preprocessing parity is unverified (BLOCKED).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import torch

from app.config import settings


@dataclass
class ModelHandle:
    ready: bool = False
    error: Optional[str] = None
    model: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    preprocessing_config: Dict[str, Any] = field(default_factory=dict)
    manifest: Dict[str, Any] = field(default_factory=dict)
    checkpoint_path: Optional[Path] = None
    checkpoint_sha256: Optional[str] = None
    expected_sha256: Optional[str] = None
    inference_status: str = "BLOCKED_PREPROCESSING_PARITY"
    device: str = "cpu"
    parameter_count: Optional[int] = None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_model_class(model_def_path: Path):
    spec = importlib.util.spec_from_file_location("speechshield_model_def", str(model_def_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load model definition from {model_def_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "CompactCNN"):
        raise RuntimeError("model_def.py does not define CompactCNN")
    return mod.CompactCNN


def load_v4_model() -> ModelHandle:
    handle = ModelHandle(device=settings.device)
    try:
        artifact_dir = settings.resolved_artifact_dir()
        ckpt_path = settings.resolved_checkpoint_path()
        cfg_path = settings.resolved_config_path()
        manifest_path = settings.resolved_manifest_path()
        model_def_path = artifact_dir / "model_def.py"
        preproc_path = artifact_dir / "preprocessing_config.json"

        for p in (ckpt_path, cfg_path, manifest_path, model_def_path, preproc_path):
            if not p.is_file():
                raise FileNotFoundError(f"Missing required artifact: {p}")

        handle.checkpoint_path = ckpt_path
        handle.config = _load_json(cfg_path)
        handle.preprocessing_config = _load_json(preproc_path)
        handle.manifest = _load_json(manifest_path)

        # Expected SHA from manifest
        expected = None
        files = handle.manifest.get("files", {})
        entry = files.get("checkpoints/best_v4.pt") or files.get("v4_training/checkpoints/best_v4.pt")
        if entry and "sha256" in entry:
            expected = entry["sha256"]
        if handle.manifest.get("checkpoint_sha256"):
            expected = handle.manifest.get("checkpoint_sha256")
        if handle.config.get("checkpoint_sha256"):
            expected = handle.config.get("checkpoint_sha256")
        if settings.expected_checkpoint_sha256:
            expected = settings.expected_checkpoint_sha256
        handle.expected_sha256 = expected

        actual = _sha256_file(ckpt_path)
        handle.checkpoint_sha256 = actual
        if expected and actual.lower() != expected.lower():
            raise RuntimeError(
                f"Checkpoint SHA-256 mismatch: expected {expected}, got {actual}"
            )

        # Architecture compatibility
        arch = handle.config.get("model_architecture")
        if arch != "CompactCNN":
            raise RuntimeError(f"Unexpected model_architecture: {arch}")

        model_cls = _load_model_class(model_def_path)
        model = model_cls()
        # weights_only=True: checkpoint is a raw state_dict of tensors
        state_dict = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        if not isinstance(state_dict, dict):
            raise RuntimeError("Checkpoint is not a state_dict")
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        for p in model.parameters():
            p.requires_grad_(False)

        handle.model = model
        handle.parameter_count = sum(p.numel() for p in model.parameters())
        handle.ready = True
        handle.inference_status = "BLOCKED_PREPROCESSING_PARITY"
    except Exception as exc:  # noqa: BLE001
        handle.ready = False
        handle.error = str(exc)
        handle.model = None
    return handle


# Module-level singleton, populated during app lifespan
_model_handle: Optional[ModelHandle] = None


def get_model_handle() -> Optional[ModelHandle]:
    return _model_handle


def set_model_handle(h: ModelHandle) -> None:
    global _model_handle
    _model_handle = h
