"""Layer 4 security hardening tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.services.auth_service import create_access_token, decode_access_token
from fastapi.testclient import TestClient
from jose import jwt


def test_password_not_stored_plaintext(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "secuser", "email": "sec@example.com", "password": "supersecret123"},
    )
    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "secuser").first()
        assert u is not None
        assert u.password_hash != "supersecret123"
        assert u.password_hash.startswith("$2")
    finally:
        db.close()


def test_expired_token_rejected(client: TestClient):
    token = create_access_token(subject="ghost", expires_delta=timedelta(seconds=-10))
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_tampered_token_rejected(client: TestClient):
    token = create_access_token(subject="ghost")
    # tamper payload by re-encoding with wrong secret
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + "." + "a" * len(parts[2])
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_invalid_signature_rejected(client: TestClient):
    token = jwt.encode(
        {"sub": "ghost", "exp": datetime.now(UTC).timestamp() + 3600},
        "wrong-secret",
        algorithm="HS256",
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_malformed_token_rejected(client: TestClient):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
    assert r.status_code == 401


def test_missing_bearer(client: TestClient):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_wrong_scheme(client: TestClient):
    r = client.get("/api/auth/me", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


def test_unknown_user_token(client: TestClient):
    token = create_access_token(subject="no_such_user")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_decode_access_token_invalid():
    assert decode_access_token("garbage") is None


def test_audit_log_on_register_and_login(client: TestClient):
    before = _audit_count()
    client.post(
        "/api/auth/register",
        json={"username": "audituser", "email": "audit@example.com", "password": "password123"},
    )
    client.post("/api/auth/token", json={"username": "audituser", "password": "password123"})
    after = _audit_count()
    assert after >= before + 2


def test_audit_log_on_failed_login(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "auditfail", "email": "auditfail@example.com", "password": "password123"},
    )
    before = _audit_count(action="login", success=False)
    client.post("/api/auth/token", json={"username": "auditfail", "password": "wrong"})
    after = _audit_count(action="login", success=False)
    assert after == before + 1


def test_audit_timestamp_utc_aware(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "tsuser", "email": "ts@example.com", "password": "password123"},
    )
    db = SessionLocal()
    try:
        ev = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert ev is not None
        assert ev.timestamp.tzinfo is not None
    finally:
        db.close()


def test_audit_no_secrets(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "username": "secretuser",
            "email": "secret@example.com",
            "password": "supersecret999",
        },
    )
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).all()
        for r in rows:
            text = (r.metadata_json or "") + (r.resource_id or "")
            assert "supersecret999" not in text
            assert "access_token" not in text.lower() or "supersecret" not in text
    finally:
        db.close()


def test_failed_auth_does_not_lose_audit(client: TestClient):
    before = _audit_count(action="auth_failure", success=False)
    client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    after = _audit_count(action="auth_failure", success=False)
    assert after == before + 1


def test_audit_correlation_id(client: TestClient):
    r = client.post(
        "/api/auth/register",
        json={"username": "ciduser", "email": "cid@example.com", "password": "password123"},
        headers={"X-Request-ID": "test-corr-123"},
    )
    assert r.status_code == 201
    db = SessionLocal()
    try:
        ev = db.query(AuditLog).filter(AuditLog.correlation_id == "test-corr-123").first()
        assert ev is not None
    finally:
        db.close()


def test_rate_limit_login(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "ratelimituser", "email": "rl@example.com", "password": "password123"},
    )
    # exhaust per-account limit
    for _ in range(10):
        client.post("/api/auth/token", json={"username": "ratelimituser", "password": "wrong"})
    r = client.post("/api/auth/token", json={"username": "ratelimituser", "password": "wrong"})
    assert r.status_code == 429


def _audit_count(action: str | None = None, success: bool | None = None) -> int:
    db = SessionLocal()
    try:
        q = db.query(AuditLog)
        if action is not None:
            q = q.filter(AuditLog.action == action)
        if success is not None:
            q = q.filter(AuditLog.success == success)
        return q.count()
    finally:
        db.close()
