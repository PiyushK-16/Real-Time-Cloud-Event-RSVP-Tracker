from tests.conftest import auth_headers, register


def test_register_and_login(client):
    token, user = register(client, "alice@test.com")
    assert user["role"] == "attendee"
    r = client.post("/api/login", json={"email": "alice@test.com", "password": "password123"})
    assert r.status_code == 200


def test_duplicate_registration_rejected(client):
    register(client, "bob@test.com")
    r = client.post("/api/register", json={"email": "bob@test.com", "name": "Bob", "password": "password123"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_TAKEN"


def test_login_wrong_password(client):
    register(client, "carol@test.com")
    r = client.post("/api/login", json={"email": "carol@test.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    r = client.get("/api/me")
    assert r.status_code == 401


def test_logout_revokes_token(client):
    token, _ = register(client, "dave@test.com")
    r = client.post("/api/logout", headers=auth_headers(token))
    assert r.status_code == 200
    r2 = client.get("/api/me", headers=auth_headers(token))
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "TOKEN_REVOKED"
