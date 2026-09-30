"""RSVP workflow, capacity control and FIFO waitlist.

THE RACE CONDITION (interview favourite)
    if going_count < capacity:      # 1. both users read 99 < 100  -> both pass
        insert RSVP / going += 1    # 2. both write               -> 101 people for 100 seats
Check and write are two separate steps, so two requests can interleave between them.

THE FIX (three layers, all used here)
 1. Atomic conditional UPDATE - the check and the increment are ONE statement:
        UPDATE events SET going_count = going_count + 1
         WHERE id = :id AND going_count < maximum_capacity
    rowcount == 1 -> seat claimed, rowcount == 0 -> event is full. No gap to interleave in.
 2. Serialised transactions - SQLite: BEGIN IMMEDIATE (single writer);
    PostgreSQL: SELECT ... FOR UPDATE row lock on the event (see _lock_event).
 3. CHECK constraint going_count <= maximum_capacity - the database refuses to oversell
    even if application code had a bug.
Plus UNIQUE(event_id, user_id) so a user can never hold two RSVPs for one event.
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from backend.models.entities import RSVP, Event, User, Waitlist
from backend.services.common import audit
from backend.utils.errors import AppError, not_found
from backend.utils.time import iso, utcnow
from cloud import notification_service as notifs
from realtime.realtime_service import hub

log = logging.getLogger("rsvp.service")
STATUSES = ("GOING", "MAYBE", "NOT_GOING", "WAITLISTED")


@dataclass
class RSVPResult:
    rsvp: RSVP | None
    counts: dict
    event_status: str
    changed: bool = True
    message: str = ""
    promoted_user_ids: list = field(default_factory=list)


# ---------- read helpers ----------
def rsvp_counts(db, event_id: int) -> dict:
    rows = db.execute(select(RSVP.status, func.count()).where(RSVP.event_id == event_id).group_by(RSVP.status)).all()
    counts = {s: 0 for s in STATUSES}
    counts.update({s: n for s, n in rows})
    return counts


def snapshot(db, event: Event) -> dict:
    """The payload broadcast to real-time subscribers: the database is the source of truth."""
    db.flush()  # push any pending ORM changes (e.g. event.status) before reloading attributes
    db.expire(event)
    counts = rsvp_counts(db, event.id)
    return {"event_id": event.id, "counts": counts, "capacity": event.maximum_capacity,
            "going_count": event.going_count, "available_seats": max(event.maximum_capacity - event.going_count, 0),
            "event_status": event.status, "ts": iso(utcnow())}


def get_my_rsvp(db, event_id: int, user: User):
    return db.execute(select(RSVP).where(RSVP.event_id == event_id, RSVP.user_id == user.id)).scalar_one_or_none()


def waitlist_position(db, event_id: int, user_id: int):
    entry = db.execute(select(Waitlist).where(Waitlist.event_id == event_id, Waitlist.user_id == user_id,
                                              Waitlist.status == "WAITING")).scalar_one_or_none()
    if not entry:
        return None
    ahead = db.execute(select(func.count()).select_from(Waitlist).where(
        Waitlist.event_id == event_id, Waitlist.status == "WAITING", Waitlist.id < entry.id)).scalar()
    return ahead + 1


# ---------- concurrency-safe primitives ----------
def _lock_event(db, event_id: int):
    stmt = select(Event).where(Event.id == event_id)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()  # row-level lock: other RSVPs for this event queue up
    return db.execute(stmt).scalar_one_or_none()


def claim_seat(db, event_id: int) -> bool:
    res = db.execute(update(Event).where(Event.id == event_id, Event.going_count < Event.maximum_capacity)
                     .values(going_count=Event.going_count + 1))
    return res.rowcount == 1


def release_seat(db, event_id: int):
    db.execute(update(Event).where(Event.id == event_id, Event.going_count > 0)
               .values(going_count=Event.going_count - 1))


def _refresh_status(db, event: Event):
    db.expire(event)
    if event.status in ("PUBLISHED", "FULL"):
        event.status = "FULL" if event.going_count >= event.maximum_capacity else "PUBLISHED"


# ---------- waitlist ----------
def rebalance(db, event: Event) -> list:
    """Promote FIFO waitlisted users while seats are free. Returns notifications to push after commit."""
    pending = []
    while True:
        entry = db.execute(select(Waitlist).where(Waitlist.event_id == event.id, Waitlist.status == "WAITING")
                           .order_by(Waitlist.id).limit(1)).scalar_one_or_none()
        if entry is None or not claim_seat(db, event.id):
            break
        entry.status = "PROMOTED"
        rsvp = db.execute(select(RSVP).where(RSVP.event_id == event.id, RSVP.user_id == entry.user_id)).scalar_one()
        rsvp.status, rsvp.updated_at = "GOING", utcnow()
        pending.append(notifs.notify(db, entry.user_id, event.id, "WAITLIST_PROMOTION",
                                     f"Good news! A seat opened up - you're now GOING to '{event.event_name}'"))
        audit(db, None, event.id, "WAITLIST_PROMOTED", user_id=entry.user_id)
    _refresh_status(db, event)
    return pending


# ---------- main use-cases ----------
def set_rsvp(db, event_id: int, user: User, status: str, *, join_waitlist=False, mode="upsert") -> RSVPResult:
    """createRSVP (mode=create), updateRSVP (mode=update) or either (upsert). Idempotent per (event,user,status)."""
    event = _lock_event(db, event_id)
    if event is None or (event.status == "DRAFT" and event.organizer_id != user.id):
        raise not_found("Event")
    if event.status in ("CANCELLED", "COMPLETED"):
        raise AppError(409, "EVENT_NOT_OPEN", f"This event is {event.status.lower()}")
    existing = get_my_rsvp(db, event_id, user)
    if mode == "create" and existing:
        raise AppError(409, "RSVP_EXISTS", "You already have an RSVP for this event; update it instead")
    if mode == "update" and not existing:
        raise AppError(404, "RSVP_NOT_FOUND", "No RSVP to update; create one first")
    prev = existing.status if existing else None
    if status != "NOT_GOING" and utcnow() > event.registration_deadline:
        raise AppError(400, "REGISTRATION_CLOSED", "The registration deadline has passed")

    # Idempotency: repeating the same request (double click, retry, refresh) changes nothing.
    if prev == status or (prev == "WAITLISTED" and status == "GOING"):
        return RSVPResult(existing, rsvp_counts(db, event_id), event.status, changed=False,
                          message="RSVP unchanged")

    final = status
    if status == "GOING":
        if claim_seat(db, event_id):
            final = "GOING"
        elif join_waitlist:
            final = "WAITLISTED"
        else:
            raise AppError(409, "EVENT_FULL", "This event is full", {"can_join_waitlist": True})

    released = prev == "GOING" and final != "GOING"
    if released:
        release_seat(db, event_id)
    if prev == "WAITLISTED" and final != "WAITLISTED":
        for w in db.execute(select(Waitlist).where(Waitlist.event_id == event_id, Waitlist.user_id == user.id,
                                                   Waitlist.status == "WAITING")).scalars():
            w.status = "LEFT"
    if final == "WAITLISTED":
        db.add(Waitlist(event_id=event_id, user_id=user.id, status="WAITING"))

    now = utcnow()
    try:
        if existing:
            existing.status, existing.updated_at = final, now
            rsvp = existing
        else:
            rsvp = RSVP(event_id=event_id, user_id=user.id, status=final, responded_at=now, updated_at=now)
            db.add(rsvp)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "DUPLICATE_RSVP", "Duplicate RSVP rejected by the database")

    pending = []
    if released:
        pending += rebalance(db, event)
    _refresh_status(db, event)
    text = {"WAITLISTED": f"You're on the waitlist for '{event.event_name}'"}.get(
        final, f"Your RSVP for '{event.event_name}' is now {final.replace('_', ' ')}")
    pending.append(notifs.notify(db, user.id, event_id, "RSVP_CONFIRMATION", text))
    audit(db, user.id, event_id, "RSVP_SET", previous=prev, status=final)
    snap = snapshot(db, event)
    db.commit()

    # After commit: fan out. Failures here are logged, never raised.
    notifs.push(pending)
    hub.publish_threadsafe(f"event:{event_id}", {"type": "rsvp_update", **snap})
    promoted = [n.user_id for n in pending if n.type == "WAITLIST_PROMOTION"]
    return RSVPResult(rsvp, snap["counts"], event.status, True, "Your RSVP has been recorded.", promoted)


def cancel_rsvp(db, event_id: int, user: User) -> RSVPResult:
    event = _lock_event(db, event_id)
    if event is None:
        raise not_found("Event")
    rsvp = get_my_rsvp(db, event_id, user)
    if rsvp is None:
        raise AppError(404, "RSVP_NOT_FOUND", "You have no RSVP for this event")
    prev = rsvp.status
    pending = []
    if prev == "GOING":
        release_seat(db, event_id)
    if prev == "WAITLISTED":
        for w in db.execute(select(Waitlist).where(Waitlist.event_id == event_id, Waitlist.user_id == user.id,
                                                   Waitlist.status == "WAITING")).scalars():
            w.status = "LEFT"
    db.delete(rsvp)
    db.flush()
    if prev == "GOING" and event.status not in ("CANCELLED", "COMPLETED"):
        pending += rebalance(db, event)
    _refresh_status(db, event)
    audit(db, user.id, event_id, "RSVP_CANCELLED", previous=prev)
    snap = snapshot(db, event)
    db.commit()
    notifs.push(pending)
    hub.publish_threadsafe(f"event:{event_id}", {"type": "rsvp_update", **snap})
    return RSVPResult(None, snap["counts"], event.status, True, "Your RSVP has been cancelled.",
                      [n.user_id for n in pending])


def event_rsvps(db, event_id: int):
    rows = db.execute(select(RSVP, User).join(User, User.id == RSVP.user_id)
                      .where(RSVP.event_id == event_id).order_by(RSVP.responded_at)).all()
    return [{"rsvp_id": r.id, "event_id": r.event_id, "user_id": u.id, "user_name": u.name, "user_email": u.email,
             "status": r.status, "responded_at": iso(r.responded_at), "updated_at": iso(r.updated_at)} for r, u in rows]


def rsvp_out(r: RSVP, position=None) -> dict:
    d = {"rsvp_id": r.id, "event_id": r.event_id, "user_id": r.user_id, "status": r.status,
         "responded_at": iso(r.responded_at), "updated_at": iso(r.updated_at)}
    if position is not None:
        d["waitlist_position"] = position
    return d
