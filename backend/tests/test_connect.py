"""Tests for POST /api/connect/steam and POST /api/connect/lastfm."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
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
def connect_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    mock_db.scalar.return_value = None  # no existing connection by default

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
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
# POST /api/connect/steam
# ---------------------------------------------------------------------------


def test_steam_connect_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post("/api/connect/steam", json={"steam_id": "76561198000000000"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_steam_connect_with_steam_id(connect_client: TestClient, mock_db: MagicMock) -> None:
    steam_id = "76561198000000000"
    mock_db.scalar.return_value = None

    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.return_value = {"steamid": steam_id, "personaname": "halva"}
        # db.add() sets conn, then db.commit() — mock scalar returns None (new connection)
        # after db.add the ORM tracks it; we just check mock calls and response shape
        mock_db.scalar.return_value = None

        resp = connect_client.post("/api/connect/steam", json={"steam_id": steam_id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "steam"
    assert body["external_user_id"] == steam_id
    assert body["sync_status"] == "pending"


def test_steam_connect_with_vanity_url(connect_client: TestClient, mock_db: MagicMock) -> None:
    steam_id = "76561198000000000"

    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.resolve_vanity_url.return_value = steam_id
        instance.get_player_summary.return_value = {"steamid": steam_id, "personaname": "halva"}
        mock_db.scalar.return_value = None

        resp = connect_client.post("/api/connect/steam", json={"vanity_url": "halva"})

    assert resp.status_code == 200
    instance.resolve_vanity_url.assert_called_once_with("halva")
    assert resp.json()["external_user_id"] == steam_id


def test_steam_connect_vanity_not_found_returns_404(
    connect_client: TestClient,
) -> None:
    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.resolve_vanity_url.side_effect = ValueError("Vanity URL 'nobody' not found")

        resp = connect_client.post("/api/connect/steam", json={"vanity_url": "nobody"})

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "STEAM_USER_NOT_FOUND"


def test_steam_connect_steam_id_no_profile_returns_404(
    connect_client: TestClient,
) -> None:
    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.side_effect = ValueError("No Steam profile found")

        resp = connect_client.post("/api/connect/steam", json={"steam_id": "99999"})

    assert resp.status_code == 404


def test_steam_connect_missing_both_fields_returns_422(
    connect_client: TestClient,
) -> None:
    resp = connect_client.post("/api/connect/steam", json={})
    assert resp.status_code == 422


def test_steam_connect_both_fields_returns_422(connect_client: TestClient) -> None:
    resp = connect_client.post(
        "/api/connect/steam",
        json={"steam_id": "76561198000000000", "vanity_url": "halva"},
    )
    assert resp.status_code == 422


def test_steam_connect_upstream_error_returns_502(connect_client: TestClient) -> None:
    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.side_effect = httpx.RequestError("timeout")

        resp = connect_client.post("/api/connect/steam", json={"steam_id": "76561198000000000"})

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_steam_connect_updates_existing_connection(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    steam_id = "76561198000000000"
    existing = _make_connection("steam", "old-id")
    mock_db.scalar.return_value = existing

    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.return_value = {"steamid": steam_id, "personaname": "halva"}

        resp = connect_client.post("/api/connect/steam", json={"steam_id": steam_id})

    assert resp.status_code == 200
    assert existing.external_user_id == steam_id
    assert existing.sync_status == "pending"
    assert existing.sync_error is None


# ---------------------------------------------------------------------------
# POST /api/connect/lastfm
# ---------------------------------------------------------------------------


def test_lastfm_connect_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post("/api/connect/lastfm", json={"username": "halva"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_lastfm_connect_valid_username(connect_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.return_value = [{"name": "Radiohead", "playcount": "500"}]

        resp = connect_client.post("/api/connect/lastfm", json={"username": "halva"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "lastfm"
    assert body["external_user_id"] == "halva"
    assert body["sync_status"] == "pending"
    instance.get_top_artists.assert_called_once_with("halva", limit=1)


def test_lastfm_connect_user_not_found_returns_404(connect_client: TestClient) -> None:
    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = ValueError("Last.fm API error 6: User not found")

        resp = connect_client.post("/api/connect/lastfm", json={"username": "nobody_here_xyz"})

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LASTFM_USER_NOT_FOUND"


def test_lastfm_connect_upstream_error_returns_502(connect_client: TestClient) -> None:
    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = httpx.RequestError("timeout")

        resp = connect_client.post("/api/connect/lastfm", json={"username": "halva"})

    assert resp.status_code == 502


def test_lastfm_connect_empty_username_returns_422(connect_client: TestClient) -> None:
    resp = connect_client.post("/api/connect/lastfm", json={"username": ""})
    assert resp.status_code == 422


def test_lastfm_connect_updates_existing_connection(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    existing = _make_connection("lastfm", "old-username")
    mock_db.scalar.return_value = existing

    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.return_value = [{"name": "Radiohead"}]

        resp = connect_client.post("/api/connect/lastfm", json={"username": "halva"})

    assert resp.status_code == 200
    assert existing.external_user_id == "halva"
    assert existing.sync_status == "pending"
