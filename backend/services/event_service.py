"""Event management: createEvent, updateEvent, deleteEvent, cancelEvent, getEvent, getEvents, getUpcomingEvents."""
from datetime import datetime

from sqlalchemy import func, or_, select

from backend.models.entities import RSVP, Event, Invitation, User, Waitlist
from backend.services.common import audit
from backend.utils.errors import AppError, forbidden, not_found, validation
from backend.utils.time import utcnow
from cloud import notification_service as notifs
from realtime.realtime_service import hub


def _validate_schedule(event_date, start, end, deadline, *, creating: bool):
    if end <= start:
        raise validation("end_time must be after start_time")
    start_dt = datetime.combine(event_date, start)
    if creating and start_dt <= utcnow():
        raise validation("Event must start in the future")
    if deadline and deadline > start_dt:
        raise validation("registration_deadline must be on or before the event start")
    return start_dt


def get_event_or_404(db, event_id: int) -> Event:
    e = db.get(Event, event_id)
    if not e:
        raise not_found("Event")
    return e


def can_manage(event: Event, user: User) -> bool:
    return user.role == "admin" or (user.role == "organizer" and event.organizer_id == user.id)


def require_manage(event: Event, user: User):
    if not can_manage(event, user):
        raise forbidden("Only the organizer of this event can do that")


def visible_to(event: Event, user: User) -> bool:
    return event.status != "DRAFT" or can_manage(event, user)


def sync_completed(db):
    """Lazily flip finished events to COMPLETED (a scheduled job does this in production)."""
    now = utcnow()
    rows = db.execute(select(Event).where(Event.status.in_(("PUBLISHED", "FULL")))).scalars().all()
    changed = False
    for e in rows:
        if datetime.combine(e.event_date, e.end_time) < now:
            e.status = "COMPLETED"
            changed = True
    if changed:
        db.commit()


def create_event(db, organizer: User, data) -> Event:
    start_dt = _validate_schedule(data.event_date, data.start_time, data.end_time, data.registration_deadline, creating=True)
    if not (data.venue or data.online_link):
        raise validation("Provide a venue or an online_link")
    e = Event(organizer_id=organizer.id, event_name=data.event_name.strip(), description=data.description,
              event_type=data.event_type, event_date=data.event_date, start_time=data.start_time,
              end_time=data.end_time, venue=data.venue, online_link=data.online_link,
              maximum_capacity=data.maximum_capacity, registration_deadline=data.registration_deadline or start_dt,
              status="PUBLISHED" if data.publish else "DRAFT", going_count=0)
    db.add(e)
    db.flush()
    audit(db, organizer.id, e.id, "EVENT_CREATED", name=e.event_name)
    db.commit()
    return e


def list_events(db, user: User, *, scope="upcoming", mine=False, q=None, event_type=None, limit=50, offset=0):
    sync_completed(db)
    stmt = select(Event)
    if mine:
        stmt = stmt.where(Event.organizer_id == user.id)
    elif user.role != "admin":
        stmt = stmt.where(Event.status != "DRAFT")
    if scope == "upcoming":
        stmt = stmt.where(Event.status.in_(("PUBLISHED", "FULL")), Event.event_date >= utcnow().date())
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Event.event_name).like(like), func.lower(Event.description).like(like)))
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    stmt = stmt.order_by(Event.event_date, Event.start_time).limit(min(limit, 100)).offset(offset)
    return db.execute(stmt).scalars().all()


def update_event(db, event_id: int, user: User, data) -> Event:
    from backend.services import rsvp_service
    e = get_event_or_404(db, event_id)
    require_manage(e, user)
    if e.status in ("CANCELLED", "COMPLETED"):
        raise AppError(409, "EVENT_CLOSED", f"A {e.status.lower()} event cannot be edited")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(e, k) for k in changes}
    date_, st, en = changes.get("event_date", e.event_date), changes.get("start_time", e.start_time), changes.get("end_time", e.end_time)
    deadline = changes.get("registration_deadline", e.registration_deadline)
    _validate_schedule(date_, st, en, deadline, creating=False)
    if "maximum_capacity" in changes and changes["maximum_capacity"] < e.going_count:
        raise validation(f"Capacity cannot be lower than current GOING count ({e.going_count})")
    for k, v in changes.items():
        setattr(e, k, v)
    if not (e.venue or e.online_link):
        raise validation("Provide a venue or an online_link")
    db.flush()
    pending = []
    place_changed = any(k in changes and changes[k] != old[k] for k in ("venue", "online_link"))
    time_changed = any(k in changes and changes[k] != old[k] for k in ("event_date", "start_time", "end_time"))
    audience = db.execute(select(RSVP.user_id).where(RSVP.event_id == e.id,
                          RSVP.status.in_(("GOING", "MAYBE", "WAITLISTED")))).scalars().all()
    for uid in audience:
        if place_changed:
            pending.append(notifs.notify(db, uid, e.id, "VENUE_CHANGE", f"Venue/link updated for '{e.event_name}'"))
        if time_changed:
            pending.append(notifs.notify(db, uid, e.id, "TIME_CHANGE",
                                         f"New time for '{e.event_name}': {e.event_date} {e.start_time:%H:%M}-{e.end_time:%H:%M}"))
    if "maximum_capacity" in changes:
        pending += rsvp_service.rebalance(db, e)  # bigger capacity may free seats for the waitlist
    audit(db, user.id, e.id, "EVENT_UPDATED", fields=list(changes))
    snap = rsvp_service.snapshot(db, e)
    db.commit()
    notifs.push(pending)
    hub.publish_threadsafe(f"event:{e.id}", {"type": "rsvp_update", **snap})
    return e


def publish_event(db, event_id: int, user: User) -> Event:
    e = get_event_or_404(db, event_id)
    require_manage(e, user)
    if e.status != "DRAFT":
        raise AppError(409, "NOT_DRAFT", "Only draft events can be published")
    e.status = "PUBLISHED"
    audit(db, user.id, e.id, "EVENT_PUBLISHED")
    db.commit()
    return e


def cancel_event(db, event_id: int, user: User) -> Event:
    from backend.services import rsvp_service
    e = get_event_or_404(db, event_id)
    require_manage(e, user)
    if e.status == "CANCELLED":
        return e  # idempotent
    if e.status == "COMPLETED":
        raise AppError(409, "EVENT_CLOSED", "A completed event cannot be cancelled")
    e.status = "CANCELLED"
    audience = db.execute(select(RSVP.user_id).where(RSVP.event_id == e.id, RSVP.status != "NOT_GOING")).scalars().all()
    pending = [notifs.notify(db, uid, e.id, "EVENT_CANCELLED", f"'{e.event_name}' has been cancelled") for uid in audience]
    audit(db, user.id, e.id, "EVENT_CANCELLED", notified=len(audience))
    snap = rsvp_service.snapshot(db, e)
    db.commit()
    notifs.push(pending)
    hub.publish_threadsafe(f"event:{e.id}", {"type": "rsvp_update", **snap})
    return e


def delete_event(db, event_id: int, user: User):
    e = get_event_or_404(db, event_id)
    require_manage(e, user)
    has_rsvps = db.execute(select(func.count()).select_from(RSVP).where(RSVP.event_id == e.id)).scalar()
    if has_rsvps:
        raise AppError(409, "HAS_RSVPS", "Events with RSVPs cannot be deleted; cancel the event instead")
    for model in (Invitation, Waitlist):
        for row in db.execute(select(model).where(model.event_id == e.id)).scalars():
            db.delete(row)
    audit(db, user.id, e.id, "EVENT_DELETED", name=e.event_name)
    db.delete(e)
    db.commit()
