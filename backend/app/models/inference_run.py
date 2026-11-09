"""Inference run model (Layer 8)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import UTCDateTime


class InferenceRun(Base):
    __tablename__ = "inference_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audio_asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audio_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("audio_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_id: Mapped[str] = mapped_column(String(32), default="V4", nullable=False)
    checkpoint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), default="BLOCKED_PENDING_AUTHORIZATION", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    spoof_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_class: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_logit: Mapped[float | None] = mapped_column(Float, nullable=True)
    waveform_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_map_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_segment_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_segment_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_input_shape: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preprocessing_device: Mapped[str | None] = mapped_column(String(16), nullable=True)
    inference_device: Mapped[str | None] = mapped_column(String(16), nullable=True)
