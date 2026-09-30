import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_event_rsvp.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.middleware.rate_limit import limiter
from cloud.database_service import Base, engine


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.reset()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def register(client, email, role="attendee", name=None):
    r = client.post("/api/register", json={"email": email, "name": name or email.split("@")[0],
                                           "password": "password123", "role": role})
    assert r.status_code == 201, r.text
    return r.json()["token"], r.json()["user"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_event(client, org_token, **overrides):
    body = {"event_name": "Cloud Computing Workshop", "event_date": "2026-12-01", "start_time": "10:00",
            "end_time": "12:00", "venue": "Auditorium", "maximum_capacity": 2}
    body.update(overrides)
    r = client.post("/api/events", json=body, headers=auth_headers(org_token))
    assert r.status_code == 201, r.text
    return r.json()
