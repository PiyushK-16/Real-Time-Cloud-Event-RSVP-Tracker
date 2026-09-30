"""Seed the local database with dummy/synthetic users and events for demos and screenshots.
Run:  python sample_data/seed.py
"""
import sys
from datetime import date, time, timedelta

sys.path.insert(0, ".")
from cloud import auth_service
from cloud.database_service import SessionLocal, init_db
from backend.models.entities import Event, RSVP, User
from backend.utils.time import utcnow

init_db()
db = SessionLocal()

USERS = [
    ("priya.organizer@example.com", "Priya Sharma", "organizer"),
    ("javier.organizer@example.com", "Javier Ruiz", "organizer"),
    ("admin@example.com", "Platform Admin", "admin"),
] + [(f"attendee{i}@example.com", f"Attendee {i}", "attendee") for i in range(1, 13)]

user_rows = {}
for email, name, role in USERS:
    u = User(email=email, name=name, password_hash=auth_service.hash_password("password123"), role=role)
    db.add(u)
    db.flush()
    user_rows[email] = u
print(f"Created {len(user_rows)} dummy users (all passwords: password123)")

org1, org2 = user_rows["priya.organizer@example.com"], user_rows["javier.organizer@example.com"]
today = utcnow().date()

events_def = [
    dict(organizer_id=org1.id, event_name="Cloud Computing Workshop", event_type="workshop",
        event_date=today + timedelta(days=7), start_time=time(10, 0), end_time=time(13, 0),
        venue="Engineering Auditorium", maximum_capacity=5, description="Hands-on session on serverless architecture."),
    dict(organizer_id=org1.id, event_name="Annual Tech Meetup", event_type="meetup",
        event_date=today + timedelta(days=14), start_time=time(18, 0), end_time=time(21, 0),
        online_link="https://meet.example.com/tech-meetup", maximum_capacity=3,
        description="Community meetup for cloud & distributed systems enthusiasts."),
    dict(organizer_id=org2.id, event_name="Career Fair 2026", event_type="career",
        event_date=today + timedelta(days=21), start_time=time(9, 0), end_time=time(17, 0),
        venue="Main Campus Hall", maximum_capacity=8, description="Meet recruiters from top tech companies."),
]
events = []
for d in events_def:
    e = Event(**d, registration_deadline=utcnow() + timedelta(days=5), status="PUBLISHED", going_count=0)
    db.add(e)
    db.flush()
    events.append(e)
print(f"Created {len(events)} dummy events")

attendees = [u for email, u in user_rows.items() if u.role == "attendee"]
from backend.services.rsvp_service import claim_seat
for i, e in enumerate(events):
    for j, a in enumerate(attendees):
        status = ["GOING", "MAYBE", "NOT_GOING"][(i + j) % 3]
        if status == "GOING":
            if not claim_seat(db, e.id):
                status = "MAYBE"  # event full in this demo pass, fall back
        db.add(RSVP(event_id=e.id, user_id=a.id, status=status))
db.commit()
print("Seed complete. Try logging in as priya.organizer@example.com / password123")
db.close()
