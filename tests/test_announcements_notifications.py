from tests.conftest import auth_headers, make_event, register


def test_announcement_creation_and_notification(client):
    org, _ = register(client, "org9@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "att9@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    r = client.post(f"/api/events/{e['event_id']}/announcements",
                    json={"title": "Venue moved", "message": "New room: B204", "category": "VENUE_UPDATED"},
                    headers=auth_headers(org))
    assert r.status_code == 201
    notifs = client.get("/api/notifications", headers=auth_headers(att)).json()
    assert any(n["type"] == "ANNOUNCEMENT" for n in notifs["notifications"])


def test_notification_marked_read(client):
    org, _ = register(client, "org10@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "att10@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    notifs = client.get("/api/notifications", headers=auth_headers(att)).json()["notifications"]
    nid = notifs[0]["notification_id"]
    r = client.put(f"/api/notifications/{nid}/read", headers=auth_headers(att))
    assert r.status_code == 200 and r.json()["read"] is True
