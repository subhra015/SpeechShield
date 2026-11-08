import numpy as np
import pytest
import soundfile as sf
import torch
from app.ml.preprocessor import (
    N_SAMPLES,
    SR,
    _resolve_preprocessing_device,
    extract_features,
    standardize_audio,
)


def test_standardize_short_right_pads(tmp_path):
    audio = np.ones(1000, dtype=np.float32)
    out, dur = standardize_audio(audio, SR)
    assert out.shape == (N_SAMPLES,)
    assert out.dtype == np.float32
    assert np.all(out[1000:] == 0.0)


def test_standardize_long_center_crops():
    audio = np.arange(N_SAMPLES + 1000, dtype=np.float32)
    out, dur = standardize_audio(audio, SR)
    assert out.shape == (N_SAMPLES,)
    start = (len(audio) - N_SAMPLES) // 2
    np.testing.assert_array_equal(out, audio[start : start + N_SAMPLES])


def test_standardize_resamples_non16k():
    audio = np.ones(22050, dtype=np.float32)
    out, dur = standardize_audio(audio, 22050)
    assert out.shape == (N_SAMPLES,)


def test_standardize_mono_from_stereo():
    data = np.stack([np.ones(1000), np.ones(1000) * 2], axis=1).astype(np.float32)
    out, dur = standardize_audio(data, SR)
    assert out.shape == (N_SAMPLES,)
    # first 1000 samples mean = 1.5
    assert abs(float(out[0]) - 1.5) < 1e-6


def test_standardize_rejects_empty():
    try:
        standardize_audio(np.array([], dtype=np.float32), SR)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_standardize_rejects_nonfinite():
    try:
        standardize_audio(np.array([1.0, np.nan], dtype=np.float32), SR)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_extract_features_shape_and_dtype(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(str(p), np.zeros(SR, dtype=np.float32), SR)
    feat = extract_features(p)
    assert feat["model_input"].shape == (1, 1, 64, 401)
    assert feat["model_input"].dtype == torch.float32
    assert feat["model_input"].device.type == "cpu"
    assert feat["feature"].device.type == "cpu"
    assert feat["normalized_feature_fp32"].shape == (1, 64, 401)
    assert feat["standardized_waveform"].shape == (N_SAMPLES,)
    # fp16 round trip present
    assert feat["feature_cache_fp16"].dtype == np.float16


def test_extract_features_finite(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(str(p), (np.random.randn(SR) * 0.1).astype(np.float32), SR)
    feat = extract_features(p)
    assert torch.isfinite(feat["model_input"]).all()


def test_cuda_preprocessing_fails_closed_when_unavailable(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="Refusing to fall back to CPU"):
        _resolve_preprocessing_device("cuda")
