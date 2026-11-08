# Audit Logging (Layer 4)

## Model
`audit_logs` table: id, timestamp (UTC-aware), actor_user_id (nullable), action, resource_type, resource_id, success, correlation_id, metadata_json, source_identifier.

## Coverage
- register (success/failure), login (success/failure), auth_failure, auth_me, rate-limit rejections.

## Safety
- Passwords, hashes, tokens, secrets, Authorization headers are never stored.
- Metadata sanitized (sensitive keys removed, bounded to 4096 chars).
- Append-only application behavior (no public modify/delete API).
- Failed auth transactions still record audit events (separate DB session/commit).

## Tamper resistance
Normal database table, not cryptographically tamper-proof. Protection is application-level (no public mutation endpoints). Documented limitation.

## Timestamps
UTC-aware via custom TypeDecorator (SQLite stores naive UTC, returns aware). `datetime.now(UTC)` used.