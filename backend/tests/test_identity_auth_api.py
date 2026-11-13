import time
from urllib.parse import parse_qs, urlparse

import jwt

from shared.config.settings import settings


def _build_geekclass_token(role: str = "teacher") -> str:
    payload = {
        "id": "user-42",
        "name": "Geek User",
        "role": role,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def test_auth_options(client) -> None:
    response = client.get("/api/v1/auth/options")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["dev_login_enabled"], bool)
    assert isinstance(payload["geekclass_enabled"], bool)


def test_dev_login_and_me(client) -> None:
    login = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": "dev-user", "role": "teacher"},
    )
    assert login.status_code == 200
    session = login.json()
    assert session["provider"] == "dev"
    assert session["external_user_id"].startswith("dev:")

    me = client.get("/api/v1/me", headers={"X-Session-Id": session["session_id"]})
    assert me.status_code == 200
    assert me.json()["session_id"] == session["session_id"]

    # Backward-compatible header alias.
    me_alias = client.get("/api/v1/identity/me", headers={"X-Dev-Session": session["session_id"]})
    assert me_alias.status_code == 200
    assert me_alias.json()["session_id"] == session["session_id"]


def test_geekclass_login_with_bearer_token(client) -> None:
    token = _build_geekclass_token(role="admin")
    response = client.post(
        "/api/v1/auth/login/geekclass",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "geekclass"
    assert payload["external_user_id"] == "user-42"
    assert payload["role"] == "admin"


def test_auth_callback_redirect_includes_session_id(client) -> None:
    token = _build_geekclass_token(role="teacher")
    response = client.get(
        "/api/v1/auth/callback",
        params={"token": token, "next": "/workspace/demo-team"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 307}
    location = response.headers["location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    assert "session_id" in params


def test_failed_geekclass_callback_stops_automatic_login_loop_and_preserves_next(client):
    for params in [
        {"next": "/lobbies/example?tab=participants"},
        {"token": "invalid", "next": "/lobbies/example?tab=participants"},
    ]:
        response = client.get("/api/v1/auth/callback", params=params, follow_redirects=False)
        assert response.status_code == 307
        location = urlparse(response.headers["location"])
        assert location.path == "/login"
        assert parse_qs(location.query) == {
            "auth_error": ["geekclass"],
            "next": ["/lobbies/example?tab=participants"],
        }


def test_failed_geekclass_callback_does_not_preserve_an_external_redirect(client):
    response = client.get(
        "/api/v1/auth/callback",
        params={"next": "https://elsewhere.example"},
        follow_redirects=False,
    )
    assert parse_qs(urlparse(response.headers["location"]).query)["next"] == ["/"]


def test_geekclass_callback_keeps_query_and_fragment_and_replaces_stale_session(client):
    response = client.get(
        "/api/v1/auth/callback",
        params={
            "token": _build_geekclass_token(),
            "next": "/lobbies?all=1&session_id=stale#results",
        },
        follow_redirects=False,
    )
    target = urlparse(response.headers["location"])
    query = parse_qs(target.query)
    assert target.path == "/lobbies" and target.fragment == "results"
    assert query["all"] == ["1"]
    assert len(query["session_id"]) == 1 and query["session_id"] != ["stale"]
