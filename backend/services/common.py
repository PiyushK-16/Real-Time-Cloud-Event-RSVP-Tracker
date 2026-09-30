"""Shared helpers: audit logging and JSON serializers."""
import json

from backend.models.entities import AuditLog, Event, User
from backend.utils.time import iso, utcnow


def audit(db, actor_id, event_id, action, **details):
    db.add(AuditLog(actor_id=actor_id, event_id=event_id, action=action,
                    details=json.dumps(details, default=str), created_at=utcnow()))


def user_out(u: User) -> dict:
    return {"user_id": u.id, "email": u.email, "name": u.name, "role": u.role, "is_active": u.is_active,
            "created_at": iso(u.created_at)}


def event_out(e: Event, counts: dict | None = None, my_rsvp: str | None = None) -> dict:
    d = {
        "event_id": e.id, "organizer_id": e.organizer_id,
        "organizer_name": e.organizer.name if e.organizer else None,
        "event_name": e.event_name, "description": e.description, "event_type": e.event_type,
        "event_date": e.event_date.isoformat(), "start_time": e.start_time.isoformat(timespec="minutes"),
        "end_time": e.end_time.isoformat(timespec="minutes"), "venue": e.venue, "online_link": e.online_link,
        "maximum_capacity": e.maximum_capacity, "registration_deadline": iso(e.registration_deadline),
        "status": e.status, "going_count": e.going_count,
        "available_seats": max(e.maximum_capacity - e.going_count, 0),
        "created_at": iso(e.created_at), "updated_at": iso(e.updated_at),
    }
    if counts is not None:
        d["counts"] = counts
    if my_rsvp is not None:
        d["my_rsvp"] = my_rsvp
    return d
