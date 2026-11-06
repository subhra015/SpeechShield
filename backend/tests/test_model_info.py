def test_model_info_safe_metadata_only(client):
    r = client.get("/api/model/info")
    assert r.status_code == 200
    data = r.json()
    assert data["inference_production_ready"] is False
    assert data["inference_status"] == "BLOCKED_PREPROCESSING_PARITY"
    assert data["preprocessing_parity_verified"] is False
    assert data["inference_ready"] is False
    # safe metadata present
    assert data["model_version"] == "V4"
    assert data["architecture"] == "CompactCNN"
    assert data["checkpoint_sha256"] is not None
    assert data["sha256_verified"] is True
    # no checkpoint bytes / paths / manifests
    for forbidden in ("checkpoint_bytes", "checkpoint_path", "state_dict", "manifest", "speaker"):
        assert forbidden not in data


def test_model_info_no_prediction_endpoint(client):
    # Layer 0 must not expose inference
    for path in ("/api/predict", "/api/analyze", "/api/infer", "/api/upload"):
        r = client.get(path)
        assert r.status_code in (404, 405)
