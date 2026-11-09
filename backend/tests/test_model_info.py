def test_model_info_safe_metadata_only(client):
    response = client.get("/api/model/info")
    assert response.status_code == 200

    data = response.json()

    assert data["inference_production_ready"] is False
    assert data["inference_status"] == "INTERNAL_INFERENCE_READY"
    assert data["preprocessing_parity_verified"] is True
    assert data["inference_ready"] is True

    assert data["model_version"] == "V4"
    assert data["architecture"] == "CompactCNN"
    assert data["checkpoint_sha256"] is not None
    assert data["sha256_verified"] is True

    for forbidden in (
        "checkpoint_bytes",
        "checkpoint_path",
        "state_dict",
        "manifest",
        "speaker",
    ):
        assert forbidden not in data


def test_model_info_no_prediction_endpoint(client):
    for path in (
        "/api/predict",
        "/api/analyze",
        "/api/infer",
        "/api/upload",
    ):
        response = client.get(path)
        assert response.status_code in (404, 405)


def test_model_info_reports_internal_readiness_separately_from_production(client, monkeypatch):
    import app.ml.reference_validation as rv
    import app.routers.model_info as model_info_router

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", True)
    monkeypatch.setattr(
        model_info_router,
        "get_inference_status_code",
        lambda: "INTERNAL_INFERENCE_READY",
    )

    response = client.get("/api/model/info")

    assert response.status_code == 200
    data = response.json()

    assert data["preprocessing_parity_verified"] is True
    assert data["inference_status"] == "INTERNAL_INFERENCE_READY"
    assert data["inference_ready"] is True
    assert data["inference_production_ready"] is False


def test_model_info_reports_cuda_runtime_block_separately(client, monkeypatch):
    import app.ml.reference_validation as rv
    import app.routers.model_info as model_info_router

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", True)
    monkeypatch.setattr(
        model_info_router,
        "get_inference_status_code",
        lambda: "BLOCKED_VALIDATED_PREPROCESSING_RUNTIME",
    )

    response = client.get("/api/model/info")

    assert response.status_code == 200
    data = response.json()

    assert data["preprocessing_parity_verified"] is True
    assert data["inference_status"] == "BLOCKED_VALIDATED_PREPROCESSING_RUNTIME"
    assert data["inference_ready"] is False
    assert data["inference_production_ready"] is False
