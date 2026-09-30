# Real-Time Cloud-Based Event Planning & RSVP Tracker

A full-stack Cloud Computing course project: organizers create and manage events, attendees RSVP
(Going / Maybe / Not Going), and every RSVP change is pushed to every connected dashboard **in
real time**, with concurrency-safe capacity control, a FIFO waitlist, notifications, and analytics.

## Overview

Think of it as a small, self-hosted alternative to Eventbrite/Meetup, built specifically to
demonstrate cloud computing concepts end-to-end: cloud database, authentication, REST APIs,
real-time communication, role-based authorization, scalability, security, and deployment.

## Problem Statement

Manually coordinating an event's attendee list by email or spreadsheet doesn't scale: organizers
can't see live headcounts, attendees can't easily update their response, and there's no single
source of truth once more than a handful of people are involved.

## Objectives

- Let an organizer create, edit, publish, and cancel events with a maximum capacity.
- Let an attendee discover events and RSVP Going / Maybe / Not Going, updating anytime.
- Reflect every RSVP change on the organizer's dashboard **instantly**, without a manual refresh.
- Never oversell a capacity-limited event, even under simultaneous requests for the last seat.
- Demonstrate real cloud computing concepts (see table below), not just a CRUD website.

## Features

**Organizer**: create/edit/cancel events, set capacity & deadline, view live RSVP counts and
analytics, manage a FIFO waitlist, send announcements and reminders, view the attendee list.

**Attendee**: register/login, browse/search upcoming events, RSVP and change RSVP anytime, join a
waitlist when full, see event announcements, get in-app notifications, view "My RSVPs".

## Industry Relevance

The same organizer/attendee + live-RSVP pattern powers conferences, college fests, corporate
town halls, webinars, workshops, meetups, training programs, weddings, community events,
ticketing platforms, and professional networking events. Business benefits: centralized event
management, live attendance tracking, remote accessibility, less manual coordination, automated
RSVP handling, scalable attendee management, real-time visibility, and built-in analytics.

## Cloud Computing Concepts Demonstrated

See [`docs/cloud_concepts_mapping.md`](docs/cloud_concepts_mapping.md) for a full table mapping
every required concept (SaaS/PaaS/IaaS, cloud & real-time databases, auth, RBAC, REST, WebSockets,
SSE, serverless, event-driven architecture, scalability, elasticity, HA, load balancing, API
gateway, CDN, caching, env vars, secrets, logging, monitoring, backup, CI/CD, deployment) to the
exact file or design decision that implements it.

## Real-Time Architecture

```
Organizer
   |  creates event
   v
Cloud Database  --publish-->  Attendees view event
                                    |  selects RSVP (Going/Maybe/Not Going)
                                    v
                              Cloud Backend (FastAPI)
                                    |  atomic capacity-safe transaction
                                    v
                              RSVP stored in Cloud Database
                                    |  real-time event emitted
                                    v
                    WebSocket/SSE hub  -->  Organizer Dashboard
                                             (Going/Maybe/Not-Going counters update live)
```

Three real-time approaches are explained and compared in
[`backend/services/rsvp_service.py`](backend/services/rsvp_service.py) and implemented in
[`realtime/realtime_service.py`](realtime/realtime_service.py): **polling** (frontend fallback),
**Server-Sent Events** (`GET /api/events/{id}/stream`), and **WebSockets**
(`/ws/events/{id}`, `/ws/me`) - the primary implementation used by the bundled frontend.

## Technology Stack

This repo implements **Option A (local) fully working today**, structured so it upgrades directly
into **Option B (recommended cloud)** by changing only `DATABASE_URL` and a couple of environment
variables - no code rewrite needed.

| | Option A - Local (implemented here) | Option B - Recommended Cloud | Option C - Advanced Cloud |
|---|---|---|---|
| Frontend | Plain HTML/CSS/JS (`frontend/public`) | React | React / Next.js |
| Backend | Python FastAPI | Python FastAPI (same code) | FastAPI / serverless functions |
| Database | SQLite | Supabase/Neon PostgreSQL | AWS RDS / DynamoDB |
| Auth | Custom JWT (`cloud/auth_service.py`) | Same, or Supabase Auth | Cognito / Firebase Auth |
| Real-time | In-process WebSocket/SSE hub | Same hub, or Supabase Realtime | API Gateway WebSocket API |
| Deployment | `uvicorn` on your machine | Render/Railway free tier | AWS/Azure/GCP managed services |
| Cost | Free | Free tier | Pay-as-you-go |
| Best for | Learning & grading demo | A strong GitHub portfolio piece | Interview deep-dives on AWS |

**Recommendation for a student**: build and demo on Option A (zero cost, zero setup risk), deploy
once to Option B for a live link on your resume, and study Option C's architecture diagram for
interviews - you don't need to actually run it to explain it well.

## User Roles

| Permission | Attendee | Organizer | Admin (optional) |
|---|:---:|:---:|:---:|
| Register / login | Y | Y | Y |
| Browse & RSVP to events | Y | Y | Y |
| View own RSVPs / notifications | Y | Y | Y |
| Create / edit / cancel own events | - | Y | Y (any event) |
| View attendee list & analytics for own events | - | Y | Y (any event) |
| Send announcements / reminders | - | Y (own events) | Y |
| Manage users / view platform stats | - | - | Y |

## Event Management

Fields, statuses (`DRAFT -> PUBLISHED -> FULL -> COMPLETED`, or `CANCELLED`), and validation rules
are defined in [`backend/models/entities.py`](backend/models/entities.py) and enforced in
[`backend/services/event_service.py`](backend/services/event_service.py) (date/time validity,
capacity vs. current GOING count, registration deadline, organizer-only permissions).

## RSVP System

`GOING / MAYBE / NOT_GOING / WAITLISTED`, one active RSVP per user per event enforced by a
database `UNIQUE(event_id, user_id)` constraint (not just application code). See
[`backend/services/rsvp_service.py`](backend/services/rsvp_service.py).

## Capacity Management & Concurrency (interview-important section)

```
Event capacity = 100, current going_count = 99.
User A and User B both click "Going" at almost the same instant.
```

A naive check-then-write (`if going_count < capacity: insert`) has a gap between the read and the
write, where both requests can pass the check before either writes - overselling the event. This
project closes that gap with:

1. **One atomic conditional UPDATE** instead of a separate check + insert:
   `UPDATE events SET going_count = going_count + 1 WHERE id=:id AND going_count < maximum_capacity`
   - only one of two simultaneous requests can affect a row, the other sees `rowcount == 0`.
2. **Serialized transactions**: SQLite uses `BEGIN IMMEDIATE` (single writer); PostgreSQL uses a
   `SELECT ... FOR UPDATE` row lock on the event.
3. **A database CHECK constraint** (`going_count BETWEEN 0 AND maximum_capacity`) as a final
   backstop even if application code had a bug.

`tests/test_rsvp.py::test_simultaneous_final_seat_requests` proves exactly one of two simultaneous
"last seat" requests succeeds.

## Waitlist

FIFO, ordered by the waitlist row's auto-increment `id`. When a GOING attendee cancels, the
longest-waiting user is automatically promoted and notified (`rsvp_service.rebalance`).

## Cloud Database

ER diagram, keys, indexes, and relational-vs-NoSQL discussion:
[`docs/architecture.md`](docs/architecture.md).

## Authentication & Authorization

PBKDF2-hashed passwords, JWT access tokens with revocation-on-logout, and server-side role checks
on every mutating endpoint (a client can never claim a role or ownership it doesn't have). Details
in [`docs/security.md`](docs/security.md).

## Notifications

In-app notifications for RSVP confirmation, event reminders, venue/time changes, cancellations,
waitlist promotion, and organizer announcements - persisted to the database and pushed instantly
over the real-time hub. Email/SMS/push are pluggable hooks in
[`cloud/notification_service.py`](cloud/notification_service.py).

## Analytics

Response rate, capacity utilization, RSVP conversion rate, and RSVP growth over time - see
[`analytics/event_analytics.py`](analytics/event_analytics.py). Example:
`Invited = 500, Responded = 350 -> Response Rate = 350/500*100 = 70%`.

## REST APIs

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/api/register` | - | Create an account |
| POST | `/api/login` | - | Get a JWT access token |
| POST | `/api/logout` | Bearer | Revoke the current token |
| GET | `/api/me` | Bearer | Current user profile |
| POST | `/api/events` | Organizer/Admin | Create an event |
| GET | `/api/events` | Bearer | List events (search/filter) |
| GET | `/api/events/{id}` | Bearer | Event detail + live counts |
| PUT | `/api/events/{id}` | Organizer of event | Update an event |
| POST | `/api/events/{id}/publish` | Organizer of event | Publish a draft |
| POST | `/api/events/{id}/cancel` | Organizer of event | Cancel an event |
| DELETE | `/api/events/{id}` | Organizer of event | Delete (only if no RSVPs) |
| POST | `/api/events/{id}/rsvp` | Bearer | Create an RSVP |
| PUT | `/api/events/{id}/rsvp` | Bearer | Update your RSVP |
| DELETE | `/api/events/{id}/rsvp` | Bearer | Cancel your RSVP |
| GET | `/api/events/{id}/rsvps` | Organizer of event | List attendees |
| GET | `/api/rsvps/me` | Bearer | Your RSVPs across events |
| GET | `/api/events/{id}/analytics` | Organizer of event | Event analytics |
| GET | `/api/organizer/summary` | Organizer/Admin | Dashboard summary |
| POST/GET | `/api/events/{id}/announcements` | mixed | Create/list announcements |
| POST | `/api/events/{id}/invite` | Organizer of event | Invite by email |
| POST | `/api/events/{id}/remind` | Organizer of event | Send reminders |
| GET | `/api/notifications` | Bearer | List your notifications |
| PUT | `/api/notifications/{id}/read` | Bearer | Mark one read |
| WS | `/ws/events/{id}?token=` | token query param | Live RSVP counts |
| WS | `/ws/me?token=` | token query param | Live personal notifications |
| GET | `/api/events/{id}/stream` | token query param | SSE alternative to the WebSocket |
| GET | `/healthz` / `/readyz` | - | Liveness / readiness probes |

Every endpoint returns errors as `{"error": {"code": "...", "message": "..."}}` with an
appropriate HTTP status (400/401/403/404/409/422/429). Interactive docs: `GET /docs` (Swagger UI,
provided automatically by FastAPI).

## Folder Structure

```
Real-Time-Cloud-Event-RSVP-Tracker/
├── backend/            FastAPI app: routes, models, services, middleware, schemas, config
├── realtime/           WebSocket/SSE pub-sub hub
├── cloud/              Database, auth, and notification "cloud services"
├── analytics/          Pure analytics calculations
├── frontend/public/    Plain HTML/CSS/JS demo UI (Option A)
├── tests/              28 automated pytest tests
├── sample_data/        seed.py - dummy users & events
├── docs/               architecture, cloud-concepts mapping, scalability, security, deployment
├── reports/            Full project report, resume/LinkedIn content, interview prep
├── screenshots/        Proof-of-work screenshot checklist (see docs)
├── requirements.txt / requirements-cloud.txt
├── .env.example        Every configurable value, no secret ever hardcoded
└── render.yaml, Procfile, .github/workflows/ci.yml   Deployment & CI
```

## Installation (local)

```bash
git clone <your-repo-url>
cd Real-Time-Cloud-Event-RSVP-Tracker
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # edit JWT_SECRET at minimum
python sample_data/seed.py                              # optional: dummy data
uvicorn backend.app:app --reload
```

Open **http://127.0.0.1:8000** - the bundled frontend and the API are served from the same process.
Interactive API docs: **http://127.0.0.1:8000/docs**.

## Environment Variables

See [`.env.example`](.env.example) for the full list (`DATABASE_URL`, `JWT_SECRET`,
`JWT_EXPIRE_MINUTES`, `CORS_ORIGINS`, rate limits, optional admin bootstrap credentials). Nothing
sensitive is ever hardcoded in source.

## Local / Multi-User Real-Time Simulation

1. Run `uvicorn backend.app:app --reload` and open `http://127.0.0.1:8000` in **three browser
   windows** (or one normal + two incognito, so sessions don't collide).
2. Window 1: register as an **organizer**, create "Cloud Computing Workshop" with capacity 2, and
   open its event page (this is your live dashboard).
3. Window 2: register as attendee A, open the same event, click **Going** - Window 1's counter
   updates to `1` immediately, no refresh.
4. Window 3: register as attendee B, click **Maybe**, then change it to **Going** - Window 1
   updates twice, live, to `2`.
5. In Window 3, try to RSVP a third attendee as **Going** - the event is now full
   (`EVENT_FULL`, `can_join_waitlist: true`); joining the waitlist and then Window 2 cancelling
   demonstrates automatic FIFO promotion.
6. In Window 1, post an announcement - Windows 2 and 3 see it appear under the event and in
   **Notifications**.

This is the strongest single piece of proof that the system is genuinely real-time - screenshot
all three windows side by side (see the screenshot checklist below).

## Cloud Deployment

Two full paths (free-tier PaaS + Supabase/Neon, and an enterprise AWS/Azure/GCP architecture) are
documented in [`docs/deployment.md`](docs/deployment.md).

## Testing

28 automated tests (`pytest`, see [`tests/`](tests/)) cover registration/login, event CRUD and
authorization, the full RSVP lifecycle, duplicate-RSVP prevention, capacity enforcement, the FIFO
waitlist, **the simultaneous-final-seat race condition**, announcements, notifications, analytics
calculations, idempotency (double-click safety), expired tokens, and cancelled-event rejection.

```bash
pytest              # run everything
pytest -v tests/test_rsvp.py   # just the RSVP/concurrency suite
```

## Security

See [`docs/security.md`](docs/security.md) - authentication, RBAC, HTTPS, encryption, input
validation, injection/XSS prevention, CORS, rate limiting, secrets management, audit logs, and
specifically **why the frontend can never set RSVP counts directly** (the database is always the
source of truth).

## Scalability

See [`docs/scalability.md`](docs/scalability.md) - 100 to 1,000,000 users, the flash-crowd
scenario (100k RSVPs in 5 minutes), database hot spots, and how to fix them (queues, counter
sharding, Redis, CDN, autoscaling, WebSocket fan-out via Redis Pub/Sub).

## Failure Handling

- **Idempotent RSVPs**: repeating the same RSVP (double-click, retried request) is a no-op, proven
  by `tests/test_failure_handling.py::test_double_click_rsvp_is_idempotent`.
- **Database transaction + rollback**: any exception inside a service function rolls back the
  whole transaction - no half-applied RSVP.
- **Transient DB errors**: `cloud/database_service.py::run_with_retry` retries with exponential
  backoff.
- **WebSocket disconnects**: the frontend (`api.js::connectEventRealtime`) detects the drop and
  falls back to 4-second polling automatically; on reconnect it re-fetches a full snapshot so it
  never silently drifts from the true counts.
- **Expired/invalid tokens**: return a clear `401 TOKEN_EXPIRED` / `INVALID_TOKEN`, prompting
  re-login rather than a confusing generic failure.

## Screenshots

See [`docs/screenshot_checklist.md`](docs/screenshot_checklist.md) for the 28-item checklist and
professional filenames to use when capturing proof-of-work for the report/GitHub/LinkedIn.

## Results

A working end-to-end system: organizers publish capacity-limited events; attendees RSVP from
multiple simultaneous sessions; every dashboard updates live; the last-seat race condition is
provably safe (automated test); a FIFO waitlist auto-promotes on cancellation; 28/28 automated
tests pass.

## Limitations

- The bundled real-time hub is single-process (fine for a course demo / small deployment); scaling
  to multiple backend instances needs Redis Pub/Sub or a managed realtime service (documented).
- Notifications are in-app only by default; email/SMS need a provider key to activate.
- The bundled frontend is intentionally plain HTML/JS for zero build tooling - Option B/C swap in
  React without touching the backend.

## Future Improvements

Recurring events, calendar (ICS) export, QR-code check-in at the venue, paid ticketing, multi-day
events, and a push-notification channel (web push / FCM).

## Learning Outcomes

Building this project covers: relational schema design under concurrency constraints, atomic
database operations vs. race conditions, JWT authentication & RBAC from scratch, real-time
communication (WebSockets/SSE) design trade-offs, REST API design and error handling, automated
testing of concurrent behavior, and the free-tier cloud deployment path a student can actually
afford.

## Author

Student project for a Cloud Computing course. See [`reports/`](reports/) for the full project
report, resume/LinkedIn bullet points, and interview preparation Q&A.
