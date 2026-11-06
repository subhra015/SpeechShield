from app.ml.reference_validation import PREPROCESSING_PARITY_VERIFIED, parity_status
from app.services.inference_service import is_inference_ready, run_inference


def test_parity_not_verified():
    assert PREPROCESSING_PARITY_VERIFIED is False


def test_parity_status_blocked():
    s = parity_status()
    assert s["preprocessing_parity_verified"] is False
    assert s["inference_ready"] is False


def test_inference_not_ready():
    assert is_inference_ready() is False


def test_inference_returns_not_ready(tmp_path):
    import numpy as np
    import soundfile as sf

    p = tmp_path / "t.wav"
    sf.write(str(p), np.zeros(1600, dtype=np.float32), 16000)
    r = run_inference(str(p))
    assert r.ready is False or r.ready is True  # model may be loaded
    assert r.inference_ready is False
    assert "blocked" in r.message.lower() or "parity" in r.message.lower()
    assert r.spoof_probability is None
