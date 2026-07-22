"""Tests for /api/me and service-connection management."""
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
        "email": "me@example.com",
        "display_name": "Test User",
        "is_matchable": False,
        "onboarded": False,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


def _make_connection(**kwargs: object) -> ServiceConnection:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "service": "spotify",
        "external_user_id": "spotify-123",
        "sync_status": "pending",
        "last_synced_at": None,
        "token_expires_at": now,
        "sync_error": None,
        "access_token_encrypted": b"enc",
        "refresh_token_encrypted": b"enc",
        "created_at": now,
    }
    return ServiceConnection(**{**defaults, **kwargs})


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Unauthenticated client — used only to assert 401 behaviour."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def me_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Authenticated client — require_auth bypassed via dependency_overrides."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    mock_db.scalars.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# User data
# ---------------------------------------------------------------------------


def test_me_returns_user_data(me_client: TestClient) -> None:
    resp = me_client.get("/api/me")
    assert resp.status_code == 200
    user = resp.json()["user"]
    assert user["email"] == "me@example.com"
    assert user["display_name"] == "Test User"
    assert "id" in user
    assert "created_at" in user
    assert "updated_at" in user
    assert "is_matchable" in user
    assert "onboarded" in user
    assert "avatar_url" in user
    assert "bio" in user
    assert "discord_handle" in user
    assert "social_links" in user


# ---------------------------------------------------------------------------
# Service connections
# ---------------------------------------------------------------------------


def test_me_returns_empty_connections_when_none(
    me_client: TestClient, mock_db: MagicMock
) -> None:
    mock_db.scalars.return_value.all.return_value = []
    resp = me_client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["connections"] == []


def test_me_returns_service_connections(me_client: TestClient, mock_db: MagicMock) -> None:
    conn = _make_connection(
        service="spotify", external_user_id="REDDIT_DEV_USERNAME", sync_status="ok"
    )
    mock_db.scalars.return_value.all.return_value = [conn]

    resp = me_client.get("/api/me")
    assert resp.status_code == 200
    connections = resp.json()["connections"]
    assert len(connections) == 1
    assert connections[0]["service"] == "spotify"
    assert connections[0]["external_user_id"] == "REDDIT_DEV_USERNAME"
    assert connections[0]["sync_status"] == "ok"


def test_me_returns_multiple_connections(me_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalars.return_value.all.return_value = [
        _make_connection(service="spotify"),
        _make_connection(service="steam", external_user_id="76561198000000000"),
    ]

    resp = me_client.get("/api/me")
    assert resp.status_code == 200
    connections = resp.json()["connections"]
    assert len(connections) == 2
    services = {c["service"] for c in connections}
    assert services == {"spotify", "steam"}


def test_me_connection_includes_sync_metadata(me_client: TestClient, mock_db: MagicMock) -> None:
    conn = _make_connection(sync_status="error", sync_error="timeout")
    mock_db.scalars.return_value.all.return_value = [conn]

    resp = me_client.get("/api/me")
    c = resp.json()["connections"][0]
    assert c["sync_status"] == "error"
    assert c["sync_error"] == "timeout"
    assert "last_synced_at" in c
    assert "token_expires_at" in c


def test_me_does_not_expose_encrypted_tokens(me_client: TestClient, mock_db: MagicMock) -> None:
    conn = _make_connection()
    mock_db.scalars.return_value.all.return_value = [conn]

    resp = me_client.get("/api/me")
    connection = resp.json()["connections"][0]
    assert "access_token_encrypted" not in connection
    assert "refresh_token_encrypted" not in connection
    assert "id" not in connection


# ---------------------------------------------------------------------------
# DELETE /api/me/connections/{service}
# ---------------------------------------------------------------------------


def test_delete_connection_requires_auth(client: TestClient) -> None:
    resp = client.delete("/api/me/connections/spotify")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_delete_connection_returns_204_and_purges_user_data(
    me_client: TestClient, mock_db: MagicMock
) -> None:
    connection = _make_connection(service="spotify")
    mock_db.scalar.return_value = connection

    resp = me_client.delete("/api/me/connections/spotify")

    assert resp.status_code == 204
    assert resp.content == b""
    statements = [call.args[0] for call in mock_db.execute.call_args_list]
    assert len(statements) == 2
    assert "DELETE FROM user_items" in str(statements[0])
    assert "DELETE FROM user_embeddings" in str(statements[1])
    mock_db.delete.assert_called_once_with(connection)
    mock_db.commit.assert_called_once()


def test_delete_connection_not_found_returns_404(
    me_client: TestClient, mock_db: MagicMock
) -> None:
    mock_db.scalar.return_value = None

    resp = me_client.delete("/api/me/connections/spotify")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
    mock_db.delete.assert_not_called()
    mock_db.commit.assert_not_called()
