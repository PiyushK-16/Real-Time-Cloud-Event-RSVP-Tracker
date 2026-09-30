"""Database tables (relational design). See docs/architecture.md for the ER diagram."""
from datetime import date, datetime, time

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String,
                        Text, Time, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.utils.time import utcnow
from cloud.database_service import Base

ROLES = ("attendee", "organizer", "admin")
EVENT_STATUSES = ("DRAFT", "PUBLISHED", "FULL", "COMPLETED", "CANCELLED")
RSVP_STATUSES = ("GOING", "MAYBE", "NOT_GOING", "WAITLISTED")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="attendee")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    event_type: Mapped[str] = mapped_column(String(50), default="general")
    event_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    online_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    maximum_capacity: Mapped[int] = mapped_column(Integer)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    # Denormalised counter of GOING RSVPs. It is only changed by atomic UPDATE statements
    # and the CHECK below lets the *database itself* refuse to oversell.
    going_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    organizer: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint("maximum_capacity > 0", name="ck_capacity_positive"),
        CheckConstraint("going_count >= 0 AND going_count <= maximum_capacity", name="ck_going_within_capacity"),
        Index("ix_events_status_date", "status", "event_date"),
    )


class RSVP(Base):
    __tablename__ = "rsvps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    responded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship()

    __table_args__ = (
        # One active RSVP per user per event, enforced by the database (not just app code).
        UniqueConstraint("event_id", "user_id", name="uq_rsvp_event_user"),
        Index("ix_rsvps_event_status", "event_id", "status"),
    )


class Waitlist(Base):
    __tablename__ = "waitlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # increasing id = FIFO order
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(15), default="WAITING")  # WAITING | PROMOTED | LEFT

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_waitlist_event_user"),
        Index("ix_waitlist_event_status", "event_id", "status", "id"),
    )


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_invite_event_email"),)


class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(30), default="GENERAL")
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_notif_user_read", "user_id", "read", "created_at"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RevokedToken(Base):
    """Logout list: JWTs are stateless, so a logged-out token's jti is stored until it expires."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
