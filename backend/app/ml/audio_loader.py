"""Audio loading and validation utilities (Layer 2).

Only WAV and FLAC are supported. Decoding uses soundfile (libsndfile).
No resampling, mono conversion, cropping, or feature extraction is performed here;
those steps are part of preprocessing parity, which is currently BLOCKED.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass
class LoadedAudio:
    waveform: np.ndarray  # native channels, float32
    sample_rate: int
    channels: int
    num_samples: int
    duration_seconds: float


class AudioLoadError(ValueError):
    pass


def load_audio(path: str | Path) -> LoadedAudio:
    p = Path(path)
    if not p.is_file():
        raise AudioLoadError(f"Audio file not found: {p}")
    suffix = p.suffix.lower()
    if suffix not in {".wav", ".flac"}:
        raise AudioLoadError(f"Unsupported format {suffix}; only .wav and .flac are supported")
    try:
        data, sr = sf.read(str(p), dtype="float32", always_2d=False)
    except Exception as exc:  # noqa: BLE001
        raise AudioLoadError(f"Failed to decode audio: {exc}") from exc
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 1:
        channels = 1
    elif arr.ndim == 2:
        channels = arr.shape[1]
    else:
        raise AudioLoadError(f"Unexpected audio array shape: {arr.shape}")
    if sr <= 0:
        raise AudioLoadError(f"Invalid sample rate: {sr}")
    if arr.size == 0:
        raise AudioLoadError("Audio contains no samples")
    if not np.all(np.isfinite(arr)):
        raise AudioLoadError("Audio contains non-finite values (NaN/Inf)")
    duration = arr.shape[0] / float(sr)
    return LoadedAudio(
        waveform=arr,
        sample_rate=int(sr),
        channels=channels,
        num_samples=int(arr.shape[0]),
        duration_seconds=float(duration),
    )
