"""Layer 9 end-to-end workflow tests."""

from __future__ import annotations

import io

import numpy as np
import pytest  # noqa: E402
import soundfile as sf
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, username: str) -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    r = client.post("/api/auth/token", json={"username": username, "password": "password123"})
    return r.json()["access_token"]


def test_e2e_workflow(client: TestClient, monkeypatch):
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

    token = _register_and_login(client, "e2euser")
    # session restore
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "e2euser"

    # upload
    data = np.random.randn(16000).astype("float32") * 0.1
    buf = io.BytesIO()
    sf.write(buf, data, 16000, format="WAV")
    r = client.post(
        "/api/audio",
        files={"file": ("e2e.wav", buf.getvalue(), "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    asset_id = r.json()["id"]
    assert r.json()["sha256"]

    # list + ownership
    r = client.get("/api/audio", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # get metadata
    r = client.get(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # preflight job
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "BLOCKED_PENDING_INFERENCE_AUTHORIZATION"

    # blocked inference
    r = client.post(
        f"/api/jobs/{job['id']}/inference", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 201
    assert r.json()["status"] == "COMPLETED"

    # logout (cookie flow not used; token still valid until expiry, but endpoint clears cookie)
    r = client.post("/api/auth/logout")
    assert r.status_code == 204


def test_cross_user_idor(client: TestClient):
    token_a = _register_and_login(client, "e2eA")
    token_b = _register_and_login(client, "e2eB")
    data = np.random.randn(16000).astype("float32") * 0.1
    buf = io.BytesIO()
    import soundfile as sf

    sf.write(buf, data, 16000, format="WAV")
    r = client.post(
        "/api/audio",
        files={"file": ("x.wav", buf.getvalue(), "audio/wav")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    asset_id = r.json()["id"]
    # B cannot read
    r = client.get(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404
    # B cannot delete
    r = client.delete(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


GOLDEN_DIR = __import__("pathlib").Path(
    r"D:\Projects\SpeechShield-Backups\SpeechShield_V4_Approved_Golden_20261107T183430Z"
)
GOLDEN_LOGITS = {"genuine_normal": -14.27575397491455, "synthetic_normal": 0.6027581691741943}
GOLDEN_PROBS = {"genuine_normal": 6.311295805971895e-07, "synthetic_normal": 0.6462870836257935}
GOLDEN_CLASSES = {"genuine_normal": 0, "synthetic_normal": 1}


def _register_and_login2(client, username):
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    r = client.post("/api/auth/token", json={"username": username, "password": "password123"})
    return r.json()["access_token"]


@pytest.fixture
def authorized_client(client, monkeypatch, tmp_path):
    import app.ml.reference_validation as rv
    from app.config import settings

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", True)
    monkeypatch.setattr(settings, "preprocessing_device", "cuda")
    storage = tmp_path / "audio_uploads"
    storage.mkdir()
    monkeypatch.setattr(settings, "audio_storage_dir", str(storage))
    yield client, storage


@pytest.mark.gpu
@pytest.mark.parametrize("fixture_name", ["genuine_normal", "synthetic_normal"])
def test_isolated_real_inference(authorized_client, fixture_name):
    client, storage = authorized_client
    token = _register_and_login2(client, f"iso_{fixture_name}")
    wav_path = GOLDEN_DIR / "fixtures" / f"{fixture_name}.wav"
    data = wav_path.read_bytes()
    r = client.post(
        "/api/audio",
        files={"file": (f"{fixture_name}.wav", data, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    asset_id = r.json()["id"]
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    job_id = r.json()["id"]
    r = client.post(f"/api/jobs/{job_id}/inference", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert abs(body["model_logit"] - GOLDEN_LOGITS[fixture_name]) <= 1e-4
    assert abs(body["spoof_probability"] - GOLDEN_PROBS[fixture_name]) <= 1e-5
    assert body["predicted_class"] == GOLDEN_CLASSES[fixture_name]
    run_id = body["id"]
    r = client.get(f"/api/inference/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


import pytest  # noqa: E402


@pytest.mark.gpu
def test_real_inference_runs(client):
    token = _register_and_login(client, "realinf")
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
    asset_id = r.json()["id"]
    r = client.post(f"/api/audio/{asset_id}/jobs", headers={"Authorization": f"Bearer {token}"})
    job_id = r.json()["id"]
    r = client.post(f"/api/jobs/{job_id}/inference", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["spoof_probability"] is not None
    assert 0 <= body["spoof_probability"] <= 1
    assert body["predicted_class"] in (0, 1)
