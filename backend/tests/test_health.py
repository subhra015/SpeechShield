def test_health_application_available(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["application"] == "available"
    assert data["model_ready"] is True
    assert data["checkpoint_loaded"] is True
    assert data["inference_ready"] is False
    assert data["model_error"] is None
    assert data["status"] == "ok"


def test_health_distinguishes_model_readiness(client):
    r = client.get("/api/health")
    data = r.json()
    # application availability != model readiness concept: both reported
    assert "model_ready" in data
    assert "application" in data


def test_root_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
