# Security Architecture (Layer 4)

## Authentication
- Passwords hashed with bcrypt (cost default).
- JWT HS256, configurable secret (min 16 chars; production requires >=32 and rejects defaults/placeholders).
- Algorithm allowlist: HS256 only. Tokens decoded with explicit algorithms list (prevents alg confusion).
- Bearer scheme required; missing/invalid tokens return 401 with generic messages.

## Rate limiting
- General API: 60 req/min per IP (process-local).
- Login: 10 req/min per IP and per normalized account (process-local).
- Process-local state is a limitation for multi-worker deployments (documented).

## Security headers
X-Content-Type-Options, X-Frame-Options, Referrer-Policy, X-XSS-Protection.

## Secrets
- JWT secret never logged or exposed. `.env.example` uses an unmistakable placeholder with generation command.
- Real secrets must not be committed.

## Inference gate
Unchanged. `PREPROCESSING_PARITY_VERIFIED=False`, `inference_production_ready=False`. No prediction endpoint.