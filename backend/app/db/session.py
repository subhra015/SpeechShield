"""Database session management (Layer 3)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _resolve_db_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        path_part = url.replace("sqlite:///", "", 1)
        from pathlib import Path

        p = Path(path_part)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent.parent.parent / p).resolve()
            url = f"sqlite:///{p.as_posix()}"
        p.parent.mkdir(parents=True, exist_ok=True)
    return url


engine = create_engine(
    _resolve_db_url(),
    connect_args={"check_same_thread": False} if "sqlite" in _resolve_db_url() else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Additive, idempotent schema migration for SQLite (no data loss)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    # audio_assets: ensure all columns exist
    if "audio_assets" in insp.get_table_names():
        existing = {c["name"] for c in insp.get_columns("audio_assets")}
        # no new columns in Layer 11 for audio_assets
    if "inference_runs" in insp.get_table_names():
        existing = {c["name"] for c in insp.get_columns("inference_runs")}
        additions = {
            "waveform_preview": "TEXT",
            "feature_map_preview": "TEXT",
            "evaluated_segment_start": "FLOAT",
            "evaluated_segment_end": "FLOAT",
            "model_input_shape": "VARCHAR(32)",
            "preprocessing_device": "VARCHAR(16)",
            "inference_device": "VARCHAR(16)",
        }
        with engine.begin() as conn:
            for col, typ in additions.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE inference_runs ADD COLUMN {col} {typ}"))
