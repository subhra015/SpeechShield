# SpeechShield

Deepfake audio detection (audio spoofing). Layer 0 foundation.

## Status

**Layer 0 only.** Inference is BLOCKED pending preprocessing parity verification. No prediction or audio-upload endpoint is exposed.

## V4 model (private)

Validated V4 checkpoint and configs live under `backend/artifacts/v4` (private, gitignored):

- `checkpoints/best_v4.pt` (SHA-256 `40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda`)
- `v4_config.json`, `preprocessing_config.json`, `model_def.py`, `v4_artifact_manifest.json`

These must never be copied into `frontend/public` or served by any endpoint.

## Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
```

Endpoints:
- `GET /api/health` — application availability and model readiness (separate).
- `GET /api/model/info` — safe model metadata only.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Preprocessing parity blocker (Layer 1 prerequisite)

Exact training-extractor parity is not yet established. Before any inference endpoint:

1. Resolve log transformation (ln vs log10) and Mel parameter semantics.
2. Verify sample cropping/padding (`center_crop_or_right_pad`, 4.0 s @ 16 kHz).
3. Verify per-recording mean/std normalization (std floor 1e-5).
4. Verify exact feature tensor shape and numerical behavior.
5. Inspect training source references (not yet available in repo).

Config reference (`preprocessing_config.json`): 64 mel, n_fft 512, hop 160, power 2.0, center True, pad_mode reflect, norm None, scale htk, window hann, log_eps 1e-6, normalization per_recording_mean_std.

Until parity is verified, inference is BLOCKED. Do not expose a misleading prediction endpoint.

## Audio formats

Layer 0: WAV and FLAC (via soundfile/librosa). MP3 and WebM/Opus require a maintained FFmpeg decoder (not yet integrated). Do not claim support before verifying decoding.

## Security notes

- Checkpoint loaded with `weights_only=True`; SHA-256 verified against manifest.
- Artifacts are gitignored and not served.
- CORS restricted to configured origins.
- No auth in Layer 0; acceptable only because no sensitive operations are exposed.
