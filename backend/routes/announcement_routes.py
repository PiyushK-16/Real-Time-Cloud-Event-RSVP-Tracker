"""POST/GET /api/events/{id}/announcements, POST .../invite, POST .../remind"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.middleware.auth import current_user
from backend.models.entities import User
from backend.schemas import AnnouncementIn, InviteIn
from backend.services import announcement_service
from cloud.database_service import get_db

router = APIRouter(prefix="/api/events", tags=["announcements"])


@router.post("/{event_id}/announcements", status_code=201)
def create_announcement(event_id: int, body: AnnouncementIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return announcement_service.announcement_out(announcement_service.create_announcement(db, event_id, user, body))


@router.get("/{event_id}/announcements")
def list_announcements(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"announcements": announcement_service.list_announcements(db, event_id, user)}


@router.post("/{event_id}/invite")
def invite(event_id: int, body: InviteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return announcement_service.invite(db, event_id, user, body.emails)


@router.post("/{event_id}/remind")
def remind(event_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = announcement_service.send_reminders(db, event_id, user)
    return {"reminders_sent": n}
