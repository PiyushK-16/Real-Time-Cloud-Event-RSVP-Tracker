# Resume, LinkedIn & Interview Preparation

## A. Resume bullet points (3)

- Built a real-time cloud event RSVP platform (FastAPI, SQLAlchemy, WebSockets) enforcing
  concurrency-safe capacity control via atomic database transactions, verified by an automated
  test simulating simultaneous "last seat" requests.
- Designed a relational schema with database-level uniqueness and check constraints (one RSVP per
  user per event, capacity never exceeded) and a FIFO waitlist with automatic promotion.
- Implemented JWT-based authentication with role-based authorization (attendee/organizer/admin),
  a WebSocket/SSE real-time layer, and 28 automated tests covering auth, RSVP logic, and failure
  handling; documented free-tier and AWS deployment paths.

## B. Two-line resume project description

Real-Time Cloud-Based Event Planning & RSVP Tracker - a FastAPI + WebSocket platform where
organizers manage capacity-limited events and attendee RSVPs update every dashboard live, with
provably race-condition-safe seat allocation and a FIFO waitlist.

## C. Professional LinkedIn project description

I built a real-time, cloud-oriented event management platform as a Cloud Computing course
project: organizers publish events with a maximum capacity, and attendees RSVP Going/Maybe/Not
Going with changes reflected on every connected dashboard instantly via WebSockets. The part I'm
most proud of is the concurrency handling - I implemented an atomic conditional database update
(rather than a naive check-then-write) to guarantee an event can never be oversold, even when many
users try to claim the last seat at once, and backed that guarantee with an automated test. The
project also covers JWT authentication, role-based authorization, a FIFO waitlist, in-app
notifications, an analytics dashboard, and a documented deployment path to free-tier and
enterprise cloud infrastructure.

## D. Technical skills demonstrated

Python, FastAPI, SQLAlchemy (ORM + raw atomic SQL), relational schema design, database transactions
& concurrency control, JWT authentication, role-based access control, REST API design, WebSockets &
Server-Sent Events, event-driven architecture, automated testing (pytest), CI (GitHub Actions),
cloud deployment (Render/Railway, AWS reference architecture), and secure secrets management.

## E. GitHub repository description

"Real-time cloud-based event planning and RSVP platform featuring event management, live RSVP
tracking, cloud authentication, capacity control, notifications, analytics, and scalable cloud
architecture."

---

## Interview Preparation - 10 Questions & Answers

**1. Explain your project.**
It's a real-time event RSVP platform. Organizers create events with a maximum capacity; attendees
RSVP Going, Maybe, or Not Going, and can change their response anytime. Every RSVP change is
pushed live to the organizer's dashboard over a WebSocket, so counts update without a page
refresh. The core engineering challenge I focused on was making sure the event can never be
oversold, even if many people try to claim the last seat at the same time - I solved that with an
atomic database update instead of a naive check-then-write, and I wrote a test that proves it.

**2. What cloud computing concepts does this project demonstrate, and where?**
Cloud database (SQLite locally, PostgreSQL in the cloud, same code), authentication and
role-based authorization, REST APIs, real-time communication via WebSockets and SSE, an
event-driven design (an RSVP commit publishes an event that fans out to subscribers), environment-
variable-based configuration and secrets management, structured logging and health-check
monitoring endpoints, and a documented CI/CD pipeline and deployment path to both free-tier PaaS
and an enterprise AWS architecture.

**3. How does real-time communication work in your app, and why did you choose that approach?**
I implemented an in-process publish/subscribe hub. When an RSVP is committed, the backend
publishes a snapshot of the event's counts to a channel named after the event ID; every WebSocket
connected to that event receives it immediately. I chose WebSockets as the primary channel because
they're full-duplex and low-latency, but I also implemented Server-Sent Events as a simpler
one-way alternative, and the frontend automatically falls back to polling if the WebSocket
connection drops, so the app degrades gracefully instead of breaking.

**4. Walk me through how your cloud database is structured.**
Seven core tables: users, events, RSVPs, waitlist, invitations, announcements, and notifications,
plus an audit log. The important design decision is a UNIQUE constraint on (event_id, user_id) in
both the RSVPs and waitlist tables - that means the database itself refuses a duplicate RSVP, so
I'm not relying solely on application logic to prevent that bug class.

**5. How does your REST API handle authentication and authorization?**
Authentication is a JWT issued at login, signed with a server-only secret, sent as a Bearer token.
Authorization is separate: every mutating endpoint re-checks, server-side, whether the calling
user's role and ownership actually permit the action - for example, only the organizer who created
an event (or an admin) can edit or cancel it. The client's claims about who it is are never
trusted beyond what the verified token says.

**6. Explain the RSVP logic and what happens when a user changes their response.**
An RSVP has a status: GOING, MAYBE, NOT_GOING, or WAITLISTED. POST creates a new RSVP, PUT updates
an existing one, DELETE cancels it. If a user switches away from GOING, their seat is released and
I run a waitlist rebalance in the same transaction, so the longest-waiting person is automatically
promoted if there's now room. Repeating the same RSVP twice is a no-op - I treat it as idempotent
so accidental double-clicks or retried requests never double-count.

**7. This is the one I'd expect to go deepest on: explain the race condition around capacity, and
how you fixed it.**
If you check "is there room?" and then separately write the new RSVP, two requests can both pass
the check before either one writes, and you oversell the event. I collapse the check and the write
into one atomic SQL statement: `UPDATE events SET going_count = going_count + 1 WHERE id = :id AND
going_count < maximum_capacity`. Only one of two simultaneous requests can actually increment the
row; the other gets `rowcount == 0` and I return "event full" to that user instead. On SQLite I
also serialize writers with `BEGIN IMMEDIATE`, and on PostgreSQL I take a row lock with `SELECT ...
FOR UPDATE` as a second layer. There's also a database CHECK constraint that going_count can never
exceed capacity, as a last-resort safety net. I wrote an automated test that fires two "last seat"
requests concurrently and asserts exactly one of them succeeds.

**8. How would this scale to a very popular event with 100,000 people trying to RSVP in five
minutes?**
The stateless API servers themselves can scale out behind a load balancer, and a CDN handles static
assets. The real bottleneck is that every GOING RSVP for the same event contends on that one
event's row - that's a classic database hot spot. I'd put a queue in front of writes to smooth the
burst, potentially shard the counter across several rows and sum them for display, and consider a
Redis atomic counter as a fast pre-check in front of the database transaction, which stays the
source of truth. I'd also move the real-time hub from in-process pub/sub to Redis Pub/Sub so
messages fan out correctly across multiple backend instances.

**9. What security measures does your app have?**
Passwords are hashed with PBKDF2-SHA256 with a per-user salt, never stored or logged in plaintext.
JWTs are short-lived and can be revoked on logout. Every request body is validated against a strict
schema before it touches the database, and all database queries are parameterized, so there's no
SQL injection surface. CORS is locked to specific origins, not a wildcard, and sensitive
configuration - the JWT secret, the database URL - comes from environment variables, never
hardcoded. I also log an audit trail of who did what to each event.

**10. What happens if the database or the real-time connection fails mid-RSVP?**
If anything fails inside the RSVP transaction, the whole thing rolls back - there's no partially
applied state. Transient database errors are retried with exponential backoff. If a client's
WebSocket disconnects, the frontend detects it and falls back to polling every few seconds, and on
any reconnect it requests a fresh snapshot rather than trusting whatever it last had in memory, so
it can't silently drift out of sync with the real counts in the database.
