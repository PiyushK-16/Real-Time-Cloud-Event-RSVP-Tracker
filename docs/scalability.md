# Scalability notes

## 100 -> 10,000 -> 1,000,000 users
- **100 users**: one small backend instance + SQLite/small PostgreSQL is plenty. This is the local demo.
- **10,000 users**: move to managed PostgreSQL with connection pooling (PgBouncer), run 2-3 backend
  instances behind a load balancer, add a CDN for the static frontend.
- **1,000,000 users / a hot event**: see the flash-crowd scenario below.

## Flash crowd: 100,000 RSVP attempts for one event in 5 minutes
1. **CDN** serves the static frontend so the API only handles RSVP writes, not asset traffic.
2. **API Gateway + rate limiting** throttles abusive clients before they reach application servers.
3. **Autoscaling** application servers (stateless FastAPI containers) scale out horizontally under load.
4. **The real bottleneck is the single event row.** Every GOING RSVP for the same event contends on
   the same row (`UPDATE events SET going_count = going_count + 1 WHERE id = :id AND going_count < cap`).
   This is a classic **database hot spot**. Mitigations:
   - A **queue** (SQS/Pub-Sub) absorbs the burst and processes RSVPs at a rate the database can sustain,
     returning "request received, confirming shortly" instantly to the client.
   - **Sharding the counter**: keep N partial counters (e.g. 10 rows) and sum them for display, so writes
     spread across rows instead of serializing on one. Reconcile to the exact total periodically.
   - A **Redis atomic counter** (`INCR` with a Lua script) as a fast pre-check in front of the database,
     with the database transaction as the final source of truth.
5. **WebSocket scaling**: with several backend instances, replace the single in-process hub with
   **Redis Pub/Sub** (or a managed real-time service - Supabase Realtime, API Gateway WebSocket API)
   so a message published on any instance reaches clients connected to any other instance.
6. **Caching** read-heavy, slow-changing data (event details, analytics summaries) reduces database load;
   invalidate the cache on write.

## Database hot spots in this project
- The `events` row of a popular event (every GOING RSVP touches it) - mitigated as above.
- `notifications` for a mass announcement - insert in batches, or fan out asynchronously via a queue.
