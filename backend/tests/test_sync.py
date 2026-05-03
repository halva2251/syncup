"""Tests for POST /api/sync/{service} route and _do_sync_generic background task."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.api.routes.sync import (  # noqa: PLC2701
    _do_sync_generic,
    _safe_error_message,
)
from syncup.config import Settings
from syncup.db.models import ServiceConnection, User
from syncup.ingest.protocol import RawItem, TokenPair

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**kwargs: Any) -> User:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "display_name": "Test User",
        "is_matchable": False,
        "onboarded": False,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


def _make_connection(service: str, external_user_id: str = "test-id") -> ServiceConnection:
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


def _raw_item(external_id: str = "1", service_specific: bool = False) -> RawItem:
    return RawItem(
        external_id=external_id,
        name=f"Item {external_id}",
        item_type="game",
        engagement_score=0.5,
        raw_value=100.0,
        raw_type="consumption",
        metadata={},
        last_engaged_at=None,
    )


# ---------------------------------------------------------------------------
# Route fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def sync_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    mock_db.scalar.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user

    with (
        patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()),
        patch("syncup.api.routes.sync._do_sync_generic"),
    ):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def unauthed_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


def test_sync_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post("/api/sync/spotify")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_sync_invalid_service_returns_404(sync_client: TestClient) -> None:
    resp = sync_client.post("/api/sync/tiktok")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SERVICE_NOT_FOUND"


def test_sync_not_connected_returns_404(sync_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None
    resp = sync_client.post("/api/sync/spotify")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SERVICE_NOT_CONNECTED"


def test_sync_spotify_returns_syncing(sync_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_connection("spotify")
    resp = sync_client.post("/api/sync/spotify")
    assert resp.status_code == 200
    assert resp.json() == {"status": "syncing", "service": "spotify"}


def test_sync_steam_returns_syncing(sync_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_connection("steam", "76561198000000000")
    resp = sync_client.post("/api/sync/steam")
    assert resp.status_code == 200
    assert resp.json() == {"status": "syncing", "service": "steam"}


def test_sync_lastfm_returns_syncing(sync_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_connection("lastfm", "halva")
    resp = sync_client.post("/api/sync/lastfm")
    assert resp.status_code == 200
    assert resp.json() == {"status": "syncing", "service": "lastfm"}


def test_sync_sets_syncing_status_and_commits(
    sync_client: TestClient, mock_db: MagicMock
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    conn.sync_status = "ok"
    mock_db.scalar.return_value = conn

    sync_client.post("/api/sync/steam")

    assert conn.sync_status == "syncing"
    assert conn.sync_error is None
    mock_db.commit.assert_called()


def test_sync_already_syncing_returns_409(
    sync_client: TestClient, mock_db: MagicMock
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    conn.sync_status = "syncing"
    mock_db.scalar.return_value = conn

    resp = sync_client.post("/api/sync/steam")

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_SYNCING"


# ---------------------------------------------------------------------------
# Background task fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    db = MagicMock(spec=DbSession)
    db.execute.return_value.scalar_one.return_value = uuid.uuid4()
    return db


@pytest.fixture
def mock_db_factory(mock_session: MagicMock) -> MagicMock:
    factory = MagicMock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    return s


def _mock_client(items: list[RawItem], token_pair: TokenPair | None = None) -> MagicMock:
    client = MagicMock()
    client.fetch_items.return_value = items
    client.refresh_token.return_value = token_pair
    return client


# ---------------------------------------------------------------------------
# _do_sync_generic — happy path
# ---------------------------------------------------------------------------


def test_do_sync_generic_happy_path(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    user_id = uuid.uuid4()
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn
    client = _mock_client([_raw_item("730"), _raw_item("570")])

    with patch("syncup.api.routes.sync.get_client", return_value=client):
        _do_sync_generic(mock_db_factory, mock_settings, user_id, "steam")

    assert conn.sync_status == "ok"
    assert conn.last_synced_at is not None
    assert conn.sync_error is None
    mock_session.commit.assert_called()
    mock_session.close.assert_called_once()
    # 2 items × 2 execute calls (item upsert + user_item upsert) = 4
    assert mock_session.execute.call_count == 4


def test_do_sync_generic_no_connection_exits_gracefully(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_session.scalar.return_value = None
    client = _mock_client([])

    with patch("syncup.api.routes.sync.get_client", return_value=client):
        _do_sync_generic(mock_db_factory, mock_settings, uuid.uuid4(), "steam")

    client.fetch_items.assert_not_called()
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_do_sync_generic_empty_items(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn
    client = _mock_client([])

    with patch("syncup.api.routes.sync.get_client", return_value=client):
        _do_sync_generic(mock_db_factory, mock_settings, uuid.uuid4(), "steam")

    assert conn.sync_status == "ok"
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_called()


# ---------------------------------------------------------------------------
# _do_sync_generic — token refresh
# ---------------------------------------------------------------------------


def test_do_sync_generic_refresh_token_when_client_returns_pair(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    user_id = uuid.uuid4()
    conn = _make_connection("spotify", "spotify-user-id")
    conn.access_token_encrypted = b"old_access"
    conn.refresh_token_encrypted = b"old_refresh"
    mock_session.scalar.return_value = conn

    new_expiry = datetime.now(UTC) + timedelta(hours=1)
    token_pair = TokenPair(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_at=new_expiry,
    )
    client = _mock_client([], token_pair=token_pair)

    with (
        patch("syncup.api.routes.sync.get_client", return_value=client),
        patch("syncup.api.routes.sync.encrypt_token", return_value=b"enc") as mock_enc,
    ):
        _do_sync_generic(mock_db_factory, mock_settings, user_id, "spotify")

    # encrypt_token called for access + refresh
    assert mock_enc.call_count == 2
    assert conn.token_expires_at == new_expiry
    assert conn.sync_status == "ok"
    mock_session.flush.assert_called_once()


def test_do_sync_generic_no_refresh_when_client_returns_none(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn
    client = _mock_client([])  # refresh_token returns None by default

    with (
        patch("syncup.api.routes.sync.get_client", return_value=client),
        patch("syncup.api.routes.sync.encrypt_token") as mock_enc,
    ):
        _do_sync_generic(mock_db_factory, mock_settings, uuid.uuid4(), "steam")

    mock_enc.assert_not_called()
    mock_session.flush.assert_not_called()


# ---------------------------------------------------------------------------
# _do_sync_generic — error handling
# ---------------------------------------------------------------------------


def test_do_sync_generic_upstream_error_sets_error_status(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn
    client = MagicMock()
    client.refresh_token.return_value = None
    client.fetch_items.side_effect = httpx.RequestError("timeout")

    with patch("syncup.api.routes.sync.get_client", return_value=client):
        _do_sync_generic(mock_db_factory, mock_settings, uuid.uuid4(), "steam")

    mock_session.rollback.assert_called_once()
    mock_session.execute.assert_called()  # _set_sync_error UPDATE
    mock_session.close.assert_called_once()


def test_do_sync_generic_set_sync_error_self_failure_is_handled(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    """If _set_sync_error's own UPDATE fails, it rolls back and logs without raising."""
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn
    mock_session.execute.side_effect = Exception("DB is down")
    client = MagicMock()
    client.refresh_token.return_value = None
    client.fetch_items.side_effect = httpx.RequestError("timeout")

    with patch("syncup.api.routes.sync.get_client", return_value=client):
        _do_sync_generic(mock_db_factory, mock_settings, uuid.uuid4(), "steam")

    # rollback called twice: once for main failure, once inside _set_sync_error
    assert mock_session.rollback.call_count == 2
    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# _safe_error_message
# ---------------------------------------------------------------------------


def test_safe_error_message_sanitises_upstream_responses() -> None:
    http_err = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=MagicMock(status_code=503)
    )
    assert _safe_error_message(http_err) == "Upstream API returned 503"

    net_err = httpx.RequestError("connection refused")
    assert _safe_error_message(net_err) == "Network error reaching upstream service"

    val_err = ValueError("Missing refresh token — reconnect Spotify via OAuth")
    assert _safe_error_message(val_err) == str(val_err)

    generic = RuntimeError("internal traceback with /home/halva/secrets")
    assert _safe_error_message(generic) == "Sync failed — please retry"
