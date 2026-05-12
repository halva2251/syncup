"""Tests for GET/PATCH /api/me/dimensions."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import User, UserDimensionWeight

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


def _make_weight(
    service: str, weight: float, user_id: uuid.UUID | None = None
) -> UserDimensionWeight:
    row = UserDimensionWeight()
    row.user_id = user_id or uuid.uuid4()
    row.service = service
    row.weight = weight
    return row


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
def dim_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Authenticated client."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    mock_db.scalars.return_value.all.return_value = []

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


def test_get_dimensions_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/me/dimensions")
    assert resp.status_code == 401


def test_patch_dimensions_requires_auth(client: TestClient) -> None:
    resp = client.patch("/api/me/dimensions", json={"weights": {"steam": 1.0}})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/me/dimensions
# ---------------------------------------------------------------------------


def test_get_dimensions_returns_empty_when_none_set(dim_client: TestClient) -> None:
    resp = dim_client.get("/api/me/dimensions")
    assert resp.status_code == 200
    assert resp.json() == {"weights": {}}


def test_get_dimensions_returns_stored_weights(
    dim_client: TestClient, mock_db: MagicMock
) -> None:
    rows = [
        _make_weight("steam", 0.3),
        _make_weight("lastfm", 0.5),
        _make_weight("spotify", 0.2),
    ]
    mock_db.scalars.return_value.all.return_value = rows

    resp = dim_client.get("/api/me/dimensions")
    assert resp.status_code == 200
    weights = resp.json()["weights"]
    assert weights["steam"] == pytest.approx(0.3)
    assert weights["lastfm"] == pytest.approx(0.5)
    assert weights["spotify"] == pytest.approx(0.2)


def test_get_dimensions_returns_single_service(
    dim_client: TestClient, mock_db: MagicMock
) -> None:
    mock_db.scalars.return_value.all.return_value = [_make_weight("steam", 1.0)]

    resp = dim_client.get("/api/me/dimensions")
    assert resp.json() == {"weights": {"steam": pytest.approx(1.0)}}


# ---------------------------------------------------------------------------
# PATCH /api/me/dimensions
# ---------------------------------------------------------------------------


def test_patch_dimensions_normalises_weights(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 7.0, "spotify": 3.0}},
    )
    assert resp.status_code == 200
    weights = resp.json()["weights"]
    assert weights["steam"] == pytest.approx(0.7)
    assert weights["spotify"] == pytest.approx(0.3)


def test_patch_dimensions_already_normalised_unchanged(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 0.6, "lastfm": 0.4}},
    )
    assert resp.status_code == 200
    weights = resp.json()["weights"]
    assert weights["steam"] == pytest.approx(0.6)
    assert weights["lastfm"] == pytest.approx(0.4)


def test_patch_dimensions_single_service_gets_weight_one(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"lastfm": 5.0}},
    )
    assert resp.status_code == 200
    assert resp.json()["weights"]["lastfm"] == pytest.approx(1.0)


def test_patch_dimensions_zero_weight_allowed_alongside_positive(
    dim_client: TestClient,
) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 1.0, "spotify": 0.0}},
    )
    assert resp.status_code == 200
    weights = resp.json()["weights"]
    assert weights["steam"] == pytest.approx(1.0)
    assert weights["spotify"] == pytest.approx(0.0)


def test_patch_dimensions_deletes_and_replaces_existing(
    dim_client: TestClient, mock_db: MagicMock
) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 1.0}},
    )
    assert resp.status_code == 200
    mock_db.execute.assert_called_once()


def test_patch_dimensions_invalid_service_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"tiktok": 1.0}},
    )
    assert resp.status_code == 422


def test_patch_dimensions_mixed_valid_invalid_service_returns_422(
    dim_client: TestClient,
) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 0.5, "tiktok": 0.5}},
    )
    assert resp.status_code == 422


def test_patch_dimensions_negative_weight_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": -1.0}},
    )
    assert resp.status_code == 422


def test_patch_dimensions_all_zero_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 0.0, "spotify": 0.0}},
    )
    assert resp.status_code == 422


def test_patch_dimensions_empty_weights_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch("/api/me/dimensions", json={"weights": {}})
    assert resp.status_code == 422


def test_patch_dimensions_missing_weights_key_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch("/api/me/dimensions", json={"steam": 1.0})
    assert resp.status_code == 422


def test_patch_dimensions_weights_not_a_dict_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch("/api/me/dimensions", json={"weights": "heavy"})
    assert resp.status_code == 422


def test_patch_dimensions_weights_null_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch("/api/me/dimensions", json={"weights": None})
    assert resp.status_code == 422


def test_patch_dimensions_non_numeric_weight_returns_422(dim_client: TestClient) -> None:
    resp = dim_client.patch(
        "/api/me/dimensions", json={"weights": {"steam": "heavy"}}
    )
    assert resp.status_code == 422


def test_patch_dimensions_commit_failure_returns_500(
    dim_client: TestClient, mock_db: MagicMock
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    mock_db.commit.side_effect = SQLAlchemyError("connection lost")

    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 1.0}},
    )
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"
    mock_db.rollback.assert_called_once()


def test_patch_dimensions_execute_failure_triggers_rollback(
    dim_client: TestClient, mock_db: MagicMock
) -> None:
    """D4: SQLAlchemyError on DELETE must roll back and return 500."""
    from sqlalchemy.exc import SQLAlchemyError

    mock_db.execute.side_effect = SQLAlchemyError("lock timeout")

    resp = dim_client.patch(
        "/api/me/dimensions",
        json={"weights": {"steam": 1.0}},
    )
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"
    mock_db.rollback.assert_called_once()
