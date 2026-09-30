"""GET /api/notifications, PUT /api/notifications/{id}/read"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.middleware.auth import current_user
from backend.models.entities import Notification, User
from backend.utils.errors import not_found
from cloud.database_service import get_db
from cloud.notification_service import serialize

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread_only: bool = False, limit: int = 50,
                       user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    rows = db.execute(stmt.order_by(Notification.created_at.desc()).limit(min(limit, 100))).scalars().all()
    unread = db.execute(select(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))).all()
    return {"notifications": [serialize(n) for n in rows], "unread_count": len(unread)}


@router.put("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise not_found("Notification")
    n.read = True
    db.commit()
    return serialize(n)


@router.put("/read-all")
def mark_all_read(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False)).values(read=True))
    db.commit()
    return {"message": "All notifications marked read"}
