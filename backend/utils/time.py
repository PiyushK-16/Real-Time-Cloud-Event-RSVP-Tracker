"""Time helpers. All timestamps are stored as naive UTC; event date/time are treated as UTC too."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.isoformat() if dt is not None else None
