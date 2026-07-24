"""Tests for PATCH /api/me/items/{item_id} — item exclusion toggle."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import Item, User, UserItem
from syncup.limiter import limiter as _rate_limiter

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
        "onboarded": True,
        "languages": None,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


def _make_item(**kwargs: object) -> Item:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "service": "steam",
        "item_type": "game",
        "external_id": str(uuid.uuid4()),
        "name": "Disco Elysium",
        "meta": {},
        "embedding": None,
        "embedding_computed_at": None,
        "created_at": datetime.now(UTC),
    }
    return Item(**{**defaults, **kwargs})


def _make_user_item(
    user_id: uuid.UUID,
    item: Item,
    excluded: bool = False,
    engagement_score: float = 0.8,
) -> UserItem:
    ui = UserItem()
    ui.id = uuid.uuid4()
    ui.user_id = user_id
    ui.item_id = item.id
    ui.item = item
    ui.engagement_score = engagement_score
    ui.raw_value = 100.0
    ui.raw_type = "consumption"
    ui.excluded = excluded
    ui.last_engaged_at = datetime.now(UTC)
    ui.fetched_at = datetime.now(UTC)
    return ui


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def auth_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[tuple[TestClient, User, MagicMock], None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    user = _make_user()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: user
    _rate_limiter.enabled = False
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c, user, mock_db
    _rate_limiter.enabled = True
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def unauth_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.patch(f"/api/me/items/{uuid.uuid4()}", json={"excluded": True})
    assert resp.status_code == 401


def test_list_taste_items_returns_selectable_owned_items(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    item = _make_item(name="Disco Elysium", service="steam", item_type="game")
    user_item = _make_user_item(user.id, item)
    db.scalars.return_value.all.return_value = [user_item]

    resp = client.get("/api/me/items")

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "id": str(item.id),
            "name": "Disco Elysium",
            "service": "steam",
            "item_type": "game",
        }
    ]


# ---------------------------------------------------------------------------
# 404 — item not found or belongs to another user
# ---------------------------------------------------------------------------


def test_unknown_item_id_returns_404(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    db.scalar.return_value = None

    resp = client.patch(f"/api/me/items/{uuid.uuid4()}", json={"excluded": True})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_another_users_item_returns_404(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """item_id belongs to a different user — must 404, not 403 (don't leak existence)."""
    client, user, db = auth_client
    # Simulate the query returning None because the WHERE user_id = user.id clause filtered it
    db.scalar.return_value = None

    resp = client.patch(f"/api/me/items/{uuid.uuid4()}", json={"excluded": True})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Success — exclude
# ---------------------------------------------------------------------------


def test_exclude_item_sets_excluded_true(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    item = _make_item()
    user_item = _make_user_item(user.id, item, excluded=False)
    db.scalar.return_value = user_item

    resp = client.patch(f"/api/me/items/{user_item.id}", json={"excluded": True})
    assert resp.status_code == 200
    assert resp.json()["excluded"] is True
    assert user_item.excluded is True
    db.commit.assert_called_once()


def test_include_item_sets_excluded_false(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    item = _make_item()
    user_item = _make_user_item(user.id, item, excluded=True)
    db.scalar.return_value = user_item

    resp = client.patch(f"/api/me/items/{user_item.id}", json={"excluded": False})
    assert resp.status_code == 200
    assert resp.json()["excluded"] is False
    assert user_item.excluded is False
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Success — response shape
# ---------------------------------------------------------------------------


def test_response_contains_expected_fields(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    item = _make_item(name="Hades", service="steam", item_type="game")
    user_item = _make_user_item(user.id, item, excluded=False)
    db.scalar.return_value = user_item

    resp = client.patch(f"/api/me/items/{user_item.id}", json={"excluded": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(user_item.id)
    assert body["excluded"] is True
    assert body["item"]["id"] == str(item.id)
    assert body["item"]["name"] == "Hades"
    assert body["item"]["service"] == "steam"
    assert body["item"]["item_type"] == "game"


def test_idempotent_exclude_already_excluded(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """Excluding an already-excluded item is idempotent — returns 200, commits."""
    client, user, db = auth_client
    item = _make_item()
    user_item = _make_user_item(user.id, item, excluded=True)
    db.scalar.return_value = user_item

    resp = client.patch(f"/api/me/items/{user_item.id}", json={"excluded": True})
    assert resp.status_code == 200
    assert resp.json()["excluded"] is True


def test_idempotent_include_already_included(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    item = _make_item()
    user_item = _make_user_item(user.id, item, excluded=False)
    db.scalar.return_value = user_item

    resp = client.patch(f"/api/me/items/{user_item.id}", json={"excluded": False})
    assert resp.status_code == 200
    assert resp.json()["excluded"] is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_missing_excluded_field_returns_422(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    resp = client.patch(f"/api/me/items/{uuid.uuid4()}", json={})
    assert resp.status_code == 422


def test_non_boolean_excluded_returns_422(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    resp = client.patch(f"/api/me/items/{uuid.uuid4()}", json={"excluded": {"value": 1}})
    assert resp.status_code == 422


def test_invalid_uuid_in_path_returns_422(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    resp = client.patch("/api/me/items/not-a-uuid", json={"excluded": True})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Route sanity
# ---------------------------------------------------------------------------


def test_route_exists_and_is_patch(unauth_client: TestClient) -> None:
    """Sanity: route responds (not 404) — auth fires before body validation."""
    resp = unauth_client.patch(f"/api/me/items/{uuid.uuid4()}", json={"excluded": True})
    assert resp.status_code != 404
