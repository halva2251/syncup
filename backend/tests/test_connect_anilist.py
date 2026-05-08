"""Tests for AniList OAuth connect routes:
GET /api/connect/anilist/oauth/start
GET /api/connect/anilist/oauth/callback
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


def _make_connection(service: str, external_user_id: str) -> ServiceConnection:
    now = datetime.now(UTC)
    return ServiceConnection(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        service=service,
        external_user_id=external_user_id,
        sync_status="pending",
        last_synced_at=None,
        token_expires_at=None,
        sync_error=None,
        access_token_encrypted=None,
        refresh_token_encrypted=None,
        created_at=now,
    )


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def anilist_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("ANILIST_CLIENT_ID", "test-anilist-client-id")
    monkeypatch.setenv("ANILIST_CLIENT_SECRET", "test-anilist-secret")
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
def anilist_client_no_creds(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Client fixture with AniList credentials NOT configured."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    # Deliberately NOT setting ANILIST_CLIENT_ID / ANILIST_CLIENT_SECRET

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
def unauthed_anilist_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("ANILIST_CLIENT_ID", "test-anilist-client-id")
    monkeypatch.setenv("ANILIST_CLIENT_SECRET", "test-anilist-secret")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/connect/anilist/oauth/start
# ---------------------------------------------------------------------------


def test_anilist_oauth_start_requires_auth(unauthed_anilist_client: TestClient) -> None:
    resp = unauthed_anilist_client.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 401


def test_anilist_oauth_start_redirects_to_anilist(anilist_client: TestClient) -> None:
    resp = anilist_client.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "anilist.co" in location


def test_anilist_oauth_start_sets_state_cookie(anilist_client: TestClient) -> None:
    resp = anilist_client.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 302
    assert "anilist_state" in resp.cookies


def test_anilist_oauth_start_not_configured_returns_error(
    anilist_client_no_creds: TestClient,
) -> None:
    resp = anilist_client_no_creds.get("/api/connect/anilist/oauth/start")
    assert resp.status_code in (400, 503)
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/connect/anilist/oauth/callback
# ---------------------------------------------------------------------------


def test_anilist_oauth_callback_requires_auth(unauthed_anilist_client: TestClient) -> None:
    resp = unauthed_anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
        cookies={"anilist_state": "some-state"},
    )
    assert resp.status_code == 401


def test_anilist_oauth_callback_state_mismatch_returns_400(
    anilist_client: TestClient,
) -> None:
    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"anilist_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_anilist_oauth_callback_missing_state_cookie_returns_400(
    anilist_client: TestClient,
) -> None:
    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
        # no state cookie set
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_anilist_oauth_callback_success_redirects_home(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    anilist_client: TestClient,
) -> None:
    from syncup.ingest.protocol import TokenPair

    monkeypatch.setattr(
        "syncup.api.routes.connect.AniListClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_at=None,
        ),
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"encrypted")
    mock_db.scalar.return_value = None  # no existing connection

    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "valid-code", "state": "matching-state"},
        cookies={"anilist_state": "matching-state"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"
