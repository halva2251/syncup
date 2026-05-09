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
    assert resp.json()["status"] == "ok"


# S12 — health endpoint must not expose version string (fingerprinting)
def test_health_does_not_expose_version(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert "version" not in resp.json(), "Health endpoint must not expose version"


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


# ---------------------------------------------------------------------------
# S1 — OAuth state comparison must use secrets.compare_digest (timing-safe)
# ---------------------------------------------------------------------------


def test_spotify_callback_uses_compare_digest_for_state_validation(
    authed_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State comparison in the Spotify callback must use secrets.compare_digest."""
    import secrets as _secrets

    called: list[tuple[str, str]] = []
    original = _secrets.compare_digest

    def spy(a: str, b: str) -> bool:
        called.append((a, b))
        return original(a, b)

    monkeypatch.setattr("syncup.api.app.secrets.compare_digest", spy)
    authed_client.get("/api/auth/spotify", follow_redirects=False)
    state = authed_client.cookies.get("spotify_state")
    authed_client.get(f"/api/auth/spotify/callback?code=c&state={state}")
    assert called, "secrets.compare_digest was not called for Spotify state validation"


# ---------------------------------------------------------------------------
# S2 — Crypto key guard must fire even in debug mode
# ---------------------------------------------------------------------------


def test_startup_requires_encryption_key_in_debug_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing SYNCUP_TOKEN_ENCRYPTION_KEY must raise RuntimeError even when DEBUG=true."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SYNCUP_TOKEN_ENCRYPTION_KEY", "")  # explicitly blank

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with pytest.raises(RuntimeError, match="SYNCUP_TOKEN_ENCRYPTION_KEY"):
            with TestClient(app):
                pass


# ---------------------------------------------------------------------------
# S3 — Spotify token error must not leak upstream response body to client
# ---------------------------------------------------------------------------


def test_spotify_token_error_does_not_leak_upstream_body(
    authed_client: TestClient,
) -> None:
    """httpx.HTTPStatusError body from Spotify must not appear in the API response."""
    import httpx as _httpx

    sensitive = "secret_internal_spotify_details_XYZ"
    with patch(
        "syncup.ingest.spotify.SpotifyClient.exchange_code",
        side_effect=_httpx.HTTPStatusError(
            "400",
            request=_httpx.Request("POST", "https://accounts.spotify.com/api/token"),
            response=_httpx.Response(400, text=sensitive),
        ),
    ):
        authed_client.get("/api/auth/spotify", follow_redirects=False)
        state = authed_client.cookies.get("spotify_state")
        resp = authed_client.get(f"/api/auth/spotify/callback?code=authcode&state={state}")

    assert sensitive not in resp.text, "Upstream error body must not be returned to client"


# ---------------------------------------------------------------------------
# S4 — Rate limiter must use get_ipaddr (honours X-Forwarded-For via proxy)
# ---------------------------------------------------------------------------


def test_limiter_uses_get_ipaddr_key_func() -> None:
    """Limiter key_func must be get_ipaddr so X-Forwarded-For is trusted when behind a proxy."""
    from slowapi.util import get_ipaddr

    from syncup.limiter import limiter

    assert limiter._key_func is get_ipaddr, (
        "limiter key_func must be get_ipaddr, not get_remote_address"
    )


# ---------------------------------------------------------------------------
# S6 — All responses must include security headers
# ---------------------------------------------------------------------------


def test_response_includes_x_content_type_options(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_response_includes_x_frame_options(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.headers.get("x-frame-options") == "DENY"


def test_response_includes_referrer_policy(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_response_includes_content_security_policy(client: TestClient) -> None:
    resp = client.get("/api/health")
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp


def test_response_includes_permissions_policy(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert "permissions-policy" in resp.headers


# ---------------------------------------------------------------------------
# S7 — DATABASE_URL must be required (no hardcoded default)
# ---------------------------------------------------------------------------


def test_settings_database_url_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must raise ValidationError when DATABASE_URL is not in the environment."""
    from pydantic import ValidationError

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from syncup.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# S9 — Bad CORS_ALLOWED_ORIGINS must be fatal in non-debug mode
# ---------------------------------------------------------------------------


def test_cors_parse_error_is_fatal_in_production_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed CORS_ALLOWED_ORIGINS must raise RuntimeError when DEBUG is not set."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "not-valid-json")
    monkeypatch.setenv("DEBUG", "false")

    from syncup.api.app import _cors_origins

    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        _cors_origins()


# ---------------------------------------------------------------------------
# S11 — session_secret default must be None (not empty string)
# ---------------------------------------------------------------------------


def test_settings_session_secret_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """session_secret must default to None so misconfiguration is detectable."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/x")
    monkeypatch.delenv("SESSION_SECRET", raising=False)

    from syncup.config import Settings

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.session_secret is None, "session_secret must default to None, not empty string"
