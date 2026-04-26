"""FastAPI HTTP layer tests — covers the 3 live routes."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from syncup.db.models import User
from syncup.ingest.spotify import TokenResponse


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
    # debug=True makes cookies non-secure so TestClient (HTTP, not HTTPS) can send them.
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    # Patch sessionmaker_for so the lifespan doesn't try to open a real DB connection.
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def authed_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Client with a mocked authenticated user for callback tests."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    now = datetime.now(UTC)
    fake_user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        display_name="Tester",
        is_matchable=False,
        onboarded=False,
        created_at=now,
        updated_at=now,
    )

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with patch("syncup.api.app.require_auth", return_value=fake_user):
            with TestClient(app, follow_redirects=False) as c:
                yield c


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# /api/auth/spotify
# ---------------------------------------------------------------------------


def test_spotify_auth_redirects_to_spotify(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "accounts.spotify.com" in resp.headers["location"]


def test_spotify_auth_sets_httponly_cookies(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify", follow_redirects=False)
    assert "spotify_state" in resp.cookies
    assert "spotify_verifier" in resp.cookies


def test_spotify_auth_includes_client_id_in_url(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify", follow_redirects=False)
    assert "test-client-id" in resp.headers["location"]


# ---------------------------------------------------------------------------
# /api/auth/spotify/callback — error cases
# ---------------------------------------------------------------------------


def test_callback_state_mismatch_returns_error_envelope(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify/callback?code=abc&state=wrong-state")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "OAUTH_STATE_MISMATCH"
    assert "message" in body["error"]


def test_callback_missing_state_cookie_returns_error(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify/callback?code=abc&state=some-state")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_callback_missing_verifier_cookie_returns_error(client: TestClient) -> None:
    # Set state cookie to matching value, but no verifier cookie.
    client.cookies.set("spotify_state", "good-state")
    resp = client.get("/api/auth/spotify/callback?code=abc&state=good-state")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_PKCE_VERIFIER"


def test_callback_empty_code_returns_validation_error(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify/callback?code=&state=s")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_callback_missing_code_returns_validation_error(client: TestClient) -> None:
    resp = client.get("/api/auth/spotify/callback?state=s")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /api/auth/spotify/callback — success path
# ---------------------------------------------------------------------------

_MOCK_TOKENS = TokenResponse(
    access_token="access-tok",
    refresh_token="refresh-tok",
    expires_in=3600,
    token_type="Bearer",
)


def test_callback_requires_auth(client: TestClient) -> None:
    # PKCE cookies present so state check passes, but no session cookie → 401.
    client.cookies.set("spotify_state", "s")
    client.cookies.set("spotify_verifier", "v")
    resp = client.get("/api/auth/spotify/callback?code=abc&state=s")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_callback_success_redirects_to_frontend(authed_client: TestClient) -> None:
    with (
        patch("syncup.ingest.spotify.SpotifyClient.exchange_code", return_value=_MOCK_TOKENS),
        patch("syncup.ingest.spotify.SpotifyClient.fetch_me", return_value={"id": "spotify-123"}),
        patch("syncup.api.app.encrypt_token", return_value=b"encrypted"),
    ):
        auth_resp = authed_client.get("/api/auth/spotify", follow_redirects=False)
        assert auth_resp.status_code in (302, 307)
        state = authed_client.cookies.get("spotify_state")
        assert state is not None

        resp = authed_client.get(f"/api/auth/spotify/callback?code=authcode&state={state}")

    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_callback_success_clears_pkce_cookies(authed_client: TestClient) -> None:
    with (
        patch("syncup.ingest.spotify.SpotifyClient.exchange_code", return_value=_MOCK_TOKENS),
        patch("syncup.ingest.spotify.SpotifyClient.fetch_me", return_value={"id": "spotify-123"}),
        patch("syncup.api.app.encrypt_token", return_value=b"encrypted"),
    ):
        authed_client.get("/api/auth/spotify", follow_redirects=False)
        state = authed_client.cookies.get("spotify_state")

        resp = authed_client.get(f"/api/auth/spotify/callback?code=c&state={state}")

    assert resp.cookies.get("spotify_state") in (None, "")
    assert resp.cookies.get("spotify_verifier") in (None, "")


def test_callback_fetch_me_failure_returns_error(authed_client: TestClient) -> None:
    import httpx

    with (
        patch("syncup.ingest.spotify.SpotifyClient.exchange_code", return_value=_MOCK_TOKENS),
        patch(
            "syncup.ingest.spotify.SpotifyClient.fetch_me",
            side_effect=httpx.HTTPStatusError(
                "403", request=httpx.Request("GET", "https://api.spotify.com/v1/me"),
                response=httpx.Response(403),
            ),
        ),
    ):
        authed_client.get("/api/auth/spotify", follow_redirects=False)
        state = authed_client.cookies.get("spotify_state")
        resp = authed_client.get(f"/api/auth/spotify/callback?code=authcode&state={state}")

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SPOTIFY_TOKEN_ERROR"


def test_callback_encrypts_both_tokens(authed_client: TestClient) -> None:
    with (
        patch("syncup.ingest.spotify.SpotifyClient.exchange_code", return_value=_MOCK_TOKENS),
        patch("syncup.ingest.spotify.SpotifyClient.fetch_me", return_value={"id": "spotify-123"}),
        patch("syncup.api.app.encrypt_token", return_value=b"encrypted") as enc_mock,
    ):
        authed_client.get("/api/auth/spotify", follow_redirects=False)
        state = authed_client.cookies.get("spotify_state")
        authed_client.get(f"/api/auth/spotify/callback?code=authcode&state={state}")

    enc_mock.assert_any_call("access-tok")
    enc_mock.assert_any_call("refresh-tok")


# ---------------------------------------------------------------------------
# Error envelope format
# ---------------------------------------------------------------------------


def test_unknown_route_returns_404(client: TestClient) -> None:
    # Starlette routing 404s are returned as direct responses (not raised
    # exceptions), so they bypass exception_handlers and use Starlette's
    # default format. We just assert the status code here.
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404


def test_syncup_error_uses_envelope_format(client: TestClient) -> None:
    # SyncUpError is our domain exception — always uses the error envelope.
    # The state-mismatch callback error is a convenient way to trigger one.
    resp = client.get("/api/auth/spotify/callback?code=x&state=mismatch")
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
