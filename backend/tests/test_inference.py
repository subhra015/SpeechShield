"""Layer 8 inference tests (gate enabled locally)."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from app.ml.reference_validation import PREPROCESSING_PARITY_VERIFIED
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, username: str) -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    r = client.post("/api/auth/token", json={"username": username, "password": "password123"})
    return r.json()["access_token"]


def _upload_asset(client: TestClient, token: str) -> int:
    data = np.random.randn(16000).astype("float32") * 0.1
    buf = io.BytesIO()
    sf.write(buf, data, 16000, format="WAV")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", buf.getvalue(), "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    return r.json()["id"]


import pytest  # noqa: E402


@pytest.mark.gpu
def test_inference_runs_when_authorized(client: TestClient):
    token = _register_and_login(client, "infuser1")
    asset_id = _upload_asset(client, token)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    job_id = r.json()["id"]
    r = client.post(f"/api/jobs/{job_id}/inference", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["spoof_probability"] is not None


def test_inference_runs_when_authorized_cpu(client, monkeypatch):
    from app.services.inference_service import InferenceResult

    monkeypatch.setattr(
        "app.routers.inference.verify_inference_authorization",
        lambda: __import__(
            "app.services.inference_service", fromlist=["AuthorizationResult"]
        ).AuthorizationResult(ok=True, reason=None),
    )
    monkeypatch.setattr(
        "app.routers.inference.run_inference",
        lambda _p: InferenceResult(
            ready=True,
            inference_ready=True,
            blocked=False,
            message="ok",
            logit=-1.0,
            spoof_probability=0.25,
            threshold=0.395,
            predicted_class=0,
        ),
    )

    token = _register_and_login(client, "infuser_cpu")
    asset_id = _upload_asset(client, token)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    job_id = r.json()["id"]
    r = client.post(f"/api/jobs/{job_id}/inference", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "COMPLETED"


def test_inference_requires_auth(client: TestClient):
    r = client.post("/api/jobs/1/inference")
    assert r.status_code == 401


def test_inference_idor(client: TestClient):
    token_a = _register_and_login(client, "infA")
    token_b = _register_and_login(client, "infB")
    asset_id = _upload_asset(client, token_a)
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token_a}"})
    job_id = r.json()["id"]
    r = client.post(f"/api/jobs/{job_id}/inference", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


def test_inference_list_own(client: TestClient):
    token = _register_and_login(client, "infuser2")
    r = client.get("/api/inference", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "items" in r.json()


def test_gate_flag_enabled():
    assert PREPROCESSING_PARITY_VERIFIED is True


import pytest  # noqa: E402


@pytest.mark.gpu
def test_verify_authorization_passes():
    from app.services.inference_service import verify_inference_authorization

    res = verify_inference_authorization()
    assert res.ok is True


def test_completion_transition_failure_marks_run_failed(monkeypatch, client):
    import app.routers.inference as inf_router
    import app.services.job_service as js

    original = js.transition

    def failing_transition(job, new_status):
        if new_status == "COMPLETED":
            raise RuntimeError("transition boom")
        return original(job, new_status)

    monkeypatch.setattr(inf_router, "transition", failing_transition)
    monkeypatch.setattr(js, "transition", failing_transition)

    import app.ml.reference_validation as rv
    from app.services.inference_service import AuthorizationResult, InferenceResult

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", True)
    monkeypatch.setattr(
        inf_router,
        "verify_inference_authorization",
        lambda: AuthorizationResult(ok=True, reason=None),
    )
    monkeypatch.setattr(
        "app.services.inference_service.verify_inference_authorization",
        lambda: AuthorizationResult(ok=True, reason=None),
    )
    monkeypatch.setattr(
        inf_router,
        "run_inference",
        lambda _p: InferenceResult(
            ready=True,
            inference_ready=True,
            blocked=False,
            message="ok",
            logit=-1.0,
            spoof_probability=0.25,
            threshold=0.395,
            predicted_class=0,
        ),
    )
    monkeypatch.setattr(
        "app.services.inference_service.run_inference",
        lambda _p: InferenceResult(
            ready=True,
            inference_ready=True,
            blocked=False,
            message="ok",
            logit=-1.0,
            spoof_probability=0.25,
            threshold=0.395,
            predicted_class=0,
        ),
    )
    monkeypatch.setattr("app.services.inference_service._cuda_preprocessing_ready", lambda: True)

    from app.services.model_loader import get_model_handle, load_v4_model, set_model_handle

    if get_model_handle() is None:
        set_model_handle(load_v4_model())

    token = _register_and_login(client, "tfuser2")
    data = np.random.randn(16000).astype("float32") * 0.1
    buf = io.BytesIO()
    sf.write(buf, data, 16000, format="WAV")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", buf.getvalue(), "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    asset_id = r.json()["id"]
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    job_id = r.json()["id"]
    r = client.post(f"/api/jobs/{job_id}/inference", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 500
    runs = client.get("/api/inference", headers={"Authorization": f"Bearer {token}"}).json()[
        "items"
    ]
    assert any(run["status"] != "COMPLETED" for run in runs)
