from tests.conftest import auth_headers, make_event, register


def test_organizer_creates_event(client):
    token, _ = register(client, "org@test.com", "organizer")
    e = make_event(client, token)
    assert e["status"] == "PUBLISHED"
    assert e["available_seats"] == 2


def test_attendee_cannot_create_event(client):
    token, _ = register(client, "att@test.com", "attendee")
    r = client.post("/api/events", json={"event_name": "Party", "event_date": "2026-12-01", "start_time": "10:00",
                                        "end_time": "11:00", "venue": "Hall", "maximum_capacity": 5},
                    headers=auth_headers(token))
    assert r.status_code == 403


def test_get_and_list_events(client):
    token, _ = register(client, "org2@test.com", "organizer")
    e = make_event(client, token)
    r = client.get(f"/api/events/{e['event_id']}", headers=auth_headers(token))
    assert r.status_code == 200
    r2 = client.get("/api/events", headers=auth_headers(token))
    assert r2.status_code == 200 and r2.json()["count"] >= 1


def test_unauthorized_event_modification(client):
    org_token, _ = register(client, "owner@test.com", "organizer")
    e = make_event(client, org_token)
    other_token, _ = register(client, "intruder@test.com", "organizer")
    r = client.put(f"/api/events/{e['event_id']}", json={"venue": "Hacked Room"}, headers=auth_headers(other_token))
    assert r.status_code == 403


def test_cancel_event(client):
    token, _ = register(client, "org3@test.com", "organizer")
    e = make_event(client, token)
    r = client.post(f"/api/events/{e['event_id']}/cancel", headers=auth_headers(token))
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
