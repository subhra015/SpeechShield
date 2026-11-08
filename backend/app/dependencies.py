"""FastAPI dependencies (Layer 3 + Layer 6 cookie support)."""

from __future__ import annotations

import secrets

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import record_audit_event
from app.services.auth_service import decode_access_token, get_user_by_username

security = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if cookie_token:
        return cookie_token
    return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    token = _extract_token(credentials, session_cookie)
    if token is None:
        record_audit_event(
            action="auth_failure",
            success=False,
            resource_type="auth",
            metadata={"reason": "missing_or_invalid_scheme"},
            correlation_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    subject = decode_access_token(token)
    if subject is None:
        record_audit_event(
            action="auth_failure",
            success=False,
            resource_type="auth",
            metadata={"reason": "invalid_token"},
            correlation_id=getattr(request.state, "request_id", None),
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
            correlation_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    return user


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)
