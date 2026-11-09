"""Inference schemas (Layer 8)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InferenceRunResponse(BaseModel):
    id: int
    audio_asset_id: int
    job_id: int | None = None
    model_id: str
    checkpoint_sha256: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_category: str | None = None
    error_message: str | None = None
    spoof_probability: float | None = None
    threshold: float | None = None
    predicted_class: int | None = None
    model_logit: float | None = None
    waveform_preview: str | None = None
    feature_map_preview: str | None = None
    evaluated_segment_start: float | None = None
    evaluated_segment_end: float | None = None
    model_input_shape: str | None = None
    preprocessing_device: str | None = None
    inference_device: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InferenceRunListResponse(BaseModel):
    items: list[InferenceRunResponse]
    total: int
    limit: int
    offset: int
