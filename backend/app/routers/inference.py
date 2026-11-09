"""Inference router (Layer 8 + remediation)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.audio_asset import AudioAsset
from app.models.audio_job import AudioJob
from app.models.inference_run import InferenceRun
from app.models.user import User
from app.schemas.inference import InferenceRunListResponse, InferenceRunResponse
from app.services.audio_service import storage_dir
from app.services.audit_service import record_audit_event
from app.services.inference_service import (
    CHECKPOINT_SHA,
    MODEL_ID,
    run_inference,
    verify_inference_authorization,
)
from app.services.job_service import transition

logger = logging.getLogger("speechshield")

router = APIRouter(tags=["inference"])


@router.post(
    "/api/jobs/{job_id}/inference",
    response_model=InferenceRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_inference(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InferenceRun:
    cid = getattr(request.state, "request_id", None)
    job = (
        db.query(AudioJob)
        .filter(AudioJob.id == job_id, AudioJob.owner_user_id == current_user.id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    asset = (
        db.query(AudioAsset)
        .filter(AudioAsset.id == job.audio_asset_id, AudioAsset.owner_user_id == current_user.id)
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    # Idempotency: return existing run if already completed/failed/blocked.
    existing = (
        db.query(InferenceRun)
        .filter(InferenceRun.job_id == job.id)
        .order_by(InferenceRun.id.desc())
        .first()
    )
    if existing is not None and existing.status in (
        "COMPLETED",
        "FAILED",
        "BLOCKED_PENDING_AUTHORIZATION",
    ):
        return existing
    if existing is not None and existing.status == "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Inference already running"
        )

    run = InferenceRun(
        owner_user_id=current_user.id,
        audio_asset_id=asset.id,
        job_id=job.id,
        model_id=MODEL_ID,
        checkpoint_sha256=CHECKPOINT_SHA,
        status="BLOCKED_PENDING_AUTHORIZATION",
        correlation_id=cid,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    auth = verify_inference_authorization()
    if not auth.ok:
        run.status = "BLOCKED_PENDING_AUTHORIZATION"
        run.error_category = auth.reason
        run.error_message = "Inference authorization not granted"
        db.commit()
        db.refresh(run)
        record_audit_event(
            action="inference_blocked",
            success=False,
            actor_user_id=current_user.id,
            resource_type="inference_run",
            resource_id=str(run.id),
            correlation_id=cid,
            metadata={"reason": auth.reason},
        )
        raise HTTPException(status_code=423, detail=f"Inference blocked: {auth.reason}")

    # Authorized path
    path = storage_dir() / asset.storage_id
    run.status = "RUNNING"
    run.started_at = datetime.now(UTC)
    db.commit()

    from app.ml.preprocessor import extract_features

    feat = extract_features(str(path))
    standardized = feat["standardized_waveform"]
    model_input = feat["model_input_fp32"]
    n = len(standardized)
    step = max(1, n // 256)
    wav_preview = [float(x) for x in standardized[::step][:256]]
    fm = model_input[0]
    t_cols = 96
    step_t = max(1, fm.shape[1] // t_cols)
    fm_preview = fm[:, ::step_t][:, :t_cols].tolist()
    fm_preview = [[round(float(v), 4) for v in row] for row in fm_preview]

    # Transition job to INFERENCE_RUNNING
    try:
        if job.status in ("VALIDATED", "BLOCKED_PENDING_INFERENCE_AUTHORIZATION"):
            transition(job, "INFERENCE_RUNNING")
            db.commit()
            db.refresh(job)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run.status = "FAILED"
        run.error_category = "state_transition_error"
        run.error_message = str(exc)[:512]
        db.commit()
        db.refresh(run)
        logger.exception("Job transition to INFERENCE_RUNNING failed")
        raise HTTPException(status_code=500, detail="State transition failed") from exc

    result = run_inference(str(path))
    run.completed_at = datetime.now(UTC)
    if result.blocked or not result.ready:
        run.status = "FAILED"
        run.error_category = "blocked"
        run.error_message = result.message
        try:
            transition(job, "FAILED")
            db.commit()
            db.refresh(job)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("Job transition to FAILED failed")
            raise HTTPException(status_code=500, detail="State transition failed") from exc
    else:
        run.status = "COMPLETED"
        run.spoof_probability = result.spoof_probability
        run.threshold = result.threshold
        run.predicted_class = result.predicted_class
        run.model_logit = result.logit
        run.waveform_preview = json.dumps(wav_preview)
        run.feature_map_preview = json.dumps(fm_preview)
        run.evaluated_segment_start = 0.0
        run.evaluated_segment_end = 4.0
        run.model_input_shape = str(tuple(feat["model_input"].shape))
        run.preprocessing_device = str(settings.preprocessing_device)
        run.inference_device = "cpu"
        try:
            transition(job, "COMPLETED")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            run.status = "FAILED"
            run.error_category = "state_transition_error"
            run.error_message = str(exc)[:512]
            db.commit()
            db.refresh(run)
            logger.exception("Job transition to COMPLETED failed; run marked FAILED")
            raise HTTPException(status_code=500, detail="State transition failed") from exc
        db.commit()
        db.refresh(job)
    db.commit()
    db.refresh(run)

    record_audit_event(
        action="inference_completed" if run.status == "COMPLETED" else "inference_failed",
        success=run.status == "COMPLETED",
        actor_user_id=current_user.id,
        resource_type="inference_run",
        resource_id=str(run.id),
        correlation_id=cid,
    )
    return run


@router.get("/api/inference/{run_id}", response_model=InferenceRunResponse)
def get_inference(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InferenceRun:
    cid = getattr(request.state, "request_id", None)
    run = (
        db.query(InferenceRun)
        .filter(InferenceRun.id == run_id, InferenceRun.owner_user_id == current_user.id)
        .first()
    )
    if run is None:
        record_audit_event(
            action="inference_access_denied",
            success=False,
            actor_user_id=current_user.id,
            resource_type="inference_run",
            resource_id=str(run_id),
            correlation_id=cid,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/api/inference", response_model=InferenceRunListResponse)
def list_inference(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> InferenceRunListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    q = db.query(InferenceRun).filter(InferenceRun.owner_user_id == current_user.id)
    total = q.count()
    items = q.order_by(InferenceRun.created_at.desc()).offset(offset).limit(limit).all()
    return InferenceRunListResponse(items=items, total=total, limit=limit, offset=offset)
