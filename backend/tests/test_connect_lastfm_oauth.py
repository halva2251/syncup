"""Tests for Last.fm web-auth connect routes:
GET /api/connect/lastfm/oauth/start
GET /api/connect/lastfm/oauth/callback
"""

from __future__ import annotations

import urllib.parse
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import ServiceConnection, User


def _make_user(**kwargs: object) -> User:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "display_name": "Test User",
        "is_matchable": False,
        "onboarded": False,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def lastfm_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("LASTFM_API_KEY", "test-lastfm-key")
    monkeypatch.setenv("LASTFM_SHARED_SECRET", "test-lastfm-secret")
    monkeypatch.setenv("FRONTEND_URL", "")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    mock_db.scalar.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def lastfm_client_no_creds(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Client fixture with Last.fm shared secret NOT configured."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("LASTFM_API_KEY", "test-lastfm-key")
    monkeypatch.setenv("LASTFM_SHARED_SECRET", "")
    monkeypatch.setenv("FRONTEND_URL", "")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def unauthed_lastfm_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("LASTFM_API_KEY", "test-lastfm-key")
    monkeypatch.setenv("LASTFM_SHARED_SECRET", "test-lastfm-secret")
    monkeypatch.setenv("FRONTEND_URL", "")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/connect/lastfm/oauth/start
# ---------------------------------------------------------------------------


def test_lastfm_oauth_start_requires_auth(unauthed_lastfm_client: TestClient) -> None:
    resp = unauthed_lastfm_client.get("/api/connect/lastfm/oauth/start")
    assert resp.status_code == 401


def test_lastfm_oauth_start_redirects_to_lastfm(lastfm_client: TestClient) -> None:
    resp = lastfm_client.get("/api/connect/lastfm/oauth/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "last.fm/api/auth" in location
    assert "api_key=test-lastfm-key" in location
    parsed = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed.query)
    assert "cb" in params
    assert "state=" in params["cb"][0]


def test_lastfm_oauth_start_sets_state_cookie(lastfm_client: TestClient) -> None:
    resp = lastfm_client.get("/api/connect/lastfm/oauth/start")
    assert resp.status_code == 302
    assert "lastfm_state" in resp.cookies


def test_lastfm_oauth_start_not_configured_returns_error(
    lastfm_client_no_creds: TestClient,
) -> None:
    resp = lastfm_client_no_creds.get("/api/connect/lastfm/oauth/start")
    assert resp.status_code == 503
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/connect/lastfm/oauth/callback
# ---------------------------------------------------------------------------


def test_lastfm_oauth_callback_requires_auth(unauthed_lastfm_client: TestClient) -> None:
    resp = unauthed_lastfm_client.get(
        "/api/connect/lastfm/oauth/callback",
        params={"token": "some-token", "state": "some-state"},
        cookies={"lastfm_state": "some-state"},
    )
    assert resp.status_code == 401


def test_lastfm_oauth_callback_state_mismatch_returns_400(
    unauthed_lastfm_client: TestClient,
) -> None:
    resp = unauthed_lastfm_client.get(
        "/api/connect/lastfm/oauth/callback",
        params={"token": "some-token", "state": "wrong-state"},
        cookies={"lastfm_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_lastfm_oauth_callback_missing_state_cookie_returns_400(
    lastfm_client: TestClient,
) -> None:
    resp = lastfm_client.get(
        "/api/connect/lastfm/oauth/callback",
        params={"token": "some-token", "state": "some-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_lastfm_oauth_callback_success_redirects_home(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    lastfm_client: TestClient,
) -> None:
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.LastfmClient.exchange_token",
        lambda self, token: (TokenPair(access_token="session-key", refresh_token=None, expires_at=None), "lastfm_user"),
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"encrypted")
    mock_db.scalar.return_value = None

    resp = lastfm_client.get(
        "/api/connect/lastfm/oauth/callback",
        params={"token": "valid-token", "state": "matching-state"},
        cookies={"lastfm_state": "matching-state"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://127.0.0.1:3001"


def test_lastfm_oauth_callback_stores_username_and_session_key(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    lastfm_client: TestClient,
) -> None:
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.LastfmClient.exchange_token",
        lambda self, token: (TokenPair(access_token="sk-123", refresh_token=None, expires_at=None), "lastfm_user"),
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"enc")
    mock_db.scalar.return_value = None

    lastfm_client.get(
        "/api/connect/lastfm/oauth/callback",
        params={"token": "t", "state": "st"},
        cookies={"lastfm_state": "st"},
    )

    added_conn: ServiceConnection = mock_db.add.call_args[0][0]
    assert added_conn.external_user_id == "lastfm_user"
    assert added_conn.access_token_encrypted == b"enc"


def test_lastfm_oauth_callback_uses_compare_digest(
    lastfm_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import secrets as _secrets

    called: list[tuple[str, str]] = []
    original = _secrets.compare_digest

    def spy(a: str, b: str) -> bool:
        called.append((a, b))
        return original(a, b)

    monkeypatch.setattr("syncup.api.routes.connect.secrets.compare_digest", spy)
    lastfm_client.get(
        "/api/connect/lastfm/oauth/callback",
        params={"token": "t", "state": "st"},
        cookies={"lastfm_state": "st"},
    )
    assert called, "secrets.compare_digest was not called for Last.fm state validation"
