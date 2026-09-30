# Architecture & Database Design

## ER Diagram (text form)

```
USERS (id PK, email UQ, name, password_hash, role, is_active, created_at)
   |1
   | creates
   *N
EVENTS (id PK, organizer_id FK->USERS.id, event_name, ..., going_count, status)
   |1                                  |1
   | has many                          | has many
   *N                                  *N
RSVPS (id PK, event_id FK, user_id FK->USERS.id, status, UNIQUE(event_id,user_id))
   |
WAITLIST (id PK, event_id FK, user_id FK, status, UNIQUE(event_id,user_id))   -- id order = FIFO

EVENTS 1---* ANNOUNCEMENTS (id PK, event_id FK, organizer_id FK, title, message)
EVENTS 1---* INVITATIONS   (id PK, event_id FK, email, UNIQUE(event_id,email))
USERS  1---* NOTIFICATIONS (id PK, user_id FK, event_id FK nullable, type, message, read)
(none) *---* AUDIT_LOGS    (id PK, actor_id, event_id, action, details, created_at)
```

**Keys & constraints**
- Primary keys: surrogate integer `id` on every table.
- Foreign keys: `events.organizer_id -> users.id`, `rsvps.event_id -> events.id` (CASCADE),
  `rsvps.user_id -> users.id`, similarly for waitlist/announcements/notifications.
- Unique constraints: `users.email`, `(event_id, user_id)` on `rsvps` and `waitlist`,
  `(event_id, email)` on `invitations` - the database itself refuses duplicates.
- Indexes: `events(status, event_date)` for the "upcoming events" query,
  `rsvps(event_id, status)` for fast counts, `notifications(user_id, read, created_at)` for the inbox.
- Check constraint: `events.going_count between 0 and maximum_capacity` - a second, database-level
  guarantee that capacity can never be oversold even if application code has a bug.

**Relational vs NoSQL**: this schema is relational (SQLite locally / PostgreSQL in the cloud)
because RSVPs need strong relational guarantees (uniqueness, foreign keys, transactions) for
correct capacity control. A document database (Firestore/MongoDB) can implement the same
design using subcollections for RSVPs and a Firestore transaction in place of `SELECT ... FOR UPDATE`.

## Real-time architecture

```
Attendee A ─┐
Attendee B ─┤ WebSocket/SSE            Cloud API (FastAPI)        Cloud Database
Attendee C ─┼──────────────────►  validates + writes  ───────►  (SQLite/PostgreSQL)
            │                              │
Organizer  ◄┘  live counts pushed          ▼
 Dashboard     ◄────────────────  RealtimeHub.publish("event:<id>", counts)
```

Flow for one RSVP:
`POST /rsvp -> validate -> DB transaction (atomic seat claim) -> commit -> hub.publish -> every
subscribed WebSocket/SSE client receives new counts instantly -> dashboard re-renders, no refresh.`

See `backend/services/rsvp_service.py` docstring for the full concurrency/race-condition explanation
and `realtime/realtime_service.py` for the WebSocket/SSE hub implementation.
