"""Audio job router (Layer 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.audio_asset import AudioAsset
from app.models.audio_job import AudioJob, JobStatus
from app.models.user import User
from app.schemas.job import AudioJobListResponse, AudioJobResponse
from app.services.audit_service import record_audit_event
from app.services.job_service import cancel_job, create_job, run_preflight

router = APIRouter(tags=["jobs"])


@router.post(
    "/api/audio/{asset_id}/jobs",
    response_model=AudioJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_audio_job(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioJob:
    cid = getattr(request.state, "request_id", None)
    asset = (
        db.query(AudioAsset)
        .filter(AudioAsset.id == asset_id, AudioAsset.owner_user_id == current_user.id)
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    job = create_job(db, asset, current_user.id, cid)
    # Run preflight only for freshly queued jobs.
    if job.status == JobStatus.QUEUED.value:
        job = run_preflight(db, job, asset, cid)
    return job


@router.get("/api/jobs", response_model=AudioJobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> AudioJobListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    q = db.query(AudioJob).filter(AudioJob.owner_user_id == current_user.id)
    total = q.count()
    items = q.order_by(AudioJob.created_at.desc()).offset(offset).limit(limit).all()
    return AudioJobListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/api/jobs/{job_id}", response_model=AudioJobResponse)
def get_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioJob:
    cid = getattr(request.state, "request_id", None)
    job = (
        db.query(AudioJob)
        .filter(AudioJob.id == job_id, AudioJob.owner_user_id == current_user.id)
        .first()
    )
    if job is None:
        record_audit_event(
            action="job_access_denied",
            success=False,
            actor_user_id=current_user.id,
            resource_type="audio_job",
            resource_id=str(job_id),
            correlation_id=cid,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/api/jobs/{job_id}/cancel", response_model=AudioJobResponse)
def cancel_job_endpoint(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioJob:
    cid = getattr(request.state, "request_id", None)
    job = (
        db.query(AudioJob)
        .filter(AudioJob.id == job_id, AudioJob.owner_user_id == current_user.id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job cannot be cancelled")
    job = cancel_job(db, job)
    record_audit_event(
        action="audio_job_cancelled",
        success=True,
        actor_user_id=current_user.id,
        resource_type="audio_job",
        resource_id=str(job_id),
        correlation_id=cid,
    )
    return job
