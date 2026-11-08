"""Audio upload and ownership router (Layer 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.audio_asset import AudioAsset
from app.models.user import User
from app.schemas.audio import AudioAssetListResponse, AudioAssetResponse
from app.services.audio_service import (
    AudioValidationError,
    delete_audio_file,
    save_audio,
    validate_audio_bytes,
)
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/audio", tags=["audio"])

# Upload-specific rate limit (process-local).
_upload_hits: dict[str, list[float]] = {}
_UPLOAD_LIMIT = settings.upload_rate_limit_per_minute


def _check_upload_rate_limit(client_ip: str) -> bool:
    import time

    now = time.monotonic()
    window = _upload_hits.setdefault(client_ip, [])
    window[:] = [t for t in window if now - t < 60.0]
    if len(window) >= _UPLOAD_LIMIT:
        return False
    window.append(now)
    return True


@router.post("", response_model=AudioAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioAsset:
    cid = getattr(request.state, "request_id", None)
    client_ip = request.client.host if request.client else "unknown"

    if not _check_upload_rate_limit(client_ip):
        record_audit_event(
            action="audio_upload_rate_limited",
            success=False,
            actor_user_id=current_user.id,
            resource_type="audio",
            correlation_id=cid,
            source_identifier=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Upload rate limit exceeded"
        )

    # Bounded read
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_size_bytes:
            record_audit_event(
                action="audio_upload_rejected",
                success=False,
                actor_user_id=current_user.id,
                resource_type="audio",
                correlation_id=cid,
                metadata={"reason": "size_exceeded"},
                source_identifier=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large"
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        record_audit_event(
            action="audio_upload_rejected",
            success=False,
            actor_user_id=current_user.id,
            resource_type="audio",
            correlation_id=cid,
            metadata={"reason": "empty"},
            source_identifier=client_ip,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        meta = validate_audio_bytes(data)
    except AudioValidationError as exc:
        record_audit_event(
            action="audio_upload_rejected",
            success=False,
            actor_user_id=current_user.id,
            resource_type="audio",
            correlation_id=cid,
            metadata={"reason": str(exc)},
            source_identifier=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid audio file"
        ) from exc

    storage_id = save_audio(data)

    asset = AudioAsset(
        owner_user_id=current_user.id,
        storage_id=storage_id,
        original_filename=file.filename,
        detected_format=meta["format"],
        mime_type=meta["mime_type"],
        file_size_bytes=meta["file_size"],
        sha256=meta["sha256"],
        duration_seconds=meta["duration"],
        sample_rate=meta["sample_rate"],
        channels=meta["channels"],
        sample_count=meta["sample_count"],
        status="uploaded",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    record_audit_event(
        action="audio_upload_succeeded",
        success=True,
        actor_user_id=current_user.id,
        resource_type="audio",
        resource_id=str(asset.id),
        correlation_id=cid,
        metadata={"format": meta["format"], "size": meta["file_size"]},
        source_identifier=client_ip,
    )
    return asset


@router.get("", response_model=AudioAssetListResponse)
def list_audio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> AudioAssetListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    q = db.query(AudioAsset).filter(AudioAsset.owner_user_id == current_user.id)
    total = q.count()
    items = q.order_by(AudioAsset.created_at.desc()).offset(offset).limit(limit).all()
    return AudioAssetListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{asset_id}", response_model=AudioAssetResponse)
def get_audio(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioAsset:
    cid = getattr(request.state, "request_id", None)
    asset = db.query(AudioAsset).filter(AudioAsset.id == asset_id).first()
    if asset is None or asset.owner_user_id != current_user.id:
        record_audit_event(
            action="audio_access_denied",
            success=False,
            actor_user_id=current_user.id,
            resource_type="audio",
            resource_id=str(asset_id),
            correlation_id=cid,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audio(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    cid = getattr(request.state, "request_id", None)
    asset = db.query(AudioAsset).filter(AudioAsset.id == asset_id).first()
    if asset is None or asset.owner_user_id != current_user.id:
        record_audit_event(
            action="audio_delete_denied",
            success=False,
            actor_user_id=current_user.id,
            resource_type="audio",
            resource_id=str(asset_id),
            correlation_id=cid,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    storage_id = asset.storage_id
    db.delete(asset)
    db.commit()
    delete_audio_file(storage_id)
    record_audit_event(
        action="audio_delete",
        success=True,
        actor_user_id=current_user.id,
        resource_type="audio",
        resource_id=str(asset_id),
        correlation_id=cid,
    )
