"""POST/GET/PUT/DELETE /api/events ..."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.middleware.auth import current_user, require_role
from backend.models.entities import User
from backend.schemas import EventIn, EventUpdate
from backend.services import event_service, rsvp_service
from backend.services.common import event_out
from cloud.database_service import get_db

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", status_code=201)
def create_event(body: EventIn, user: User = Depends(require_role("organizer", "admin")), db: Session = Depends(get_db)):
    e = event_service.create_event(db, user, body)
    return event_out(e)


@router.get("")
def list_events(scope: str = Query("upcoming", pattern="^(upcoming|all)$"), mine: bool = False,
               q: str | None = None, event_type: str | None = None, limit: int = 50, offset: int = 0,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = event_service.list_events(db, user, scope=scope, mine=mine, q=q, event_type=event_type, limit=limit, offset=offset)
    out = []
    for e in rows:
        mine_rsvp = rsvp_service.get_my_rsvp(db, e.id, user)
        out.append(event_out(e, my_rsvp=mine_rsvp.status if mine_rsvp else None))
    return {"events": out, "count": len(out)}


@router.get("/{event_id}")
def get_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = event_service.get_event_or_404(db, event_id)
    if not event_service.visible_to(e, user):
        raise event_service.forbidden("This event is not published yet")
    mine_rsvp = rsvp_service.get_my_rsvp(db, event_id, user)
    return event_out(e, counts=rsvp_service.rsvp_counts(db, event_id), my_rsvp=mine_rsvp.status if mine_rsvp else None)


@router.put("/{event_id}")
def update_event(event_id: int, body: EventUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = event_service.update_event(db, event_id, user, body)
    return event_out(e)


@router.post("/{event_id}/publish")
def publish_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return event_out(event_service.publish_event(db, event_id, user))


@router.post("/{event_id}/cancel")
def cancel_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return event_out(event_service.cancel_event(db, event_id, user))


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event_service.delete_event(db, event_id, user)
