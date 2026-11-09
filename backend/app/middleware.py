"""Request correlation ID, security headers and rate-limiting middleware (Layer 3)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-XSS-Protection", "0")
        return response


# Process-global rate-limit buckets (clearable in tests).
RATE_LIMIT_HITS: dict[str, deque[float]] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, per_minute: int = 60):
        super().__init__(app)
        self.per_minute = per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only rate-limit API routes.
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = RATE_LIMIT_HITS[client]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= self.per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit CSRF protection for cookie-authenticated unsafe requests."""

    UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
    EXEMPT_PATHS = {"/api/auth/login", "/api/auth/register", "/api/auth/token", "/api/auth/logout"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if (
            request.method in self.UNSAFE
            and request.url.path.startswith("/api")
            and request.url.path not in self.EXEMPT_PATHS
        ):
            # Only enforce when cookie auth is present (not Bearer).
            has_cookie = settings.session_cookie_name in request.cookies
            has_bearer = request.headers.get("Authorization", "").lower().startswith("bearer ")
            if has_cookie and not has_bearer:
                csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
                csrf_header = request.headers.get("X-CSRF-Token")
                if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                    return JSONResponse(
                        status_code=403, content={"detail": "CSRF validation failed"}
                    )
        return await call_next(request)
