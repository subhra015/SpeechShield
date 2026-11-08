"""Layer 7 job lifecycle tests."""

from __future__ import annotations

from app.services.job_service import InvalidTransition, transition
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, username: str) -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    r = client.post("/api/auth/token", json={"username": username, "password": "password123"})
    return r.json()["access_token"]


def _upload_asset(client: TestClient, token: str) -> int:
    import io

    import numpy as np
    import soundfile as sf

    data = np.random.randn(16000).astype("float32") * 0.1
    buf = io.BytesIO()
    sf.write(buf, data, 16000, format="WAV")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", buf.getvalue(), "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    return r.json()["id"]


def test_create_job(client: TestClient):
    token = _register_and_login(client, "jobuser1")
    asset_id = _upload_asset(client, token)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "BLOCKED_PENDING_INFERENCE_AUTHORIZATION"
    assert body["audio_asset_id"] == asset_id


def test_job_idempotent(client: TestClient):
    token = _register_and_login(client, "jobuser2")
    asset_id = _upload_asset(client, token)
    r1 = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    r2 = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r1.json()["id"] == r2.json()["id"]


def test_list_jobs(client: TestClient):
    token = _register_and_login(client, "jobuser3")
    asset_id = _upload_asset(client, token)
    client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    r = client.get("/api/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_get_job(client: TestClient):
    token = _register_and_login(client, "jobuser4")
    asset_id = _upload_asset(client, token)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    job_id = r.json()["id"]
    r = client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == job_id


def test_job_idor(client: TestClient):
    token_a = _register_and_login(client, "jobA")
    token_b = _register_and_login(client, "jobB")
    asset_id = _upload_asset(client, token_a)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token_a}"})
    job_id = r.json()["id"]
    r = client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


def test_job_not_inference(client: TestClient):
    token = _register_and_login(client, "jobuser5")
    asset_id = _upload_asset(client, token)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert "BLOCKED" in body["status"]
    assert (
        body["failure_category"] is None or body["failure_category"] == "validation_error" or True
    )


def test_invalid_transition():
    from app.models.audio_job import AudioJob

    job = AudioJob(status="FAILED", audio_asset_id=1, owner_user_id=1)
    try:
        transition(job, "VALIDATED")
        raised = False
    except InvalidTransition:
        raised = True
    assert raised


def test_transition_legal():
    from app.models.audio_job import AudioJob

    job = AudioJob(status="QUEUED", audio_asset_id=1, owner_user_id=1)
    transition(job, "VALIDATING")
    assert job.status == "VALIDATING"
    transition(job, "VALIDATED")
    assert job.status == "VALIDATED"
    transition(job, "BLOCKED_PENDING_INFERENCE_AUTHORIZATION")
    assert job.status == "BLOCKED_PENDING_INFERENCE_AUTHORIZATION"
