from types import SimpleNamespace

import app.ml.reference_validation as rv
import app.services.inference_service as svc
import numpy as np
import pytest
import soundfile as sf
import torch


def test_parity_verified():
    assert rv.PREPROCESSING_PARITY_VERIFIED is True


def test_parity_status_ready():
    status = rv.parity_status()
    assert status["preprocessing_parity_verified"] is True


def test_inference_ready():
    assert svc.is_inference_ready() is True


def test_inference_runs_when_authorized(tmp_path):
    path = tmp_path / "test.wav"
    sf.write(str(path), np.zeros(1600, dtype=np.float32), 16000)

    result = svc.run_inference(str(path))

    assert result.inference_ready is True
    assert result.spoof_probability is not None


class StubModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.called = False

    def forward(self, model_input):
        self.called = True
        return torch.zeros(
            (model_input.shape[0], 1),
            dtype=torch.float32,
            device=model_input.device,
        )


def make_test_handle():
    model = StubModel()
    model.eval()
    return SimpleNamespace(ready=True, model=model)


def test_core_blocks_when_parity_disabled(monkeypatch):
    handle = make_test_handle()

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", False)
    monkeypatch.setattr(svc, "get_model_handle", lambda: handle)
    monkeypatch.setattr(svc, "_cuda_preprocessing_ready", lambda: True)

    def unexpected_feature_extraction(_):
        pytest.fail("Feature extraction must not occur when parity is disabled.")

    monkeypatch.setattr(svc, "extract_features", unexpected_feature_extraction)

    result = svc.run_inference_core("unused.wav")

    assert result.ready is True
    assert result.inference_ready is False
    assert "parity" in result.message.lower()
    assert handle.model.called is False


def test_core_blocks_when_cuda_runtime_unavailable(monkeypatch):
    handle = make_test_handle()

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", True)
    monkeypatch.setattr(svc, "get_model_handle", lambda: handle)
    monkeypatch.setattr(svc, "_cuda_preprocessing_ready", lambda: False)

    def unexpected_feature_extraction(_):
        pytest.fail("Feature extraction must not occur without validated CUDA.")

    monkeypatch.setattr(svc, "extract_features", unexpected_feature_extraction)

    result = svc.run_inference_core("unused.wav")

    assert result.ready is True
    assert result.inference_ready is False
    assert "cuda" in result.message.lower()
    assert handle.model.called is False


def test_core_runs_only_when_all_checks_pass(monkeypatch):
    handle = make_test_handle()

    monkeypatch.setattr(rv, "PREPROCESSING_PARITY_VERIFIED", True)
    monkeypatch.setattr(svc, "get_model_handle", lambda: handle)
    monkeypatch.setattr(svc, "_cuda_preprocessing_ready", lambda: True)

    model_input = torch.zeros((1, 1, 64, 401), dtype=torch.float32)
    monkeypatch.setattr(
        svc,
        "extract_features",
        lambda _: {"model_input": model_input},
    )

    result = svc.run_inference_core("unused.wav")

    assert result.ready is True
    assert result.inference_ready is True
    assert result.logit is not None
    assert result.spoof_probability is not None
    assert 0 <= result.spoof_probability <= 1
    assert result.threshold is not None
    assert handle.model.called is True
