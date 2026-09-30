# Project Report: Real-Time Cloud-Based Event Planning & RSVP Tracker

## Abstract
This project implements a cloud-based platform that lets organizers publish events with a fixed
capacity and lets attendees RSVP Going, Maybe, or Not Going, with every response reflected on the
organizer's dashboard in real time. It demonstrates, in one working codebase, the core concepts of
a Cloud Computing course: cloud databases, authentication and role-based authorization, REST API
design, real-time communication (WebSockets/SSE), concurrency-safe transactions, scalable
architecture, security, automated testing, and cloud deployment.

## Introduction
Event coordination via spreadsheets or email does not scale past a handful of attendees: there is
no live headcount, no single source of truth, and no way to safely cap attendance. This project
builds a small but complete cloud-native alternative, deliberately scoped so every layer (database,
backend, real-time channel, frontend) can be explained and defended in an interview.

## Problem Statement
Given an event with a maximum capacity, allow many attendees to RSVP concurrently without ever
overselling the event, while giving the organizer a live, accurate view of who is coming.

## Objectives
1. CRUD event management with organizer-only permissions.
2. A correct, idempotent RSVP workflow (Going/Maybe/Not Going, with cancel and update).
3. Real-time propagation of RSVP changes to every connected client.
4. Concurrency-safe capacity enforcement, proven under simultaneous requests.
5. A FIFO waitlist with automatic promotion.
6. Role-based authorization, notifications, analytics, and automated tests.
7. A documented path to free-tier and enterprise cloud deployment.

## Existing System
Manual coordination (spreadsheets, email threads, messaging groups) or generic form tools with no
live capacity control, no organizer dashboard, and no safe concurrent-write guarantees.

## Proposed System
A FastAPI backend backed by a relational database (SQLite locally, PostgreSQL in the cloud), a
JWT-based auth layer, a WebSocket/SSE real-time hub, and a lightweight HTML/JS frontend - all in
one deployable unit, with a documented upgrade path to a React frontend and a managed cloud stack.

## Industry Relevance
The organizer/attendee + live-RSVP pattern generalizes directly to conferences, college fests,
corporate events, webinars, workshops, meetups, training programs, weddings, community events,
ticketing platforms, and professional networking events - all of which need centralized
management, live attendance tracking, remote accessibility, and automated RSVP handling.

## Cloud Computing Concepts
See `docs/cloud_concepts_mapping.md` for the full concept-to-implementation table (SaaS/PaaS/IaaS,
cloud database, real-time database, auth, RBAC, REST, WebSockets, SSE, serverless, event-driven
architecture, cloud functions, scalability, elasticity, HA, load balancing, API gateway, CDN,
caching, environment variables, secrets management, logging, monitoring, backup, CI/CD, deployment).

## Real-Time Computing Concepts
Three approaches were evaluated: **polling** (simple, higher latency and load), **Server-Sent
Events** (simple one-way push over plain HTTP, works well behind most proxies), and **WebSockets**
(full-duplex, lowest latency, used as the primary channel here with polling as an automatic
fallback). See `realtime/realtime_service.py`.

## Technology Stack
Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, PyJWT, Pydantic v2. Database: SQLite (local) /
PostgreSQL (cloud). Frontend: HTML/CSS/vanilla JS (Option A), with documented React/Next.js
upgrade paths (Options B/C). Testing: pytest. CI: GitHub Actions. Deployment: Render/Railway
(free tier) or AWS/Azure/GCP (enterprise).

## Architecture
See `docs/architecture.md` for the full ER diagram and real-time data-flow diagram.

## Database Design
Seven core tables (`users`, `events`, `rsvps`, `waitlist`, `invitations`, `announcements`,
`notifications`) plus `audit_logs` and `revoked_tokens`. Primary keys are surrogate integers;
foreign keys enforce referential integrity; unique constraints (`event_id, user_id`) prevent
duplicate RSVPs at the database level, not just in application code; a CHECK constraint keeps
`going_count` within `[0, maximum_capacity]` as a final safety net.

## Authentication
Passwords are hashed with PBKDF2-SHA256 (200,000 iterations, per-user salt); sessions are stateless
JWTs with a revocation list checked on every request, so logout is immediate and irreversible for
that token.

## Event Management
Organizers create events in `DRAFT` or publish immediately; capacity, schedule, and registration
deadline are validated server-side; only the owning organizer (or an admin) may edit or cancel.

## RSVP Workflow
`POST` creates, `PUT` updates, `DELETE` cancels a user's own RSVP; repeating the same status is a
no-op (idempotent); switching away from `GOING` releases the seat and triggers waitlist rebalancing.

## Real-Time Updates
Every committed RSVP change publishes a snapshot (`counts`, `going_count`, `available_seats`,
`event_status`) to a per-event channel; all subscribed WebSocket/SSE clients receive it
immediately, and a freshly (re)connecting client always gets a full snapshot first so it can never
silently drift out of sync.

## Capacity Management & Concurrency Control
The classic race condition - a separate "is there room?" read followed by a write - is closed by
replacing both steps with one atomic conditional `UPDATE ... WHERE going_count < maximum_capacity`.
`rowcount == 1` means the seat was claimed; `rowcount == 0` means the event was already full by the
time this request's write reached the database, regardless of what it saw at read time. SQLite
serializes writers via `BEGIN IMMEDIATE`; PostgreSQL uses `SELECT ... FOR UPDATE` row locking. An
automated test issues two simultaneous "last seat" requests and asserts exactly one succeeds.

## Waitlist
A FIFO queue ordered by insertion order (auto-increment id); when a `GOING` attendee cancels, the
longest-waiting entry is promoted inside the same transaction that frees the seat.

## Notifications
RSVP confirmations, event reminders, venue/time changes, cancellations, waitlist promotions, and
organizer announcements are persisted and pushed over the real-time hub; a failed push never fails
the underlying business operation, since the row is already committed.

## Analytics
Response rate, capacity utilization, and RSVP conversion rate are computed as percentages of
invited/responded/capacity counts; RSVP growth over time is computed by grouping responses by day.

## API Design
A full resource-oriented REST API (see the README's endpoint table) with uniform error responses
(`{"error": {"code", "message"}}`) and appropriate HTTP status codes for every failure mode.

## Implementation
Backend organized as routes -> services -> models, with cross-cutting concerns (auth, rate
limiting, error handling) as FastAPI dependencies/middleware. The frontend is a small hash-router
single-page app calling the same REST API and subscribing to the WebSocket channel per event.

## Testing
28 automated `pytest` tests across authentication, event management, RSVP/concurrency, waitlist,
announcements/notifications, analytics, and failure handling; all passing (see `tests/`).

## Cloud Deployment
Documented in `docs/deployment.md`: a free-tier path (Render/Railway + Supabase/Neon PostgreSQL)
and an enterprise AWS reference architecture (CloudFront, API Gateway, Lambda/ECS, RDS, Cognito,
SNS/SES, CloudWatch), with Azure/GCP equivalents noted.

## Security
PBKDF2 password hashing, JWT with revocation, strict input validation via Pydantic, parameterized
queries (no SQL injection surface), CORS allow-listing, per-key rate limiting, environment-variable
secrets, and audit logging. Full discussion in `docs/security.md`.

## Scalability
Documented growth path from 100 to 1,000,000 users, the flash-crowd scenario for a single popular
event, the resulting database hot spot on that event's row, and mitigations (queueing, counter
sharding, Redis, CDN, autoscaling, Redis Pub/Sub for cross-instance real-time fan-out). See
`docs/scalability.md`.

## Failure Handling
Idempotent RSVP writes, transactional rollback on error, retry-with-backoff for transient database
errors, automatic WebSocket-to-polling fallback on disconnect, and explicit, actionable error codes
for expired/invalid tokens.

## Results
All 28 automated tests pass, including the concurrency-critical "simultaneous final seat" test.
Manual multi-browser testing confirms sub-second propagation of RSVP changes to the organizer
dashboard without a page refresh.

## Advantages
Free to run and demo end-to-end locally; the same code runs against a managed cloud database with
no changes; the concurrency model is provably correct rather than "probably fine"; the API is fully
documented and testable via `/docs`.

## Limitations
Single-process real-time hub (documented multi-instance upgrade path); in-app-only notifications by
default; a deliberately framework-free frontend for zero build tooling.

## Future Scope
Recurring events, calendar export, QR check-in, paid ticketing, multi-day events, push
notifications, and a React frontend rewrite (Option B) for a richer UI.

## Conclusion
The project demonstrates that a small, well-tested codebase can correctly implement the hardest
part of an RSVP system - safe concurrent capacity control - while still covering the full breadth
of cloud computing concepts expected of a course project, and remaining genuinely free to build,
run, test, and deploy as a student.
