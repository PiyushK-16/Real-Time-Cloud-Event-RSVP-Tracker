"""POST/PUT/DELETE /api/events/{id}/rsvp, GET .../rsvps, GET /api/rsvps/me"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.middleware.auth import current_user
from backend.middleware.rate_limit import limiter
from backend.models.entities import User
from backend.schemas import RSVPIn
from backend.services import event_service, rsvp_service
from backend.utils.errors import forbidden
from cloud.database_service import get_db
from backend.config import settings

router = APIRouter(prefix="/api", tags=["rsvp"])


def _respond(db, result, event_id, user):
    if result.rsvp:
        pos = rsvp_service.waitlist_position(db, event_id, user.id) if result.rsvp.status == "WAITLISTED" else None
        d = rsvp_service.rsvp_out(result.rsvp, pos)
    else:
        d = {"status": "NOT_GOING"}
    d["message"] = result.message
    d["counts"] = result.counts
    d["event_status"] = result.event_status
    return d


@router.post("/events/{event_id}/rsvp", status_code=201)
def create_rsvp(event_id: int, body: RSVPIn, join_waitlist: bool = Query(False),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"rsvp:{user.id}", settings.RATE_LIMIT_RSVP_PER_MIN)
    result = rsvp_service.set_rsvp(db, event_id, user, body.status, join_waitlist=join_waitlist, mode="create")
    return _respond(db, result, event_id, user)


@router.put("/events/{event_id}/rsvp")
def update_rsvp(event_id: int, body: RSVPIn, join_waitlist: bool = Query(False),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"rsvp:{user.id}", settings.RATE_LIMIT_RSVP_PER_MIN)
    result = rsvp_service.set_rsvp(db, event_id, user, body.status, join_waitlist=join_waitlist, mode="update")
    return _respond(db, result, event_id, user)


@router.delete("/events/{event_id}/rsvp")
def cancel_rsvp(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = rsvp_service.cancel_rsvp(db, event_id, user)
    return _respond(db, result, event_id, user)


@router.get("/events/{event_id}/rsvps")
def list_event_rsvps(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = event_service.get_event_or_404(db, event_id)
    event_service.require_manage(e, user)  # only the organizer/admin sees the attendee list
    return {"rsvps": rsvp_service.event_rsvps(db, event_id)}


@router.get("/rsvps/me")
def my_rsvps(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from backend.models.entities import RSVP, Event
    rows = db.execute(select(RSVP, Event).join(Event, Event.id == RSVP.event_id)
                      .where(RSVP.user_id == user.id).order_by(Event.event_date)).all()
    from backend.services.common import event_out
    return {"rsvps": [{**event_out(e, my_rsvp=r.status)} for r, e in rows]}
