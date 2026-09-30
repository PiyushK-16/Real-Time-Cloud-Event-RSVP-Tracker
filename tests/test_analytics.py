from analytics.event_analytics import calc_capacity_utilization, calc_response_rate
from tests.conftest import auth_headers, make_event, register


def test_response_rate_calculation():
    assert calc_response_rate(500, 350) == 70.0
    assert calc_response_rate(0, 0) is None


def test_capacity_utilization_calculation():
    assert calc_capacity_utilization(99, 100) == 99.0
    assert calc_capacity_utilization(100, 100) == 100.0


def test_event_analytics_endpoint(client):
    org, _ = register(client, "org11@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "att11@test.com")
    client.post(f"/api/events/{e['event_id']}/rsvp", json={"status": "GOING"}, headers=auth_headers(att))
    r = client.get(f"/api/events/{e['event_id']}/analytics", headers=auth_headers(org))
    assert r.status_code == 200
    assert r.json()["going"] == 1
    assert r.json()["capacity_utilization"] == 50.0


def test_analytics_forbidden_for_non_organizer(client):
    org, _ = register(client, "org12@test.com", "organizer")
    e = make_event(client, org)
    att, _ = register(client, "att12@test.com")
    r = client.get(f"/api/events/{e['event_id']}/analytics", headers=auth_headers(att))
    assert r.status_code == 403
