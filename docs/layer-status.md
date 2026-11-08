# Layer Status

## Layer 0 — Complete (commit 18b4a3b)

Foundation: backend/frontend skeletons, V4 checkpoint integrity verification, health/model-info endpoints, artifact privacy, tests. Inference blocked.

## Layer 1 — Complete (commit f787af7)

Engineering foundation: reproducible deps, Ruff, pytest config, structured logging, correlation IDs, readiness semantics, ESLint, Vitest, Docker (dev), CI workflow, docs.

Inference status: still `BLOCKED_PREPROCESSING_PARITY`. No prediction/audio endpoint added. V4 checkpoint unchanged.

## Layer 2 — Complete (validated)

Preprocessing pipeline implemented and verified against 5 approved golden fixtures (all stages pass). Checkpoint `40c96ffa…` matches approved manifest. Inference remains disabled pending authentication layer. V4 checkpoint unchanged.

## Layer 3 — Complete

Authentication & API security: User model (SQLAlchemy/SQLite), registration/login (bcrypt), JWT issuance, `/api/auth/me`, rate limiting, security headers, DB table creation on startup. Inference still blocked (`PREPROCESSING_PARITY_VERIFIED=False`, `inference_ready=False`). No prediction endpoint added.

## Layer 4 — Complete (this change)

Authentication hardening & DB-backed audit logging:
- JWT secret hardening (>=32 chars in production, reject defaults, explicit HS256 allowlist).
- JWT validation tests (expired, tampered, invalid signature, alg confusion, malformed, missing bearer, unknown/disabled user).
- Stricter login rate limiting (per-IP + per-account, 429, generic errors).
- `AuditLog` model (UTC-aware timestamps via custom TypeDecorator, indexes, bounded fields).
- Audit events for register/login/failures/rate-limit/auth failures with correlation IDs.
- Audit records never contain passwords/tokens/secrets; sanitization enforced.
- UTC timestamp cleanup (datetime.now(UTC), timezone-aware columns).
- Additive schema (create_all, idempotent). No data loss.

Inference remains blocked. No prediction/upload/analysis endpoint. V4 checkpoint unchanged.

## Layer 5 — Complete

Secure audio upload, validation, private storage & user ownership. Inference still blocked.

## Layer 6 — Complete

Secure frontend authentication & audio upload integration (HttpOnly cookie, CSRF, React Router, upload UI).

## Layer 7 — Complete (this change)

Backend audio job lifecycle + premium frontend redesign:
- AudioJob model, state machine (QUEUED→VALIDATING→VALIDATED→BLOCKED_PENDING_INFERENCE_AUTHORIZATION / FAILED / CANCELLED), preflight (no inference).
- Endpoints: POST /api/audio/{id}/jobs, GET /api/jobs, GET /api/jobs/{id}, POST /api/jobs/{id}/cancel.
- Idempotent job creation, ownership checks, audit events.
- Frontend: design system (tokens, card/btn/input/badge), app shell with sidebar, Login/Register/Dashboard redesign, responsive, reduced-motion support.
- Tests: 75 passed (8 new job lifecycle tests). Frontend lint + build pass.
- Inference still blocked.
