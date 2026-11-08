"""Layer 5 audio upload tests."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from app.services.audio_service import storage_dir
from fastapi.testclient import TestClient


def _make_wav_bytes(duration: float = 1.0, sr: int = 16000, channels: int = 1) -> bytes:
    data = np.random.randn(int(sr * duration), channels).astype("float32") * 0.1
    if channels == 1:
        data = data.flatten()
    buf = io.BytesIO()
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


def _make_flac_bytes(duration: float = 1.0, sr: int = 16000) -> bytes:
    data = np.random.randn(int(sr * duration)).astype("float32") * 0.1
    buf = io.BytesIO()
    sf.write(buf, data, sr, format="FLAC")
    return buf.getvalue()


def _register_and_login(client: TestClient, username: str) -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    r = client.post("/api/auth/token", json={"username": username, "password": "password123"})
    return r.json()["access_token"]


def test_anonymous_upload_rejected(client: TestClient):
    r = client.post("/api/audio", files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")})
    assert r.status_code == 401


def test_invalid_token_rejected(client: TestClient):
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")},
        headers={"Authorization": "Bearer garbage"},
    )
    assert r.status_code == 401


def test_valid_wav_upload(client: TestClient):
    token = _register_and_login(client, "up1")
    data = _make_wav_bytes()
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", data, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["detected_format"] == "WAV"
    assert body["sample_rate"] == 16000
    assert "storage_id" not in body
    assert body["sha256"]


def test_valid_flac_upload(client: TestClient):
    token = _register_and_login(client, "up2")
    data = _make_flac_bytes()
    r = client.post(
        "/api/audio",
        files={"file": ("a.flac", data, "audio/flac")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json()["detected_format"] == "FLAC"


def test_empty_upload_rejected(client: TestClient):
    token = _register_and_login(client, "up3")
    r = client.post(
        "/api/audio",
        files={"file": ("empty.wav", b"", "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_corrupt_upload_rejected(client: TestClient):
    token = _register_and_login(client, "up4")
    r = client.post(
        "/api/audio",
        files={"file": ("bad.wav", b"not audio", "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_unsupported_extension_rejected(client: TestClient):
    token = _register_and_login(client, "up5")
    # executable bytes
    data = b"MZ\x90\x00" + b"\x00" * 100
    r = client.post(
        "/api/audio",
        files={"file": ("evil.exe", data, "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_oversized_upload_rejected(client: TestClient):
    token = _register_and_login(client, "up6")
    big = b"\x00" * (10 * 1024 * 1024 + 100)
    r = client.post(
        "/api/audio",
        files={"file": ("big.wav", big, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 413


def test_list_own_uploads(client: TestClient):
    token_a = _register_and_login(client, "ownerA")
    token_b = _register_and_login(client, "ownerB")
    client.post(
        "/api/audio",
        files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # B sees nothing
    r = client.get("/api/audio", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    # A sees one
    r = client.get("/api/audio", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_idor_read(client: TestClient):
    token_a = _register_and_login(client, "idorA")
    token_b = _register_and_login(client, "idorB")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    asset_id = r.json()["id"]
    r = client.get(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


def test_idor_delete(client: TestClient):
    token_a = _register_and_login(client, "delA")
    token_b = _register_and_login(client, "delB")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    asset_id = r.json()["id"]
    r = client.delete(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404
    # A can still see it
    r = client.get(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200


def test_delete_own(client: TestClient):
    token = _register_and_login(client, "delown")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    asset_id = r.json()["id"]
    r = client.delete(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
    r = client.get(f"/api/audio/{asset_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_sha256_matches(client: TestClient):
    token = _register_and_login(client, "shau")
    data = _make_wav_bytes()
    import hashlib

    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", data, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json()["sha256"] == hashlib.sha256(data).hexdigest()


def test_no_storage_path_in_response(client: TestClient):
    token = _register_and_login(client, "pathu")
    r = client.post(
        "/api/audio",
        files={"file": ("a.wav", _make_wav_bytes(), "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json()
    for key in ("storage_id", "storage_path", "path", "file_path"):
        assert key not in body


def test_storage_private(client: TestClient):
    # storage dir is under backend/data, not frontend

    sd = storage_dir()
    assert "frontend" not in str(sd)
    assert "public" not in str(sd)
