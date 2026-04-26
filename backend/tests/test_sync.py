"""Tests for POST /api/sync/{service} routes and background task functions."""
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
    _do_sync_lastfm,
    _do_sync_spotify,
    _do_sync_steam,
)
from syncup.config import Settings
from syncup.db.models import ServiceConnection, User
from syncup.ingest.spotify import TokenResponse

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

    def noop(*_: Any) -> None:
        pass

    with (
        patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()),
        patch(
            "syncup.api.routes.sync._SYNC_TASKS",
            {"spotify": noop, "steam": noop, "lastfm": noop},
        ),
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


def test_sync_invalid_service_returns_400(sync_client: TestClient) -> None:
    resp = sync_client.post("/api/sync/tiktok")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SERVICE"


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
    return MagicMock(spec=DbSession)


@pytest.fixture
def mock_db_factory(mock_session: MagicMock) -> MagicMock:
    factory = MagicMock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.steam_api_key = "test-steam-key"
    s.lastfm_api_key = "test-lastfm-key"
    s.spotify_client_id = "test-spotify-id"
    s.spotify_redirect_uri = "http://127.0.0.1:3000/api/auth/spotify/callback"
    return s


# ---------------------------------------------------------------------------
# _do_sync_steam
# ---------------------------------------------------------------------------


def test_do_sync_steam_happy_path(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    user_id = uuid.uuid4()
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn

    with patch("syncup.api.routes.sync.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_owned_games.return_value = [
            {"appid": 730, "name": "Counter-Strike 2", "playtime_forever": 1000},
            {"appid": 570, "name": "Dota 2", "playtime_forever": 500},
        ]
        _do_sync_steam(mock_db_factory, mock_settings, user_id)

    assert conn.sync_status == "ok"
    assert conn.last_synced_at is not None
    assert conn.sync_error is None
    mock_session.commit.assert_called()
    mock_session.close.assert_called_once()
    # 2 games × 2 execute calls (item upsert + user_item upsert) = 4
    assert mock_session.execute.call_count == 4


def test_do_sync_steam_no_connection_exits_gracefully(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_session.scalar.return_value = None
    _do_sync_steam(mock_db_factory, mock_settings, uuid.uuid4())
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_do_sync_steam_empty_library(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn

    with patch("syncup.api.routes.sync.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_owned_games.return_value = []
        _do_sync_steam(mock_db_factory, mock_settings, uuid.uuid4())

    assert conn.sync_status == "ok"
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_called()


def test_do_sync_steam_upstream_error_sets_error_status(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn

    with patch("syncup.api.routes.sync.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_owned_games.side_effect = httpx.RequestError("timeout")
        _do_sync_steam(mock_db_factory, mock_settings, uuid.uuid4())

    mock_session.rollback.assert_called_once()
    mock_session.execute.assert_called()  # _set_sync_error UPDATE
    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# _do_sync_lastfm
# ---------------------------------------------------------------------------


def test_do_sync_lastfm_happy_path(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    user_id = uuid.uuid4()
    conn = _make_connection("lastfm", "halva")
    mock_session.scalar.return_value = conn

    with patch("syncup.api.routes.sync.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.return_value = [
            {"name": "Radiohead", "mbid": "a74b1b7f", "playcount": "1000"},
            {"name": "Björk", "mbid": "", "playcount": "500"},
        ]
        instance.get_top_tracks.return_value = [
            {
                "name": "Karma Police",
                "mbid": "abc123",
                "artist": {"name": "Radiohead"},
                "playcount": "200",
            },
        ]
        _do_sync_lastfm(mock_db_factory, mock_settings, user_id)

    assert conn.sync_status == "ok"
    assert conn.last_synced_at is not None
    # 2 artists + 1 track = 3 items × 2 upserts = 6 execute calls
    assert mock_session.execute.call_count == 6
    mock_session.commit.assert_called()
    mock_session.close.assert_called_once()


def test_do_sync_lastfm_empty_mbid_uses_name_as_external_id(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("lastfm", "halva")
    mock_session.scalar.return_value = conn

    with patch("syncup.api.routes.sync.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.return_value = [
            {"name": "Björk", "mbid": "", "playcount": "500"},
        ]
        instance.get_top_tracks.return_value = []
        _do_sync_lastfm(mock_db_factory, mock_settings, uuid.uuid4())

    # 1 artist × 2 upserts = 2 execute calls
    assert mock_session.execute.call_count == 2


def test_do_sync_lastfm_upstream_error_sets_error_status(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("lastfm", "halva")
    mock_session.scalar.return_value = conn

    with patch("syncup.api.routes.sync.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = ValueError("Last.fm API error 6: User not found")
        _do_sync_lastfm(mock_db_factory, mock_settings, uuid.uuid4())

    mock_session.rollback.assert_called_once()
    mock_session.execute.assert_called()
    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# _do_sync_spotify
# ---------------------------------------------------------------------------


def test_do_sync_spotify_fresh_token_no_refresh(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    user_id = uuid.uuid4()
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
    conn.access_token_encrypted = b"encrypted_access"
    mock_session.scalar.return_value = conn

    with (
        patch("syncup.api.routes.sync.decrypt_token", return_value="access-token"),
        patch("syncup.api.routes.sync.encrypt_token"),
        patch("syncup.api.routes.sync.SpotifyClient") as mock_spotify_cls,
    ):
        instance = mock_spotify_cls.return_value.__enter__.return_value
        instance.fetch_top_artists.return_value = []
        instance.fetch_recently_played.return_value = []
        _do_sync_spotify(mock_db_factory, mock_settings, user_id)

    instance.refresh_access_token.assert_not_called()
    assert conn.sync_status == "ok"
    mock_session.close.assert_called_once()


def test_do_sync_spotify_expired_token_triggers_refresh(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    user_id = uuid.uuid4()
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = datetime.now(UTC) - timedelta(minutes=10)
    conn.access_token_encrypted = b"old_access"
    conn.refresh_token_encrypted = b"old_refresh"
    mock_session.scalar.return_value = conn

    new_tokens = TokenResponse(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_in=3600,
        token_type="Bearer",
    )

    with (
        patch("syncup.api.routes.sync.decrypt_token", return_value="old-refresh-token"),
        patch("syncup.api.routes.sync.encrypt_token", return_value=b"new_enc") as mock_encrypt,
        patch("syncup.api.routes.sync.SpotifyClient") as mock_spotify_cls,
    ):
        instance = mock_spotify_cls.return_value.__enter__.return_value
        instance.refresh_access_token.return_value = new_tokens
        instance.fetch_top_artists.return_value = []
        instance.fetch_recently_played.return_value = []
        _do_sync_spotify(mock_db_factory, mock_settings, user_id)

    instance.refresh_access_token.assert_called_once_with("old-refresh-token")
    assert mock_encrypt.call_count == 2  # access + refresh token
    assert conn.token_expires_at is not None
    assert conn.sync_status == "ok"
    mock_session.flush.assert_called_once()


def test_do_sync_spotify_token_is_none_skips_refresh(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    """token_expires_at=None means no expiry check; use access token directly."""
    user_id = uuid.uuid4()
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = None
    conn.access_token_encrypted = b"encrypted"
    mock_session.scalar.return_value = conn

    with (
        patch("syncup.api.routes.sync.decrypt_token", return_value="access-token"),
        patch("syncup.api.routes.sync.SpotifyClient") as mock_spotify_cls,
    ):
        instance = mock_spotify_cls.return_value.__enter__.return_value
        instance.fetch_top_artists.return_value = [
            {"id": "artist1", "name": "Arca", "genres": ["experimental"]},
        ]
        instance.fetch_recently_played.return_value = []
        _do_sync_spotify(mock_db_factory, mock_settings, user_id)

    instance.refresh_access_token.assert_not_called()
    assert conn.sync_status == "ok"
    # 1 artist × 2 upserts = 2 execute calls
    assert mock_session.execute.call_count == 2


def test_do_sync_spotify_upstream_error_sets_error_status(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = None
    conn.access_token_encrypted = b"encrypted"
    mock_session.scalar.return_value = conn

    with (
        patch("syncup.api.routes.sync.decrypt_token", return_value="access-token"),
        patch("syncup.api.routes.sync.SpotifyClient") as mock_spotify_cls,
    ):
        instance = mock_spotify_cls.return_value.__enter__.return_value
        instance.fetch_top_artists.side_effect = httpx.RequestError("timeout")
        _do_sync_spotify(mock_db_factory, mock_settings, uuid.uuid4())

    mock_session.rollback.assert_called_once()
    mock_session.execute.assert_called()
    mock_session.close.assert_called_once()


def test_do_sync_spotify_recently_played_deduplication(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    """Same track appearing 3 times in recently-played → 1 item, score=3."""
    user_id = uuid.uuid4()
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = None
    conn.access_token_encrypted = b"encrypted"
    mock_session.scalar.return_value = conn

    track = {"id": "track1", "name": "Tears", "artists": [{"name": "Arca"}]}
    recently_played = [{"track": track}, {"track": track}, {"track": track}]

    with (
        patch("syncup.api.routes.sync.decrypt_token", return_value="access-token"),
        patch("syncup.api.routes.sync.SpotifyClient") as mock_spotify_cls,
    ):
        instance = mock_spotify_cls.return_value.__enter__.return_value
        instance.fetch_top_artists.return_value = []
        instance.fetch_recently_played.return_value = recently_played
        _do_sync_spotify(mock_db_factory, mock_settings, user_id)

    assert conn.sync_status == "ok"
    # 1 deduplicated track × 2 upserts = 2 execute calls
    assert mock_session.execute.call_count == 2


def test_do_sync_spotify_no_connection_exits_gracefully(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_session.scalar.return_value = None
    _do_sync_spotify(mock_db_factory, mock_settings, uuid.uuid4())
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_do_sync_spotify_missing_refresh_token_sets_error(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = datetime.now(UTC) - timedelta(hours=1)
    conn.refresh_token_encrypted = None
    mock_session.scalar.return_value = conn

    _do_sync_spotify(mock_db_factory, mock_settings, uuid.uuid4())

    mock_session.rollback.assert_called_once()
    mock_session.execute.assert_called()  # _set_sync_error UPDATE
    mock_session.close.assert_called_once()


def test_do_sync_spotify_missing_access_token_sets_error(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    conn = _make_connection("spotify", "spotify-user-id")
    conn.token_expires_at = None
    conn.access_token_encrypted = None
    mock_session.scalar.return_value = conn

    _do_sync_spotify(mock_db_factory, mock_settings, uuid.uuid4())

    mock_session.rollback.assert_called_once()
    mock_session.execute.assert_called()
    mock_session.close.assert_called_once()


def test_do_sync_lastfm_no_connection_exits_gracefully(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_session.scalar.return_value = None
    _do_sync_lastfm(mock_db_factory, mock_settings, uuid.uuid4())
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_set_sync_error_self_failure_is_handled(
    mock_db_factory: MagicMock,
    mock_session: MagicMock,
    mock_settings: MagicMock,
) -> None:
    """If _set_sync_error's own UPDATE fails, it rolls back and logs without raising."""
    conn = _make_connection("steam", "76561198000000000")
    mock_session.scalar.return_value = conn
    mock_session.execute.side_effect = Exception("DB is down")

    with patch("syncup.api.routes.sync.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_owned_games.side_effect = httpx.RequestError("timeout")
        _do_sync_steam(mock_db_factory, mock_settings, uuid.uuid4())

    # rollback called twice: once for main failure, once inside _set_sync_error
    assert mock_session.rollback.call_count == 2
    mock_session.close.assert_called_once()


def test_safe_error_message_sanitises_upstream_responses() -> None:
    from syncup.api.routes.sync import _safe_error_message  # noqa: PLC2701

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
