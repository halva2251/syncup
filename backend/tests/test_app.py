"""FastAPI HTTP layer tests — covers the 3 live routes."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from syncup.ingest.spotify import TokenResponse


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
    # debug=True makes cookies non-secure so TestClient (HTTP, not HTTPS) can send them.
    monkeypatch.setenv("DEBUG", "true")
    from unittest.mock import MagicMock, patch

    from syncup.api.app import app

    # Patch sessionmaker_for so the lifespan doesn't try to open a real DB connection.
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
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


def test_callback_success_returns_token_metadata(client: TestClient) -> None:
    mock_tokens = TokenResponse(
        access_token="access-tok",
        refresh_token="refresh-tok",
        expires_in=3600,
        token_type="Bearer",
    )

    with patch("syncup.ingest.spotify.SpotifyClient.exchange_code", return_value=mock_tokens):
        # Trigger auth start to get real state/verifier cookies.
        assert client.get("/api/auth/spotify", follow_redirects=False).status_code in (302, 307)
        state = client.cookies.get("spotify_state")
        assert state is not None

        resp = client.get(f"/api/auth/spotify/callback?code=authcode&state={state}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600


def test_callback_success_clears_pkce_cookies(client: TestClient) -> None:
    mock_tokens = TokenResponse(
        access_token="a",
        refresh_token="r",
        expires_in=3600,
        token_type="Bearer",
    )

    with patch("syncup.ingest.spotify.SpotifyClient.exchange_code", return_value=mock_tokens):
        client.get("/api/auth/spotify", follow_redirects=False)
        state = client.cookies.get("spotify_state")

        resp = client.get(f"/api/auth/spotify/callback?code=c&state={state}")

    # After callback, PKCE cookies should be cleared.
    assert resp.cookies.get("spotify_state") in (None, "")
    assert resp.cookies.get("spotify_verifier") in (None, "")


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
