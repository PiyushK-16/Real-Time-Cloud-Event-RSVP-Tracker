"""Announcements, invitations and reminders (organizer -> attendees)."""
from sqlalchemy import select

from backend.models.entities import RSVP, Announcement, Invitation, User
from backend.services import event_service
from backend.services.common import audit
from backend.utils.errors import forbidden
from backend.utils.time import iso
from cloud import notification_service as notifs


def announcement_out(a: Announcement) -> dict:
    return {"announcement_id": a.id, "event_id": a.event_id, "category": a.category, "title": a.title,
            "message": a.message, "created_at": iso(a.created_at)}


def _audience(db, event_id):
    return db.execute(select(RSVP.user_id).where(RSVP.event_id == event_id,
                      RSVP.status.in_(("GOING", "MAYBE", "WAITLISTED")))).scalars().all()


def create_announcement(db, event_id: int, user: User, data) -> Announcement:
    e = event_service.get_event_or_404(db, event_id)
    event_service.require_manage(e, user)
    a = Announcement(event_id=e.id, organizer_id=user.id, category=data.category, title=data.title, message=data.message)
    db.add(a)
    db.flush()
    pending = [notifs.notify(db, uid, e.id, "ANNOUNCEMENT", f"{e.event_name}: {data.title}") for uid in _audience(db, e.id)]
    audit(db, user.id, e.id, "ANNOUNCEMENT_CREATED", title=data.title, recipients=len(pending))
    db.commit()
    notifs.push(pending)
    return a


def list_announcements(db, event_id: int, user: User):
    e = event_service.get_event_or_404(db, event_id)
    has_rsvp = db.execute(select(RSVP.id).where(RSVP.event_id == e.id, RSVP.user_id == user.id)).first()
    if not (event_service.can_manage(e, user) or has_rsvp):
        raise forbidden("RSVP to this event to see its announcements")
    rows = db.execute(select(Announcement).where(Announcement.event_id == e.id).order_by(Announcement.id.desc())).scalars()
    return [announcement_out(a) for a in rows]


def send_reminders(db, event_id: int, user: User) -> int:
    e = event_service.get_event_or_404(db, event_id)
    event_service.require_manage(e, user)
    ids = db.execute(select(RSVP.user_id).where(RSVP.event_id == e.id, RSVP.status.in_(("GOING", "MAYBE")))).scalars().all()
    pending = [notifs.notify(db, uid, e.id, "EVENT_REMINDER",
                             f"Reminder: '{e.event_name}' is on {e.event_date} at {e.start_time:%H:%M}") for uid in ids]
    audit(db, user.id, e.id, "REMINDERS_SENT", recipients=len(pending))
    db.commit()
    notifs.push(pending)
    return len(pending)


def invite(db, event_id: int, user: User, emails) -> dict:
    e = event_service.get_event_or_404(db, event_id)
    event_service.require_manage(e, user)
    added, pending = 0, []
    for raw in {str(m).lower() for m in emails}:
        if db.execute(select(Invitation.id).where(Invitation.event_id == e.id, Invitation.email == raw)).first():
            continue
        db.add(Invitation(event_id=e.id, email=raw))
        added += 1
        target = db.execute(select(User).where(User.email == raw)).scalar_one_or_none()
        if target:
            pending.append(notifs.notify(db, target.id, e.id, "INVITATION", f"You're invited to '{e.event_name}'"))
    audit(db, user.id, e.id, "INVITED", added=added)
    db.commit()
    notifs.push(pending)
    return {"invited": added, "skipped_duplicates": len(set(map(str, emails))) - added}
