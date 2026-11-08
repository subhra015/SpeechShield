"""Audio schemas (Layer 5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AudioAssetResponse(BaseModel):
    id: int
    detected_format: str
    mime_type: str
    file_size_bytes: int
    sha256: str
    duration_seconds: float
    sample_rate: int
    channels: int
    sample_count: int
    status: str
    original_filename: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AudioAssetListResponse(BaseModel):
    items: list[AudioAssetResponse]
    total: int
    limit: int
    offset: int
