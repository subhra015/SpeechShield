"""V4 audio preprocessing (authoritative, from high-throughput notebook Layer 2).

Uses torchaudio.transforms.MelSpectrogram to match the training pipeline.
"""

from __future__ import annotations

from math import gcd
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
import torchaudio
from scipy.signal import resample_poly

from app.config import settings


def _load_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    import json

    artifact_dir = settings.resolved_artifact_dir()
    v4_cfg = json.loads((artifact_dir / "v4_config.json").read_text(encoding="utf-8"))
    pre_cfg = json.loads((artifact_dir / "preprocessing_config.json").read_text(encoding="utf-8"))
    return v4_cfg, pre_cfg


_V4_CFG, _PRE_CFG = _load_configs()


def _resolve_preprocessing_device(device_name: str) -> torch.device:
    """Resolve the preprocessing device without silent CPU fallback."""
    if device_name == "cpu":
        return torch.device("cpu")

    if device_name == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA preprocessing requested, but CUDA is unavailable. "
                "Refusing to fall back to CPU."
            )
        return torch.device("cuda")

    raise ValueError(f"Unsupported preprocessing device: {device_name!r}")


PREPROCESSING_DEVICE = _resolve_preprocessing_device(settings.preprocessing_device)

SR: int = int(_PRE_CFG["target_sample_rate"])
N_SAMPLES: int = int(round(SR * float(_PRE_CFG["target_length_seconds"])))
N_MELS: int = int(_PRE_CFG["n_mels"])
N_FFT: int = int(_PRE_CFG["n_fft"])
HOP: int = int(_PRE_CFG["hop_length"])
EPS: float = float(_PRE_CFG["log_epsilon"])
STD_FLOOR: float = float(_PRE_CFG["normalization_std_floor"])
MEL_POWER: float = float(_PRE_CFG["mel_power"])
MEL_CENTER: bool = bool(_PRE_CFG["mel_center"])
MEL_PAD_MODE: str = _PRE_CFG["mel_pad_mode"]
MEL_NORM = _PRE_CFG["mel_norm"]
MEL_SCALE: str = _PRE_CFG["mel_scale"]
TEMPERATURE: float = float(_V4_CFG.get("temperature", 1.0))
THRESHOLD: float = float(_V4_CFG["classification_threshold"])


def _mel_device() -> torch.device:
    from app.config import settings

    dev = getattr(settings, "preprocessing_device", "cpu")
    if dev == "cuda" and torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


# Cached mel transform (device-aware)
MEL_TRANSFORM = (
    torchaudio.transforms.MelSpectrogram(
        sample_rate=SR,
        n_fft=N_FFT,
        win_length=N_FFT,
        hop_length=HOP,
        f_min=0.0,
        f_max=SR / 2,
        n_mels=N_MELS,
        window_fn=torch.hann_window,
        power=MEL_POWER,
        normalized=False,
        center=MEL_CENTER,
        pad_mode=MEL_PAD_MODE,
        norm=MEL_NORM,
        mel_scale=MEL_SCALE,
    )
    .to(_mel_device())
    .to(PREPROCESSING_DEVICE)
)


def decode_audio(path: str | Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return np.asarray(audio, dtype=np.float32), int(sr)


def standardize_audio(audio: np.ndarray, source_sr: int) -> tuple[np.ndarray, float]:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 2:
        audio = audio.mean(axis=1, dtype=np.float32)
    if audio.ndim != 1 or audio.size == 0:
        raise ValueError("Audio is empty or has an unsupported shape")
    if not np.isfinite(audio).all():
        raise ValueError("Waveform contains NaN/Inf")
    if int(source_sr) <= 0:
        raise ValueError(f"Invalid sample rate: {source_sr}")
    if int(source_sr) != SR:
        g = gcd(int(source_sr), SR)
        audio = resample_poly(audio, SR // g, int(source_sr) // g).astype(np.float32, copy=False)
    duration = len(audio) / SR
    if len(audio) > N_SAMPLES:
        start = (len(audio) - N_SAMPLES) // 2
        audio = audio[start : start + N_SAMPLES]
    elif len(audio) < N_SAMPLES:
        audio = np.pad(audio, (0, N_SAMPLES - len(audio)))
    return np.ascontiguousarray(audio, dtype=np.float32), float(duration)


@torch.inference_mode()
def mel_from_waveform(waveform: np.ndarray) -> torch.Tensor:
    device = MEL_TRANSFORM.mel_scale.fb.device
    wb = torch.from_numpy(np.ascontiguousarray(waveform, dtype=np.float32)).unsqueeze(0).to(device)
    return MEL_TRANSFORM(wb).detach().cpu()


def extract_features(path: str | Path) -> dict[str, Any]:
    audio, sr = decode_audio(path)
    standardized, duration = standardize_audio(audio, sr)
    mel = mel_from_waveform(standardized)  # (1, n_mels, frames)
    log_mel = torch.log(mel + EPS)
    mean = log_mel.mean(dim=(1, 2), keepdim=True)
    std = log_mel.std(dim=(1, 2), unbiased=False, keepdim=True).clamp_min(STD_FLOOR)
    normalized = ((log_mel - mean) / std).unsqueeze(1).float()  # (1,1,64,401)
    # FP16 cache round trip
    # Keep the public feature/model-input contract on CPU even when
    # mel computation and normalization execute on CUDA.
    normalized_cpu = normalized.detach().to(device="cpu")
    normalized_np = normalized_cpu[0].numpy().astype(np.float32)
    feature_fp16 = normalized_np.astype(np.float16)
    model_input_np = feature_fp16.astype(np.float32)
    model_input = torch.from_numpy(model_input_np).unsqueeze(0)
    return {
        "standardized_waveform": standardized,
        "duration": duration,
        "mel": mel[0].detach().cpu().numpy(),
        "log_mel": log_mel[0].detach().cpu().numpy(),
        "normalization_mean": mean[0].detach().cpu().numpy(),
        "normalization_std": std[0].detach().cpu().numpy(),
        "normalized_feature_fp32": normalized_np,
        "feature_cache_fp16": feature_fp16,
        "model_input_fp32": model_input_np,
        "model_input": model_input,
        "feature": normalized_cpu,
    }
