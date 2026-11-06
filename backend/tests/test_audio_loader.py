import numpy as np
import soundfile as sf
from app.ml.audio_loader import AudioLoadError, load_audio


def test_load_wav(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(str(p), np.zeros(1600, dtype=np.float32), 16000)
    a = load_audio(p)
    assert a.sample_rate == 16000
    assert a.channels == 1
    assert a.num_samples == 1600
    assert a.duration_seconds == 0.1


def test_load_flac(tmp_path):
    p = tmp_path / "t.flac"
    sf.write(str(p), np.ones(800, dtype=np.float32) * 0.1, 8000)
    a = load_audio(p)
    assert a.sample_rate == 8000
    assert a.channels == 1


def test_stereo_shape(tmp_path):
    p = tmp_path / "s.wav"
    data = np.stack([np.zeros(1000), np.ones(1000)], axis=1).astype(np.float32)
    sf.write(str(p), data, 16000)
    a = load_audio(p)
    assert a.channels == 2
    assert a.waveform.shape == (1000, 2)


def test_unsupported_format(tmp_path):
    p = tmp_path / "t.mp3"
    p.write_bytes(b"fake")
    try:
        load_audio(p)
        raised = False
    except AudioLoadError:
        raised = True
    assert raised


def test_missing_file(tmp_path):
    try:
        load_audio(tmp_path / "nope.wav")
        raised = False
    except AudioLoadError:
        raised = True
    assert raised


def test_non_finite_validation_logic(monkeypatch, tmp_path):
    import numpy as np
    from app.ml import audio_loader

    p = tmp_path / "x.wav"
    p.write_bytes(b"fake")
    monkeypatch.setattr(
        audio_loader.sf,
        "read",
        lambda *a, **k: (np.array([1.0, np.nan, 2.0], dtype=np.float32), 16000),
    )
    try:
        audio_loader.load_audio(p)
        raised = False
    except AudioLoadError:
        raised = True
    assert raised


def test_corrupted_audio_rejected(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_bytes(b"not a wav file")
    try:
        load_audio(p)
        raised = False
    except AudioLoadError:
        raised = True
    assert raised
