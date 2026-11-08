"""Audio job lifecycle service (Layer 7)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.audio_asset import AudioAsset
from app.models.audio_job import AudioJob, JobStatus
from app.services.audit_service import record_audit_event

# Legal transitions
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.QUEUED.value: {JobStatus.VALIDATING.value, JobStatus.CANCELLED.value},
    JobStatus.VALIDATING.value: {
        JobStatus.VALIDATED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.VALIDATED.value: {JobStatus.BLOCKED_PENDING_INFERENCE_AUTHORIZATION.value},
    JobStatus.FAILED.value: set(),
    JobStatus.CANCELLED.value: set(),
    JobStatus.BLOCKED_PENDING_INFERENCE_AUTHORIZATION.value: set(),
}


class InvalidTransition(Exception):
    pass


def transition(job: AudioJob, new_status: str) -> None:
    if new_status not in {s.value for s in JobStatus}:
        raise InvalidTransition(f"Unknown status: {new_status}")
    if new_status not in LEGAL_TRANSITIONS.get(job.status, set()) and new_status != job.status:
        raise InvalidTransition(f"Illegal transition {job.status} -> {new_status}")
    job.status = new_status
    job.updated_at = datetime.now(UTC)
    if new_status == JobStatus.VALIDATING.value and job.started_at is None:
        job.started_at = datetime.now(UTC)
    if new_status in (
        JobStatus.VALIDATED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
        JobStatus.BLOCKED_PENDING_INFERENCE_AUTHORIZATION.value,
    ):
        job.completed_at = datetime.now(UTC)


def create_job(
    db: Session, asset: AudioAsset, owner_id: int, correlation_id: str | None = None
) -> AudioJob:
    # Idempotent: return the most recent job for this asset+owner if one exists.
    existing = (
        db.query(AudioJob)
        .filter(
            AudioJob.audio_asset_id == asset.id,
            AudioJob.owner_user_id == owner_id,
        )
        .order_by(AudioJob.id.desc())
        .first()
    )
    if existing is not None:
        return existing
    job = AudioJob(
        audio_asset_id=asset.id,
        owner_user_id=owner_id,
        job_type="preflight",
        status=JobStatus.QUEUED.value,
        correlation_id=correlation_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_preflight(
    db: Session, job: AudioJob, asset: AudioAsset, correlation_id: str | None = None
) -> AudioJob:
    """Run pre-inference checks only. No model, no features, no prediction."""
    transition(job, JobStatus.VALIDATING.value)
    db.commit()
    db.refresh(job)
    try:
        # Existence / ownership / storage consistency checks.
        from app.services.audio_service import storage_dir

        path = storage_dir() / asset.storage_id
        if not path.is_file():
            raise ValueError("Stored audio file missing")
        if asset.file_size_bytes <= 0:
            raise ValueError("Invalid file size")
        if asset.sample_rate <= 0 or asset.duration_seconds <= 0:
            raise ValueError("Invalid audio metadata")
        # Hash check
        import hashlib

        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != asset.sha256:
            raise ValueError("Stored file hash mismatch")
        transition(job, JobStatus.VALIDATED.value)
        # After validation, mark blocked pending inference authorization (no inference performed).
        transition(job, JobStatus.BLOCKED_PENDING_INFERENCE_AUTHORIZATION.value)
        record_audit_event(
            action="audio_job_preflight",
            success=True,
            actor_user_id=job.owner_user_id,
            resource_type="audio_job",
            resource_id=str(job.id),
            correlation_id=correlation_id,
            metadata={"status": job.status},
        )
    except Exception as exc:  # noqa: BLE001
        job.failure_category = "validation_error"
        job.failure_message = str(exc)[:512]
        transition(job, JobStatus.FAILED.value)
        record_audit_event(
            action="audio_job_preflight",
            success=False,
            actor_user_id=job.owner_user_id,
            resource_type="audio_job",
            resource_id=str(job.id),
            correlation_id=correlation_id,
            metadata={"error": str(exc)[:256]},
        )
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job: AudioJob) -> AudioJob:
    if job.status in (JobStatus.QUEUED.value,):
        transition(job, JobStatus.CANCELLED.value)
        db.commit()
        db.refresh(job)
    return job
