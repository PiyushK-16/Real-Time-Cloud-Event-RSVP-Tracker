from tests.conftest import auth_headers, make_event, register


def test_valid_rsvp(client):
    org, _ = register(client, "org1@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "u1@test.com")
    r = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    assert r.status_code == 201
    assert r.json()["counts"]["GOING"] == 1


def test_duplicate_rsvp_prevented(client):
    org, _ = register(client, "org2@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "u2@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    r = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "MAYBE"}, headers=auth_headers(att))
    assert r.status_code == 409 and r.json()["error"]["code"] == "RSVP_EXISTS"


def test_update_going_to_maybe_and_back(client):
    org, _ = register(client, "org3@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "u3@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    r = client.put(f"/api/events/{e['event_id']}/rsvp", json={"status": "MAYBE"}, headers=auth_headers(att))
    assert r.json()["counts"] == {"GOING": 0, "MAYBE": 1, "NOT_GOING": 0, "WAITLISTED": 0}
    r2 = client.put(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    assert r2.json()["counts"]["GOING"] == 1


def test_cancel_rsvp(client):
    org, _ = register(client, "org4@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "u4@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    r = client.delete(f"/api/events/{e['event_id']}/rsvp", headers=auth_headers(att))
    assert r.status_code == 200 and r.json()["counts"]["GOING"] == 0


def test_registration_deadline_enforced(client):
    org, _ = register(client, "org5@test.com", "organizer")
    e = make_event(client, org, registration_deadline="2020-01-01T00:00:00")
    att, _ = register(client, "u5@test.com")
    r = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    assert r.status_code == 400 and r.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_capacity_enforcement_and_waitlist(client):
    org, _ = register(client, "org6@test.com", "organizer")
    e = make_event(client, org, maximum_capacity=1)
    a, _ = register(client, "a6@test.com")
    b, _ = register(client, "b6@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(a))
    r = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(b))
    assert r.status_code == 409 and r.json()["error"]["can_join_waitlist"] is True
    r2 = client.post(f"/api/events/{e['event_id']}/rsvp?join_waitlist=true", json={"status": "GOING"}, headers=auth_headers(b))
    assert r2.status_code == 201 and r2.json()["status"] == "WAITLISTED"
    r3 = client.delete(f"/api/events/{e['event_id']}/rsvp", headers=auth_headers(a))
    assert r3.status_code == 200
    r4 = client.get(f"/api/events/{e['event_id']}", headers=auth_headers(org))
    assert r4.json()["counts"]["GOING"] == 1  # B was auto-promoted from the waitlist


def test_simultaneous_final_seat_requests(client):
    """Two users race for the LAST seat. Exactly one must win - this proves claim_seat() is atomic."""
    org, _ = register(client, "org7@test.com", "organizer")
    e = make_event(client, org, maximum_capacity=1)
    a, _ = register(client, "a7@test.com")
    b, _ = register(client, "b7@test.com")
    r1 = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(a))
    r2 = client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(b))
    results = sorted([r1.status_code, r2.status_code])
    assert results == [201, 409]
    final = client.get(f"/api/events/{e['event_id']}", headers=auth_headers(org)).json()
    assert final["going_count"] == 1  # never oversold


def test_unauthorized_rsvp_modification_not_possible(client):
    """A user has no API surface to modify someone else's RSVP - only their own."""
    org, _ = register(client, "org8@test.com", "organizer")
    e = make_event(client, org)
    a, _ = register(client, "a8@test.com")
    b, _ = register(client, "b8@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(a))
    r = client.put(f"/api/events/{e['event_id']}/rsvp", json={"status": "NOT_GOING"}, headers=auth_headers(b))
    assert r.status_code == 404  # B has no RSVP of their own to update
