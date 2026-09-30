# Security notes

- **Authentication**: PBKDF2-SHA256 password hashing (200k iterations, unique salt per user) - never
  plaintext, never a fast/unsalted hash. JWT access tokens, short-lived, signed with a server-only secret.
- **Authorization / RBAC**: `role` on the user record decides permissions; every event/RSVP-mutating
  endpoint re-checks ownership server-side (`require_manage`, `require_role`) - never trusts a client claim.
- **HTTPS / encryption in transit**: enforced by the hosting platform (Render/Railway/CloudFront all
  terminate TLS); local dev uses plain HTTP for simplicity only.
- **Encryption at rest**: managed database encryption (enabled by default on Supabase/RDS/Cloud SQL).
- **Input validation**: every request body is a Pydantic model (`backend/schemas.py`) - malformed input
  never reaches the database.
- **SQL injection**: SQLAlchemy's parameterised queries are used everywhere; no raw string-built SQL.
- **XSS**: the frontend never injects untrusted strings as HTML without any escaping strategy in a
  production build; for a React/Vue rewrite, framework auto-escaping should be relied on.
- **CORS**: `CORS_ORIGINS` in `.env` whitelists the exact frontend origin(s), not `*`.
- **Rate limiting**: `backend/middleware/rate_limit.py` throttles login/register/RSVP endpoints per key.
- **Secrets management**: `JWT_SECRET`, `DATABASE_URL`, `ADMIN_PASSWORD` all come from environment
  variables (`.env`, gitignored); production uses the platform's secret store.
- **Audit logs**: `audit_logs` table records who did what (event created/updated, RSVP set, cancellations).

## Why the frontend can never set RSVP counts directly
The frontend only ever sends an *intent* (`{"status": "GOING"}`). The `going_count` on an event is
never accepted as client input (`EventUpdate` schema has no such field) - it is only ever changed by
the atomic `UPDATE ... WHERE going_count < maximum_capacity` statement inside `rsvp_service.claim_seat`,
run on the server after validating the request. The database (`going_count <= maximum_capacity` CHECK
constraint) is the final backstop even if a bug slipped through application code. The client only ever
*reflects* counts it receives from the server/real-time hub - it can display wrong data locally, but it
can never persist wrong data.
