from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient):
    r = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "alice"

    r = client.post("/api/auth/token", json={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_login_invalid(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    r = client.post("/api/auth/token", json={"username": "bob", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_auth(client: TestClient):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_duplicate_register(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    r = client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol2@example.com", "password": "password123"},
    )
    assert r.status_code == 409


def test_security_headers(client: TestClient):
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
