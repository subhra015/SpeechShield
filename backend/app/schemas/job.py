"""Job schemas (Layer 7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AudioJobResponse(BaseModel):
    id: int
    audio_asset_id: int
    job_type: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    failure_category: str | None = None
    failure_message: str | None = None
    retry_count: int
    correlation_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AudioJobListResponse(BaseModel):
    items: list[AudioJobResponse]
    total: int
    limit: int
    offset: int
