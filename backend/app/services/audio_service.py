"""Audio validation and private storage (Layer 5)."""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from pathlib import Path
from typing import Any

import soundfile as sf

from app.config import settings

ALLOWED_FORMATS = {"WAV", "FLAC"}


class AudioValidationError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_audio_bytes(data: bytes) -> dict[str, Any]:
    if not data:
        raise AudioValidationError("Empty file")
    if len(data) > settings.max_upload_size_bytes:
        raise AudioValidationError("File exceeds maximum upload size")

    # Detect format via soundfile (server-side, not client metadata).
    try:
        info = sf.info(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise AudioValidationError(f"Unable to parse audio container: {exc}") from exc

    fmt = (info.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise AudioValidationError(f"Unsupported audio format: {fmt}")

    sr = int(info.samplerate)
    if sr < settings.min_sample_rate or sr > settings.max_sample_rate:
        raise AudioValidationError(f"Sample rate {sr} outside allowed range")

    channels = int(info.channels)
    if channels < 1 or channels > settings.max_audio_channels:
        raise AudioValidationError(f"Channel count {channels} not allowed")

    # Decode fully to validate samples.
    try:
        samples, sr2 = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception as exc:  # noqa: BLE001
        raise AudioValidationError(f"Failed to decode audio: {exc}") from exc

    arr = samples.astype("float32", copy=False)
    if arr.ndim != 2:
        raise AudioValidationError("Unexpected audio array shape")
    n_frames = int(arr.shape[0])
    if n_frames == 0:
        raise AudioValidationError("Audio contains no samples")
    if n_frames > settings.max_decoded_samples:
        raise AudioValidationError("Decoded sample count exceeds limit")
    if not (settings.min_sample_rate <= sr2 <= settings.max_sample_rate):
        raise AudioValidationError("Invalid sample rate")
    duration = n_frames / float(sr2)
    if duration > settings.max_audio_duration_seconds:
        raise AudioValidationError("Audio duration exceeds limit")
    if not (channels == arr.shape[1]):
        raise AudioValidationError("Channel mismatch")
    if not all_finite(arr):
        raise AudioValidationError("Audio contains NaN or Inf")

    mime = (
        "audio/wav"
        if fmt == "WAV"
        else "audio/flac"
        if fmt == "FLAC"
        else "application/octet-stream"
    )

    return {
        "format": fmt,
        "mime_type": mime,
        "sample_rate": int(sr2),
        "channels": int(arr.shape[1]),
        "sample_count": int(arr.shape[0]),
        "duration": float(duration),
        "sha256": sha256_bytes(data),
        "file_size": len(data),
    }


def all_finite(arr) -> bool:
    import numpy as np

    return bool(np.all(np.isfinite(arr)))


def storage_dir() -> Path:
    p = Path(settings.audio_storage_dir)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent.parent.parent / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_audio(data: bytes) -> str:
    """Save bytes to a private file with a random UUID name. Returns storage_id."""
    storage_id = uuid.uuid4().hex
    target = storage_dir() / storage_id
    tmp = storage_dir() / f".{storage_id}.tmp"
    try:
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception:  # noqa: BLE001
        import contextlib

        with contextlib.suppress(Exception):
            tmp.unlink(missing_ok=True)
        raise
    return storage_id


def delete_audio_file(storage_id: str) -> None:
    import contextlib

    with contextlib.suppress(Exception):
        (storage_dir() / storage_id).unlink(missing_ok=True)


def read_audio_bytes(storage_id: str) -> bytes | None:
    p = storage_dir() / storage_id
    if not p.is_file():
        return None
    return p.read_bytes()
