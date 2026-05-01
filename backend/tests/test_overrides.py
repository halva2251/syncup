"""Tests for GET/POST/PATCH/DELETE /api/me/overrides."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import Item, PreferenceOverride, User

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


def _make_item(**kwargs: object) -> Item:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "service": "steam",
        "item_type": "game",
        "external_id": "570",
        "name": "Dota 2",
        "meta": {},
        "embedding": None,
        "embedding_computed_at": None,
        "created_at": datetime.now(UTC),
    }
    return Item(**{**defaults, **kwargs})


def _make_override(**kwargs: object) -> PreferenceOverride:
    item = kwargs.pop("item", _make_item())  # type: ignore[arg-type]
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "item_id": item.id,
        "boost_multiplier": 2.0,
        "note": None,
        "created_at": datetime.now(UTC),
    }
    obj = PreferenceOverride(**{**defaults, **kwargs})
    obj.item = item  # satisfy relationship used by OverrideOut
    return obj


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
def ov_client(
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
    mock_db.get.return_value = None

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


def test_list_overrides_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/me/overrides")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_override_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/me/overrides",
        json={"item_id": str(uuid.uuid4()), "boost_multiplier": 2.0},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/me/overrides
# ---------------------------------------------------------------------------


def test_list_overrides_returns_empty(ov_client: TestClient) -> None:
    resp = ov_client.get("/api/me/overrides")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_overrides_returns_items(ov_client: TestClient, mock_db: MagicMock) -> None:
    item = _make_item(name="Disco Elysium")
    ov = _make_override(item=item, boost_multiplier=2.5, note="love this game")
    mock_db.scalars.return_value.all.return_value = [ov]

    resp = ov_client.get("/api/me/overrides")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["item"]["name"] == "Disco Elysium"
    assert items[0]["boost_multiplier"] == pytest.approx(2.5)
    assert items[0]["note"] == "love this game"
    assert "id" in items[0]
    assert "created_at" in items[0]


def test_list_overrides_ordered_newest_first(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    older = _make_override(created_at=datetime(2025, 1, 1, tzinfo=UTC))
    newer = _make_override(
        created_at=datetime(2025, 1, 2, tzinfo=UTC),
        boost_multiplier=3.0,
    )
    mock_db.scalars.return_value.all.return_value = [newer, older]

    resp = ov_client.get("/api/me/overrides")
    items = resp.json()
    assert items[0]["boost_multiplier"] == pytest.approx(3.0)


def test_list_overrides_null_note(ov_client: TestClient, mock_db: MagicMock) -> None:
    ov = _make_override(note=None)
    mock_db.scalars.return_value.all.return_value = [ov]

    resp = ov_client.get("/api/me/overrides")
    assert resp.json()[0]["note"] is None


# ---------------------------------------------------------------------------
# POST /api/me/overrides
# ---------------------------------------------------------------------------


def test_create_override_returns_201(ov_client: TestClient, mock_db: MagicMock) -> None:
    item = _make_item(name="Disco Elysium")
    mock_db.get.return_value = item
    mock_db.scalar.return_value = None  # no existing override

    resp = ov_client.post(
        "/api/me/overrides",
        json={"item_id": str(item.id), "boost_multiplier": 2.0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["item"]["name"] == "Disco Elysium"
    assert body["boost_multiplier"] == pytest.approx(2.0)
    assert body["note"] is None
    assert "id" in body
    assert "created_at" in body


def test_create_override_with_note(ov_client: TestClient, mock_db: MagicMock) -> None:
    item = _make_item()
    mock_db.get.return_value = item
    mock_db.scalar.return_value = None

    resp = ov_client.post(
        "/api/me/overrides",
        json={
            "item_id": str(item.id),
            "boost_multiplier": 1.5,
            "note": "love this despite low hours",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["note"] == "love this despite low hours"


def test_create_override_item_not_found_returns_404(ov_client: TestClient) -> None:
    resp = ov_client.post(
        "/api/me/overrides",
        json={"item_id": str(uuid.uuid4()), "boost_multiplier": 2.0},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_create_override_duplicate_item_returns_409(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    item = _make_item()
    existing = _make_override(item=item)
    mock_db.get.return_value = item
    mock_db.scalar.return_value = existing  # already exists

    resp = ov_client.post(
        "/api/me/overrides",
        json={"item_id": str(item.id), "boost_multiplier": 2.0},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_create_override_zero_boost_returns_422(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    item = _make_item()
    mock_db.get.return_value = item

    resp = ov_client.post(
        "/api/me/overrides",
        json={"item_id": str(item.id), "boost_multiplier": 0},
    )
    assert resp.status_code == 422


def test_create_override_negative_boost_returns_422(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    item = _make_item()
    mock_db.get.return_value = item

    resp = ov_client.post(
        "/api/me/overrides",
        json={"item_id": str(item.id), "boost_multiplier": -1.0},
    )
    assert resp.status_code == 422


def test_create_override_missing_item_id_returns_422(ov_client: TestClient) -> None:
    resp = ov_client.post("/api/me/overrides", json={"boost_multiplier": 2.0})
    assert resp.status_code == 422


def test_create_override_missing_boost_returns_422(ov_client: TestClient) -> None:
    resp = ov_client.post(
        "/api/me/overrides", json={"item_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 422


def test_create_override_note_over_max_length_returns_422(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    item = _make_item()
    mock_db.get.return_value = item

    resp = ov_client.post(
        "/api/me/overrides",
        json={"item_id": str(item.id), "boost_multiplier": 2.0, "note": "x" * 501},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/me/overrides/{id}
# ---------------------------------------------------------------------------


def test_patch_override_boost_multiplier(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    ov = _make_override(boost_multiplier=2.0, note="original note")
    mock_db.scalar.return_value = ov

    resp = ov_client.patch(
        f"/api/me/overrides/{ov.id}", json={"boost_multiplier": 3.5}
    )
    assert resp.status_code == 200
    assert resp.json()["boost_multiplier"] == pytest.approx(3.5)
    assert resp.json()["note"] == "original note"


def test_patch_override_note(ov_client: TestClient, mock_db: MagicMock) -> None:
    ov = _make_override(note=None)
    mock_db.scalar.return_value = ov

    resp = ov_client.patch(
        f"/api/me/overrides/{ov.id}", json={"note": "updated note"}
    )
    assert resp.status_code == 200
    assert resp.json()["note"] == "updated note"


def test_patch_override_clear_note(ov_client: TestClient, mock_db: MagicMock) -> None:
    ov = _make_override(note="old note")
    mock_db.scalar.return_value = ov

    resp = ov_client.patch(f"/api/me/overrides/{ov.id}", json={"note": None})
    assert resp.status_code == 200
    assert resp.json()["note"] is None


def test_patch_override_not_found_returns_404(ov_client: TestClient) -> None:
    resp = ov_client.patch(
        f"/api/me/overrides/{uuid.uuid4()}", json={"boost_multiplier": 2.0}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_patch_override_zero_boost_returns_422(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    ov = _make_override()
    mock_db.scalar.return_value = ov

    resp = ov_client.patch(f"/api/me/overrides/{ov.id}", json={"boost_multiplier": 0})
    assert resp.status_code == 422


def test_patch_override_wrong_user_returns_404(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    mock_db.scalar.return_value = None

    resp = ov_client.patch(
        f"/api/me/overrides/{uuid.uuid4()}", json={"boost_multiplier": 2.0}
    )
    assert resp.status_code == 404


def test_patch_override_note_over_max_length_returns_422(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    ov = _make_override()
    mock_db.scalar.return_value = ov

    resp = ov_client.patch(f"/api/me/overrides/{ov.id}", json={"note": "x" * 501})
    assert resp.status_code == 422


def test_patch_override_malformed_uuid_returns_422(ov_client: TestClient) -> None:
    resp = ov_client.patch("/api/me/overrides/not-a-uuid", json={"boost_multiplier": 2.0})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/me/overrides/{id}
# ---------------------------------------------------------------------------


def test_delete_override_returns_204(ov_client: TestClient, mock_db: MagicMock) -> None:
    ov = _make_override()
    mock_db.scalar.return_value = ov

    resp = ov_client.delete(f"/api/me/overrides/{ov.id}")
    assert resp.status_code == 204
    assert resp.content == b""
    mock_db.delete.assert_called_once_with(ov)
    mock_db.commit.assert_called()


def test_delete_override_not_found_returns_404(ov_client: TestClient) -> None:
    resp = ov_client.delete(f"/api/me/overrides/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_delete_override_wrong_user_returns_404(
    ov_client: TestClient, mock_db: MagicMock
) -> None:
    mock_db.scalar.return_value = None

    resp = ov_client.delete(f"/api/me/overrides/{uuid.uuid4()}")
    assert resp.status_code == 404
