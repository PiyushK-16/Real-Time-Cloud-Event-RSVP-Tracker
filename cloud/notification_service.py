"""Notifications: persisted in-app rows + instant push over the real-time hub.

Delivery is best-effort: a failed push never fails the business operation.
Email/SMS/push-notification providers plug in at `_external_channels` (see docs).
"""
import logging

from backend.models.entities import Notification
from realtime.realtime_service import hub

log = logging.getLogger("rsvp.notify")

TYPES = ("RSVP_CONFIRMATION", "EVENT_REMINDER", "VENUE_CHANGE", "TIME_CHANGE", "EVENT_CANCELLED",
         "WAITLIST_PROMOTION", "ANNOUNCEMENT", "INVITATION")


def serialize(n: Notification) -> dict:
    return {"notification_id": n.id, "user_id": n.user_id, "event_id": n.event_id, "type": n.type,
            "message": n.message, "read": n.read, "created_at": n.created_at.isoformat()}


def notify(db, user_id: int, event_id: int | None, type_: str, message: str) -> Notification:
    """Add a notification row to the CURRENT transaction (caller commits, then calls push)."""
    n = Notification(user_id=user_id, event_id=event_id, type=type_, message=message[:500])
    db.add(n)
    db.flush()
    return n


def push(notifications) -> None:
    for n in notifications:
        try:
            hub.publish_threadsafe(f"user:{n.user_id}", {"type": "notification", "notification": serialize(n)})
            _external_channels(n)
        except Exception:
            log.exception("notification push failed (id=%s); row is still stored", getattr(n, "id", "?"))


def _external_channels(n: Notification) -> None:
    """Hook for email (SES/SendGrid), SMS (SNS/Twilio) or web-push. Intentionally a no-op offline."""
    log.info("notification user=%s type=%s", n.user_id, n.type)
