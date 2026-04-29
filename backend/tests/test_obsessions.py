"""Tests for GET/POST/DELETE /api/me/obsessions."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import ManualObsession, User

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


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


def _make_obsession(**kwargs: object) -> ManualObsession:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "category": "game",
        "name": "Disco Elysium",
        "weight": 1.5,
        "item_id": None,
        "created_at": datetime.now(UTC),
    }
    return ManualObsession(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Unauthenticated client."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def obs_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Authenticated client with empty DB by default."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    mock_db.scalars.return_value.all.return_value = []
    mock_db.scalar.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: _make_user()
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_list_obsessions_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/me/obsessions")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_obsession_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/me/obsessions", json={"category": "game", "name": "Disco Elysium"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/me/obsessions
# ---------------------------------------------------------------------------


def test_list_obsessions_returns_empty(obs_client: TestClient) -> None:
    resp = obs_client.get("/api/me/obsessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_obsessions_returns_items(obs_client: TestClient, mock_db: MagicMock) -> None:
    obs = _make_obsession(category="book", name="Blindsight", weight=2.0)
    mock_db.scalars.return_value.all.return_value = [obs]

    resp = obs_client.get("/api/me/obsessions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["category"] == "book"
    assert items[0]["name"] == "Blindsight"
    assert items[0]["weight"] == pytest.approx(2.0)
    assert "id" in items[0]
    assert "created_at" in items[0]


# ---------------------------------------------------------------------------
# POST /api/me/obsessions
# ---------------------------------------------------------------------------


def test_create_obsession_returns_201(obs_client: TestClient) -> None:
    resp = obs_client.post(
        "/api/me/obsessions", json={"category": "game", "name": "Disco Elysium"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "game"
    assert body["name"] == "Disco Elysium"
    assert "id" in body
    assert "created_at" in body


def test_create_obsession_default_weight(obs_client: TestClient) -> None:
    resp = obs_client.post("/api/me/obsessions", json={"category": "music", "name": "Arca"})
    assert resp.status_code == 201
    assert resp.json()["weight"] == pytest.approx(1.0)


def test_create_obsession_explicit_weight(obs_client: TestClient) -> None:
    resp = obs_client.post(
        "/api/me/obsessions",
        json={"category": "film", "name": "Stalker", "weight": 2.5},
    )
    assert resp.status_code == 201
    assert resp.json()["weight"] == pytest.approx(2.5)


def test_create_obsession_invalid_category_returns_422(obs_client: TestClient) -> None:
    resp = obs_client.post(
        "/api/me/obsessions", json={"category": "podcast", "name": "Something"}
    )
    assert resp.status_code == 422


def test_create_obsession_empty_name_returns_422(obs_client: TestClient) -> None:
    resp = obs_client.post("/api/me/obsessions", json={"category": "game", "name": ""})
    assert resp.status_code == 422


def test_create_obsession_zero_weight_returns_422(obs_client: TestClient) -> None:
    resp = obs_client.post(
        "/api/me/obsessions", json={"category": "game", "name": "Disco Elysium", "weight": 0}
    )
    assert resp.status_code == 422


def test_create_obsession_negative_weight_returns_422(obs_client: TestClient) -> None:
    resp = obs_client.post(
        "/api/me/obsessions",
        json={"category": "game", "name": "Disco Elysium", "weight": -1.0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/me/obsessions/{id}
# ---------------------------------------------------------------------------


def test_delete_obsession_returns_204(obs_client: TestClient, mock_db: MagicMock) -> None:
    obs = _make_obsession()
    mock_db.scalar.return_value = obs

    resp = obs_client.delete(f"/api/me/obsessions/{obs.id}")
    assert resp.status_code == 204
    assert resp.content == b""
    mock_db.delete.assert_called_once_with(obs)
    mock_db.commit.assert_called()


def test_delete_obsession_not_found_returns_404(obs_client: TestClient) -> None:
    resp = obs_client.delete(f"/api/me/obsessions/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_delete_obsession_wrong_user_returns_404(
    obs_client: TestClient, mock_db: MagicMock
) -> None:
    # scalar returns None because the query filters by user_id — other user's obsession not visible
    mock_db.scalar.return_value = None

    resp = obs_client.delete(f"/api/me/obsessions/{uuid.uuid4()}")
    assert resp.status_code == 404
