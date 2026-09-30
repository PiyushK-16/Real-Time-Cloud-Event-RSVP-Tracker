from cloud.database_service import db_healthy
from tests.conftest import auth_headers, make_event, register


def test_double_click_rsvp_is_idempotent(client):
    """Clicking GOING twice (double-click / retried request) must not double count."""
    org, _ = register(client, "org13@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "att13@test.com")
    r1 = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    r2 = client.put(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    assert r1.json()["counts"]["GOING"] == 1
    assert r2.json()["counts"]["GOING"] == 1  # unchanged, not incremented again


def test_database_health_check(client):
    assert db_healthy() is True


def test_expired_token_rejected(client):
    import time
    from cloud.auth_service import create_access_token
    token, _, _ = create_access_token(1, "attendee", expires_minutes=-1)  # already expired
    r = client.get("/api/me", headers=auth_headers(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_cancelled_event_rejects_new_rsvp(client):
    org, _ = register(client, "org14@test.com", "organizer")
    e = make_event(client, org)
    client.post(f"/api/events/{e['event_id']}/cancel", headers=auth_headers(org))
    att, _ = register(client, "att14@test.com")
    r = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    assert r.status_code == 409 and r.json()["error"]["code"] == "EVENT_NOT_OPEN"
