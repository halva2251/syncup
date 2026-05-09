"""Tests for Reddit OAuth connect routes:
GET /api/connect/reddit/oauth/start
GET /api/connect/reddit/oauth/callback
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
def reddit_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "test-reddit-client-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test-reddit-secret")
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
def reddit_client_no_creds(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Client fixture with Reddit credentials NOT configured."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "")

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
def unauthed_reddit_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "test-reddit-client-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test-reddit-secret")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/connect/reddit/oauth/start
# ---------------------------------------------------------------------------


def test_reddit_oauth_start_requires_auth(unauthed_reddit_client: TestClient) -> None:
    resp = unauthed_reddit_client.get("/api/connect/reddit/oauth/start")
    assert resp.status_code == 401


def test_reddit_oauth_start_redirects_to_reddit(reddit_client: TestClient) -> None:
    resp = reddit_client.get("/api/connect/reddit/oauth/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "reddit.com" in location


def test_reddit_oauth_start_sets_state_cookie(reddit_client: TestClient) -> None:
    resp = reddit_client.get("/api/connect/reddit/oauth/start")
    assert resp.status_code == 302
    assert "reddit_state" in resp.cookies


def test_reddit_oauth_start_not_configured_returns_503(
    reddit_client_no_creds: TestClient,
) -> None:
    resp = reddit_client_no_creds.get("/api/connect/reddit/oauth/start")
    assert resp.status_code == 503
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/connect/reddit/oauth/callback
# ---------------------------------------------------------------------------


def test_reddit_oauth_callback_state_mismatch_returns_400_even_when_unauthenticated(
    unauthed_reddit_client: TestClient,
) -> None:
    resp = unauthed_reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"reddit_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_reddit_oauth_callback_requires_auth(unauthed_reddit_client: TestClient) -> None:
    resp = unauthed_reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
        cookies={"reddit_state": "some-state"},
    )
    assert resp.status_code == 401


def test_reddit_oauth_callback_state_mismatch_returns_400(
    reddit_client: TestClient,
) -> None:
    resp = reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"reddit_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_reddit_oauth_callback_missing_state_cookie_returns_400(
    reddit_client: TestClient,
) -> None:
    resp = reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_reddit_oauth_callback_user_denied_returns_400(
    reddit_client: TestClient,
) -> None:
    """Reddit sends error=access_denied when the user denies the prompt."""
    resp = reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"state": "matching-state", "error": "access_denied"},
        cookies={"reddit_state": "matching-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "REDDIT_OAUTH_DENIED"


def test_reddit_oauth_callback_missing_code_returns_400(
    reddit_client: TestClient,
) -> None:
    """Callback with matching state but no code and no error returns 400."""
    resp = reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"state": "matching-state"},
        cookies={"reddit_state": "matching-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "REDDIT_OAUTH_MISSING_CODE"


def test_reddit_oauth_callback_success_redirects_home(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    reddit_client: TestClient,
) -> None:
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.RedditClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_at=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.RedditClient.fetch_me",
        lambda self, access_token: {"name": "testuser"},
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"encrypted")
    mock_db.scalar.return_value = None

    resp = reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"code": "valid-code", "state": "matching-state"},
        cookies={"reddit_state": "matching-state"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_reddit_oauth_callback_stores_reddit_username(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    reddit_client: TestClient,
) -> None:
    """external_user_id must be the Reddit username, not the SyncUp user UUID."""
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.RedditClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_at=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.RedditClient.fetch_me",
        lambda self, access_token: {"name": "reddit_user_xyz"},
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"enc")
    mock_db.scalar.return_value = None

    reddit_client.get(
        "/api/connect/reddit/oauth/callback",
        params={"code": "code", "state": "st"},
        cookies={"reddit_state": "st"},
    )

    added_conn: ServiceConnection = mock_db.add.call_args[0][0]
    assert added_conn.external_user_id == "reddit_user_xyz"
