"""Tests for Trakt OAuth connect routes:
GET /api/connect/trakt/oauth/start
GET /api/connect/trakt/oauth/callback
"""
from __future__ import annotations

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
def trakt_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("TRAKT_CLIENT_ID", "test-trakt-client-id")
    monkeypatch.setenv("TRAKT_CLIENT_SECRET", "test-trakt-secret")
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
def trakt_client_no_creds(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Client fixture with Trakt credentials NOT configured."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TRAKT_CLIENT_ID", "")
    monkeypatch.setenv("TRAKT_CLIENT_SECRET", "")

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
def unauthed_trakt_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("TRAKT_CLIENT_ID", "test-trakt-client-id")
    monkeypatch.setenv("TRAKT_CLIENT_SECRET", "test-trakt-secret")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/connect/trakt/oauth/start
# ---------------------------------------------------------------------------


def test_trakt_oauth_start_requires_auth(unauthed_trakt_client: TestClient) -> None:
    resp = unauthed_trakt_client.get("/api/connect/trakt/oauth/start")
    assert resp.status_code == 401


def test_trakt_oauth_start_redirects_to_trakt(trakt_client: TestClient) -> None:
    resp = trakt_client.get("/api/connect/trakt/oauth/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "trakt.tv" in location


def test_trakt_oauth_start_sets_state_cookie(trakt_client: TestClient) -> None:
    resp = trakt_client.get("/api/connect/trakt/oauth/start")
    assert resp.status_code == 302
    assert "trakt_state" in resp.cookies


def test_trakt_oauth_start_not_configured_returns_503(
    trakt_client_no_creds: TestClient,
) -> None:
    resp = trakt_client_no_creds.get("/api/connect/trakt/oauth/start")
    assert resp.status_code == 503
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/connect/trakt/oauth/callback
# ---------------------------------------------------------------------------


def test_trakt_oauth_callback_state_mismatch_returns_400_even_when_unauthenticated(
    unauthed_trakt_client: TestClient,
) -> None:
    resp = unauthed_trakt_client.get(
        "/api/connect/trakt/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"trakt_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_trakt_oauth_callback_requires_auth(unauthed_trakt_client: TestClient) -> None:
    resp = unauthed_trakt_client.get(
        "/api/connect/trakt/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
        cookies={"trakt_state": "some-state"},
    )
    assert resp.status_code == 401


def test_trakt_oauth_callback_state_mismatch_returns_400(
    trakt_client: TestClient,
) -> None:
    resp = trakt_client.get(
        "/api/connect/trakt/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"trakt_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_trakt_oauth_callback_missing_state_cookie_returns_400(
    trakt_client: TestClient,
) -> None:
    resp = trakt_client.get(
        "/api/connect/trakt/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_trakt_oauth_callback_success_redirects_home(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    trakt_client: TestClient,
) -> None:
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.TraktClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_at=datetime(2025, 6, 1, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.TraktClient.fetch_me",
        lambda self, access_token: {"username": "testuser"},
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"encrypted")
    mock_db.scalar.return_value = None

    resp = trakt_client.get(
        "/api/connect/trakt/oauth/callback",
        params={"code": "valid-code", "state": "matching-state"},
        cookies={"trakt_state": "matching-state"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_trakt_oauth_callback_stores_trakt_username(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    trakt_client: TestClient,
) -> None:
    """external_user_id must be the Trakt username, not the SyncUp user UUID."""
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.TraktClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_at=datetime(2025, 6, 1, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.TraktClient.fetch_me",
        lambda self, access_token: {"username": "trakt_user_123"},
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"enc")
    mock_db.scalar.return_value = None

    trakt_client.get(
        "/api/connect/trakt/oauth/callback",
        params={"code": "code", "state": "st"},
        cookies={"trakt_state": "st"},
    )

    added_conn: ServiceConnection = mock_db.add.call_args[0][0]
    assert added_conn.external_user_id == "trakt_user_123"
