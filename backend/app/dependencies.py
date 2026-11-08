"""FastAPI dependencies (Layer 3)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import record_audit_event
from app.services.auth_service import decode_access_token, get_user_by_username

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        record_audit_event(
            action="auth_failure",
            success=False,
            resource_type="auth",
            metadata={"reason": "missing_or_invalid_scheme"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    subject = decode_access_token(credentials.credentials)
    if subject is None:
        record_audit_event(
            action="auth_failure",
            success=False,
            resource_type="auth",
            metadata={"reason": "invalid_token"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user = get_user_by_username(db, subject)
    if user is None or not user.is_active:
        record_audit_event(
            action="auth_failure",
            success=False,
            resource_type="auth",
            metadata={"reason": "unknown_or_disabled_user"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    return user
