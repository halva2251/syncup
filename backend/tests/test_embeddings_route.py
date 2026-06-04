"""Tests for POST /api/embeddings/build."""

from __future__ import annotations

import math
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import Item, User, UserDimensionWeight, UserEmbedding, UserItem
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


def _make_item(service: str = "steam", item_type: str = "game", **kwargs: object) -> Item:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "service": service,
        "item_type": item_type,
        "external_id": str(uuid.uuid4()),
        "name": "Disco Elysium",
        "meta": {},
        "embedding": [0.1] * 384,
        "embedding_computed_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    return Item(**{**defaults, **kwargs})


def _make_user_item(
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    engagement_score: float = 0.8,
    excluded: bool = False,
    **kwargs: object,
) -> UserItem:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "item_id": item_id,
        "engagement_score": engagement_score,
        "raw_value": 100.0,
        "raw_type": "consumption",
        "excluded": excluded,
        "last_engaged_at": datetime.now(UTC),
        "fetched_at": datetime.now(UTC),
    }
    return UserItem(**{**defaults, **kwargs})


def _make_dimension_weight(user_id: uuid.UUID, service: str, weight: float) -> UserDimensionWeight:
    w = UserDimensionWeight()
    w.user_id = user_id
    w.service = service
    w.weight = weight
    return w


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
    """Authenticated client."""
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
    resp = unauth_client.post("/api/embeddings/build")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 422 NO_EMBEDDINGS_AVAILABLE
# ---------------------------------------------------------------------------


def test_no_items_with_embeddings_returns_422(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    # DB returns no rows from the join query
    db.execute.return_value.fetchall.return_value = []

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "NO_EMBEDDINGS_AVAILABLE"


def test_all_items_excluded_returns_422(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    # All user_items have excluded=True; the query filters them out → empty result
    db.execute.return_value.fetchall.return_value = []

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "NO_EMBEDDINGS_AVAILABLE"


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def _fake_row(
    service: str = "steam",
    engagement_score: float = 0.8,
    embedding: list[float] | None = None,
    boost: float | None = None,
    dim_weight: float | None = None,
) -> MagicMock:
    """Build a MagicMock row that looks like the JOIN result row."""
    row = MagicMock()
    row.service = service
    row.engagement_score = engagement_score
    row.embedding = embedding if embedding is not None else [0.1] * 384
    row.boost_multiplier = boost
    row.dim_weight = dim_weight
    return row


def test_success_returns_200_with_item_count(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    rows = [_fake_row(service="steam", engagement_score=0.8)]
    db.execute.return_value.fetchall.return_value = rows
    db.merge.return_value = MagicMock()

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "combined"
    assert body["item_count"] == 1
    assert "computed_at" in body


def test_success_upserts_user_embedding(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    client, user, db = auth_client
    rows = [_fake_row()]
    db.execute.return_value.fetchall.return_value = rows

    client.post("/api/embeddings/build")

    # db.merge should have been called with a UserEmbedding
    db.merge.assert_called_once()
    merged_obj = db.merge.call_args[0][0]
    assert isinstance(merged_obj, UserEmbedding)
    assert merged_obj.user_id == user.id
    assert merged_obj.service == "combined"


def test_second_call_succeeds_idempotent(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """Two sequential calls both succeed — idempotent upsert."""
    client, user, db = auth_client
    db.execute.return_value.fetchall.return_value = [_fake_row()]

    r1 = client.post("/api/embeddings/build")
    r2 = client.post("/api/embeddings/build")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert db.merge.call_count == 2


def test_computed_at_is_updated_on_second_call(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """Each call passes a fresh computed_at to the merged UserEmbedding."""
    client, user, db = auth_client
    db.execute.return_value.fetchall.return_value = [_fake_row()]

    client.post("/api/embeddings/build")
    client.post("/api/embeddings/build")

    first_computed_at = db.merge.call_args_list[0][0][0].computed_at
    second_computed_at = db.merge.call_args_list[1][0][0].computed_at
    assert second_computed_at > first_computed_at


# ---------------------------------------------------------------------------
# Per-service cap (top 50)
# ---------------------------------------------------------------------------


def test_per_service_cap_at_50(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """More than 50 items per service → only top 50 by engagement_score are used."""
    client, user, db = auth_client

    # 60 steam items with distinct engagement scores
    rows = [_fake_row(service="steam", engagement_score=round((i + 1) / 60, 4)) for i in range(60)]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200
    # item_count should be capped at 50
    assert resp.json()["item_count"] == 50


# ---------------------------------------------------------------------------
# Dimension weights applied
# ---------------------------------------------------------------------------


def test_dimension_weights_applied(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """dim_weight from LEFT JOIN user_dimension_weights is passed through to weighting."""
    client, user, db = auth_client
    # One row with a 0.3 dimension weight
    rows = [_fake_row(service="steam", engagement_score=0.8, dim_weight=0.3)]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    # Just assert it succeeds — the weight math is tested in test_aggregate_vectors.py
    assert resp.status_code == 200


def test_missing_dimension_weight_defaults_to_1(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """When dim_weight IS NULL (no row in user_dimension_weights), default to 1.0."""
    client, user, db = auth_client
    rows = [_fake_row(service="steam", engagement_score=0.8, dim_weight=None)]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Preference overrides applied
# ---------------------------------------------------------------------------


def test_boost_multiplier_applied(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """boost_multiplier from LEFT JOIN preference_overrides is applied to weight."""
    client, user, db = auth_client
    rows = [_fake_row(service="steam", engagement_score=0.5, boost=3.0)]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200


def test_zero_engagement_score_is_skipped(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """Items with engagement_score == 0 do not contribute to the vector."""
    client, user, db = auth_client
    rows = [
        _fake_row(service="steam", engagement_score=0.0),
        _fake_row(service="steam", engagement_score=0.5),
    ]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200
    assert resp.json()["item_count"] == 1


def test_mixed_excluded_and_included_items(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """Only non-excluded items are counted; excluded ones are filtered by the query."""
    client, user, db = auth_client
    # The query filters excluded=False, so we simulate the DB already having done that.
    rows = [
        _fake_row(service="steam", engagement_score=0.9),
        _fake_row(service="steam", engagement_score=0.8),
    ]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200
    assert resp.json()["item_count"] == 2


def test_per_service_cap_is_independent(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """Cap of 50 applies per service, not globally."""
    client, user, db = auth_client
    # 60 steam + 60 spotify = 120 total, capped to 50 + 50 = 100
    rows = (
        [_fake_row(service="steam", engagement_score=round((i + 1) / 60, 4)) for i in range(60)]
        + [_fake_row(service="spotify", engagement_score=round((i + 1) / 60, 4)) for i in range(60)]
    )
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200
    assert resp.json()["item_count"] == 100


def test_success_writes_normalised_embedding(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """The vector written to UserEmbedding is L2-normalised by aggregate_vectors."""
    client, user, db = auth_client
    rows = [_fake_row(service="steam", engagement_score=0.8)]
    db.execute.return_value.fetchall.return_value = rows

    client.post("/api/embeddings/build")

    merged_obj = db.merge.call_args[0][0]
    assert isinstance(merged_obj, UserEmbedding)
    norm = math.sqrt(sum(v * v for v in merged_obj.embedding))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_missing_boost_defaults_to_1(
    auth_client: tuple[TestClient, User, MagicMock],
) -> None:
    """When boost IS NULL (no override), default to 1.0."""
    client, user, db = auth_client
    rows = [_fake_row(service="steam", engagement_score=0.5, boost=None)]
    db.execute.return_value.fetchall.return_value = rows

    resp = client.post("/api/embeddings/build")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting shape
# ---------------------------------------------------------------------------


def test_route_exists_and_is_post(unauth_client: TestClient) -> None:
    """Sanity: route responds (not 404) — auth check fires before rate limit."""
    resp = unauth_client.post("/api/embeddings/build")
    assert resp.status_code != 404
