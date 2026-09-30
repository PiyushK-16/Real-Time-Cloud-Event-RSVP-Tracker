"""Analytics calculations. Pure helpers are unit-tested; queries feed them from the database."""
import json
from collections import OrderedDict

from sqlalchemy import func, select

from backend.models.entities import RSVP, AuditLog, Event, Invitation, User
from backend.services.rsvp_service import rsvp_counts
from backend.utils.time import iso, utcnow


def pct(numerator, denominator):
    """Percentage rounded to 1 decimal; None when the denominator is 0 (undefined, not 0%)."""
    return round(numerator / denominator * 100, 1) if denominator else None


def calc_response_rate(invited: int, responded: int):
    return pct(responded, invited)  # e.g. 350 / 500 * 100 = 70.0


def calc_capacity_utilization(going: int, capacity: int):
    return pct(going, capacity)


def compute_event_analytics(db, event: Event) -> dict:
    counts = rsvp_counts(db, event.id)
    invited = db.execute(select(func.count()).select_from(Invitation).where(Invitation.event_id == event.id)).scalar()
    responded_invitees = db.execute(
        select(func.count(func.distinct(RSVP.user_id)))
        .join(User, User.id == RSVP.user_id)
        .join(Invitation, (Invitation.email == User.email) & (Invitation.event_id == RSVP.event_id))
        .where(RSVP.event_id == event.id)).scalar()
    total = sum(counts.values())
    per_day = OrderedDict(db.execute(select(func.date(RSVP.responded_at), func.count()).where(RSVP.event_id == event.id)
                                     .group_by(func.date(RSVP.responded_at)).order_by(func.date(RSVP.responded_at))).all())
    running, growth = 0, []
    for day, n in per_day.items():
        running += n
        growth.append({"date": str(day), "new_rsvps": n, "cumulative": running})
    logs = db.execute(select(AuditLog).where(AuditLog.event_id == event.id, AuditLog.action.in_(
        ("RSVP_SET", "RSVP_CANCELLED", "WAITLIST_PROMOTED"))).order_by(AuditLog.id.desc()).limit(20)).scalars().all()
    timeline = [{"at": iso(l.created_at), "action": l.action, **json.loads(l.details or "{}")} for l in logs]
    return {
        "event_id": event.id, "event_name": event.event_name, "status": event.status,
        "total_rsvps": total, "going": counts["GOING"], "maybe": counts["MAYBE"],
        "not_going": counts["NOT_GOING"], "waitlist_count": counts["WAITLISTED"],
        "capacity": event.maximum_capacity, "available_seats": max(event.maximum_capacity - event.going_count, 0),
        "capacity_utilization": calc_capacity_utilization(event.going_count, event.maximum_capacity),
        "invited": invited, "responded_invitees": responded_invitees,
        "response_rate": calc_response_rate(invited, responded_invitees),
        # conversion = invited people who committed to GOING (defined only when invitations exist)
        "rsvp_conversion_rate": pct(counts["GOING"], invited),
        "status_distribution": {k: counts[k] for k in ("GOING", "MAYBE", "NOT_GOING")},
        "growth": growth, "timeline": timeline,
    }


def compute_organizer_summary(db, organizer: User) -> dict:
    events = db.execute(select(Event).where(Event.organizer_id == organizer.id).order_by(Event.event_date)).scalars().all()
    today = utcnow().date()
    tot = {"GOING": 0, "MAYBE": 0, "NOT_GOING": 0, "WAITLISTED": 0}
    invited = responded = free = 0
    rows = []
    for e in events:
        a = compute_event_analytics(db, e)
        for k, key in (("GOING", "going"), ("MAYBE", "maybe"), ("NOT_GOING", "not_going"), ("WAITLISTED", "waitlist_count")):
            tot[k] += a[key]
        invited += a["invited"]
        responded += a["responded_invitees"]
        if e.status in ("PUBLISHED", "FULL"):
            free += a["available_seats"]
        rows.append({"event_id": e.id, "event_name": e.event_name, "status": e.status, "event_date": e.event_date.isoformat(),
                     "going": a["going"], "maybe": a["maybe"], "not_going": a["not_going"], "capacity": e.maximum_capacity,
                     "capacity_utilization": a["capacity_utilization"]})
    return {
        "total_events": len(events),
        "upcoming_events": sum(1 for e in events if e.status in ("PUBLISHED", "FULL") and e.event_date >= today),
        "total_invitees": invited, "total_responses": sum(tot.values()),
        "going": tot["GOING"], "maybe": tot["MAYBE"], "not_going": tot["NOT_GOING"],
        "response_rate": calc_response_rate(invited, responded), "available_capacity": free,
        "waitlist_size": tot["WAITLISTED"], "events": rows,
    }
