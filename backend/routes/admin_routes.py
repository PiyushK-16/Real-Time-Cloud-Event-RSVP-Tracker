"""Optional admin APIs: manage users, moderate events, platform stats."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.middleware.auth import require_role
from backend.models.entities import Event, RSVP, User
from backend.services.common import event_out, user_out
from backend.services import event_service
from cloud.database_service import get_db, db_healthy

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def platform_stats(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {
        "total_users": db.execute(select(func.count()).select_from(User)).scalar(),
        "total_organizers": db.execute(select(func.count()).select_from(User).where(User.role == "organizer")).scalar(),
        "total_events": db.execute(select(func.count()).select_from(Event)).scalar(),
        "total_rsvps": db.execute(select(func.count()).select_from(RSVP)).scalar(),
        "database_healthy": db_healthy(),
    }


@router.get("/users")
def list_users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {"users": [user_out(u) for u in db.execute(select(User)).scalars()]}


@router.put("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        from backend.utils.errors import not_found
        raise not_found("User")
    target.is_active = False
    db.commit()
    return user_out(target)


@router.put("/events/{event_id}/moderate-cancel")
def moderate_cancel(event_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    e = event_service.get_event_or_404(db, event_id)
    return event_out(event_service.cancel_event(db, event_id, user))
