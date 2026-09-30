# GitHub Upload Strategy

**Repository name**: `Real-Time-Cloud-Event-RSVP-Tracker`

**Description**: "Real-time cloud-based event planning and RSVP platform featuring event
management, live RSVP tracking, cloud authentication, capacity control, notifications, analytics,
and scalable cloud architecture."

**Topics**: `cloud-computing`, `event-management`, `rsvp`, `realtime`, `python`, `fastapi`,
`websocket`, `cloud-database`, `rest-api`, `serverless`, `authentication`

## Commands

```bash
git init
git add .
git commit -m "Initialize real-time cloud event tracker"
git branch -M main
git remote add origin <repository-url>
git push -u origin main
```

## Suggested commit sequence (also usable as a 14-day proof-of-work history)

| Day | Focus | Files created | Commit message | Screenshot proves |
|---|---|---|---|---|
| 1 | Architecture + repo scaffold | `docs/architecture.md`, folder structure, `.gitignore`, `requirements.txt` | "Create cloud event platform architecture" | #1, #2 |
| 2 | Authentication & roles | `cloud/auth_service.py`, `backend/middleware/auth.py`, `backend/routes/auth_routes.py` | "Implement authentication and roles" | #3, #4 |
| 3 | Event management module | `backend/models/entities.py`, `backend/services/event_service.py`, `backend/routes/event_routes.py` | "Add event management module" | #6, #7 |
| 4 | RSVP workflow | `backend/services/rsvp_service.py`, `backend/routes/rsvp_routes.py` | "Implement RSVP workflow" | #10, #11 |
| 5 | Cloud database | `cloud/database_service.py`, `.env.example`, `requirements-cloud.txt` | "Integrate cloud database" | #14 |
| 6 | Real-time RSVP updates | `realtime/realtime_service.py` | "Add real-time RSVP updates" | #12, #13 |
| 7 | Capacity-safe transactions | atomic `claim_seat`/`release_seat` in `rsvp_service.py`, `tests/test_rsvp.py` race test | "Implement capacity-safe transactions" | #15, #16, #21 |
| 8 | Waitlist | `Waitlist` model, `rsvp_service.rebalance` | "Add optional waitlist" | #17 |
| 9 | Organizer dashboard | `frontend/public/*`, `backend/routes/analytics_routes.py` (summary) | "Build organizer dashboard" | #5, #8, #9 |
| 10 | Announcements & notifications | `backend/services/announcement_service.py`, `cloud/notification_service.py` | "Add announcements and notifications" | #18, #19 |
| 11 | Event analytics | `analytics/event_analytics.py` | "Implement event analytics" | #20 |
| 12 | Security controls | `backend/middleware/rate_limit.py`, `docs/security.md` | "Add security controls" | #22 |
| 13 | Automated tests | full `tests/` suite, `.github/workflows/ci.yml` | "Add automated tests" | #23 |
| 14 | Deployment + docs | `render.yaml`, `Procfile`, `docs/deployment.md`, final `README.md` | "Deploy application to cloud" / "Complete README and documentation" | #24, #25, #26, #27, #28 |

Each day: implement the listed files, run `pytest`, commit with the given message, capture the
listed screenshot(s) into `screenshots/` using the filenames in
[`screenshot_checklist.md`](screenshot_checklist.md), and push.
