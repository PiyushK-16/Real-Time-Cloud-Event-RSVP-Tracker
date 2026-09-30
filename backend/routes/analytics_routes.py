"""GET /api/events/{id}/analytics, GET /api/organizer/summary"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.event_analytics import compute_event_analytics, compute_organizer_summary
from backend.middleware.auth import current_user, require_role
from backend.models.entities import User
from backend.services import event_service
from cloud.database_service import get_db

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/events/{event_id}/analytics")
def event_analytics(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = event_service.get_event_or_404(db, event_id)
    event_service.require_manage(e, user)
    return compute_event_analytics(db, e)


@router.get("/organizer/summary")
def organizer_summary(user: User = Depends(require_role("organizer", "admin")), db: Session = Depends(get_db)):
    return compute_organizer_summary(db, user)
