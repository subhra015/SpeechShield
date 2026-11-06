# V4 Model Integration (Layer 2)

## Status

**BLOCKED** — preprocessing parity not verified. Inference remains disabled.

- Checkpoint: `backend/artifacts/v4/checkpoints/best_v4.pt`
- SHA-256: `40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda`
- Architecture: `CompactCNN` (97,761 params)
- Config: `v4_config.json`, `preprocessing_config.json`

## Verified components

- Checkpoint loads with `weights_only=True`, strict `load_state_dict`.
- SHA-256 verified against manifest + config.
- Model eval mode, parameters frozen.
- Expected feature shape `(1, 64, 401)` derived from config (center=True → 401 frames).
- Audio loader: WAV/FLAC decode + validation (soundfile).
- Inference service: safe not-ready result; no model execution on unverified features.
- Readiness: `inference_ready = false` until parity verified.

## Not implemented (blocked)

- Mel spectrogram preprocessing (log base, fmin/fmax, window periodicity, resampling, crop, normalization order all unverified).
- Prediction endpoint.
- Audio upload endpoint.

## Missing evidence

See `docs/preprocessing-parity.md`.
