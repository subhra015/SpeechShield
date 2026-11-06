# Layer Status

## Layer 0 — Complete (commit 18b4a3b)

Foundation: backend/frontend skeletons, V4 checkpoint integrity verification, health/model-info endpoints, artifact privacy, tests. Inference blocked.

## Layer 1 — Complete (commit f787af7)

Engineering foundation: reproducible deps, Ruff, pytest config, structured logging, correlation IDs, readiness semantics, ESLint, Vitest, Docker (dev), CI workflow, docs.

Inference status: still `BLOCKED_PREPROCESSING_PARITY`. No prediction/audio endpoint added. V4 checkpoint unchanged.

## Layer 2 — BLOCKED (this commit)

V4 model integration scaffolding added (audio loader, reference validation contract, inference service stub, tests, docs). Preprocessing parity **not verified**; inference remains disabled. Outcome B (BLOCKED). V4 checkpoint unchanged.

## Outstanding / next

- Layer 2: V4 preprocessing parity verification (log transform, Mel semantics, crop/pad, normalization, tensor shape/numerics). Until then inference remains blocked.
- FFmpeg integration for MP3/WebM (planned, not yet).
- Docker images not built/tested locally (Docker not installed in dev environment); CI will build.
- httpx/starlette deprecation warning remains (upstream); documented, not suppressed.
