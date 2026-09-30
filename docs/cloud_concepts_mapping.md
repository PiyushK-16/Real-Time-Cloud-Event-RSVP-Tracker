# Where each Cloud Computing concept lives in this project

| Concept | Where it appears |
|---|---|
| Cloud Computing (general) | Whole app: stateless FastAPI backend + managed cloud database, deployable to any provider |
| SaaS | The deployed app itself, consumed by organizers/attendees over the browser |
| PaaS | Deployment target (Render/Railway/Fly.io) - you push code, the platform runs it |
| IaaS (where applicable) | Advanced option: raw AWS EC2/Lambda + RDS instead of a managed PaaS |
| Cloud Database | `cloud/database_service.py` - SQLite locally, PostgreSQL (Supabase/RDS) in the cloud, same code |
| Real-Time Database | `realtime/realtime_service.py` hub, or Firestore/Supabase Realtime in Option B |
| Authentication | `cloud/auth_service.py` (password hashing + JWT) |
| Authorization | `backend/middleware/auth.py: require_role`, per-route checks in services (`require_manage`) |
| Role-Based Access Control | `role` column on `users`; attendee/organizer/admin permission table in README |
| REST APIs | `backend/routes/*.py` - full resource-oriented API, see README API section |
| WebSockets | `realtime/realtime_service.py: /ws/events/{id}`, `/ws/me` |
| Server-Sent Events | `realtime/realtime_service.py: /api/events/{id}/stream` |
| Serverless Computing | Advanced deployment option: routes mapped 1:1 to AWS Lambda functions behind API Gateway |
| Event-Driven Architecture | RSVP commit -> `hub.publish_threadsafe` event -> all subscribers react |
| Cloud Functions | Same as serverless computing row; e.g. a scheduled Lambda calling `event_service.sync_completed` |
| Scalability | `docs/scalability.md`; stateless backend + `Waitlist`/queue pattern for spikes |
| Elasticity | PaaS/serverless autoscaling described in `docs/scalability.md` |
| High Availability | Managed database replicas + multiple backend instances behind a load balancer |
| Load Balancing | Render/Railway/AWS ALB in front of multiple backend instances |
| API Gateway | AWS API Gateway (advanced option) fronting Lambda; locally, FastAPI itself is the gateway |
| CDN | Static frontend assets served through a CDN (CloudFront/Cloudflare) in production |
| Caching | Organizer summary/analytics are candidates for a Redis cache layer (see scalability doc) |
| Environment Variables | `.env.example`, `backend/config.py` - no secret is ever hardcoded |
| Secrets Management | `JWT_SECRET`, `DATABASE_URL` from env vars; AWS Secrets Manager in the enterprise option |
| Logging | `backend/utils/logging.py`, structured stdout logs picked up by any cloud log service |
| Monitoring | `/healthz`, `/readyz` probes; CloudWatch/Grafana consume these in production |
| Backup | Managed PostgreSQL automatic backups (Supabase/RDS); `sample_data/seed.py` for reseeding |
| CI/CD | `.github/workflows/ci.yml` - runs the automated test suite on every push |
| Cloud Deployment | `docs/deployment.md` - free-tier and enterprise AWS paths |
