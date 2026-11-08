"""Audit logging service (Layer 4)."""

from __future__ import annotations

import json
from typing import Any

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog


def _sanitize_metadata(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    # Remove sensitive keys and bound size.
    sensitive = {"password", "password_hash", "token", "access_token", "secret", "authorization"}
    clean = {k: v for k, v in metadata.items() if k.lower() not in sensitive}
    text = json.dumps(clean, default=str)
    if len(text) > 4096:
        text = text[:4096]
    return text


def record_audit_event(
    *,
    action: str,
    success: bool,
    actor_user_id: int | None = None,
    resource_type: str = "auth",
    resource_id: str | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    source_identifier: str | None = None,
) -> None:
    """Persist an audit event in its own transaction (independent of caller tx)."""
    db = SessionLocal()
    try:
        event = AuditLog(
            actor_user_id=actor_user_id,
            action=action[:64],
            resource_type=resource_type[:64],
            resource_id=(resource_id[:128] if resource_id else None),
            success=bool(success),
            correlation_id=(correlation_id[:64] if correlation_id else None),
            metadata_json=_sanitize_metadata(metadata),
            source_identifier=(source_identifier[:128] if source_identifier else None),
        )
        db.add(event)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
