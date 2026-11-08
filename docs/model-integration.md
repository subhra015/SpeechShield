# V4 Model Integration (Layer 2 Revision)

## Status

**BLOCKED** — preprocessing pipeline implemented and verified against golden references, but the local checkpoint hash does not match the golden-reference manifest checkpoint hash. Inference remains disabled.

## Checkpoint

- Path: `backend/artifacts/v4/checkpoints/best_v4.pt`
- Local SHA-256: `40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda`
- Golden manifest SHA-256: `6f4f37e46e9fb22fcfd13334f6fb0d929c8170d125628c3d6e968b6f3272719f`
- Match: NO

## Verified components

- Checkpoint loads with `weights_only=True`, strict `load_state_dict`, eval mode, frozen params.
- SHA-256 verified against local manifest/config.
- Preprocessing implemented per notebook (`backend/app/ml/preprocessor.py`): standardize, mel, log-mel, normalization, FP16 round trip.
- Audio loader: WAV/FLAC decode + validation.
- Inference service: safe not-ready by default; `run_inference_core` callable for trusted backend/tests.
- Readiness: `inference_ready = false`.

## Preprocessing verification

All 5 golden fixtures: waveform/mel/log-mel/mean/std/normalized/fp16/model_input pass within justified CPU-vs-GPU tolerances. Logits fail due to checkpoint mismatch.

## Not enabled

- Public prediction endpoint (disabled until auth + parity).
- Audio upload endpoint.

## Docs

- `docs/preprocessing-parity.md` — full evidence table, tolerances, results.
- `docs/layer-status.md` — status.
