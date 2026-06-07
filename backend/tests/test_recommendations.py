"""Tests for GET /api/me/recommendations — Block I.

Covers:
- 401 when unauthenticated
- 422 NO_EMBEDDING_AVAILABLE when user has no combined embedding
- Happy path: returns list with correct schema (item_name, service, item_type, similarity_score)
- Default limit is 10; custom limit respected; limit > 50 rejected
- item_type filter passed through to query
- Items with distance >= 1.0 (score <= 0) are excluded from results
- similarity_score clamped to [0, 1]
- Empty result when no candidates found
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import User
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
        "is_matchable": True,
        "onboarded": True,
        "languages": None,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


def _make_rec_row(
    name: str = "Disco Elysium",
    service: str = "steam",
    item_type: str = "game",
    distance: float = 0.25,
) -> Any:
    """Build a mock row as returned by the ANN SQL query."""
    row = MagicMock()
    row.name = name
    row.service = service
    row.item_type = item_type
    row.distance = distance
    return row


def _make_owned_row(name: str, item_type: str = "game") -> Any:
    """Build a mock row for the 'items the user already owns' query (name, item_type)."""
    row = MagicMock()
    row.name = name
    row.item_type = item_type
    return row


def _setup_db_for_recs(
    mock_db: MagicMock,
    embedding: list[float] | None,
    ann_rows: list[Any],
    owned_rows: list[Any] | None = None,
) -> None:
    """Wire mock_db so the three db.execute calls return the right values.

    Query order in the endpoint: (1) user's combined embedding, (2) the user's
    owned (name, item_type) rows for title-based dedup, (3) the ANN candidates.
    """
    emb_result = MagicMock()
    emb_result.scalar_one_or_none.return_value = embedding

    owned_result = MagicMock()
    owned_result.all.return_value = owned_rows or []

    ann_result = MagicMock()
    ann_result.all.return_value = ann_rows

    mock_db.execute.side_effect = [emb_result, owned_result, ann_result]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def rec_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[tuple[TestClient, User], None, None]:
    """Authenticated client wired to mock_db."""
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
            yield c, user
    _rate_limiter.enabled = True
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def unauth_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    from syncup.api.app import app

    _rate_limiter.enabled = False
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    _rate_limiter.enabled = True


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_requires_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/me/recommendations")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 422 NO_EMBEDDING_AVAILABLE
# ---------------------------------------------------------------------------


def test_no_embedding_returns_422(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """422 when the user has no combined embedding yet."""
    client, _ = rec_client
    _setup_db_for_recs(mock_db, embedding=None, ann_rows=[])

    resp = client.get("/api/me/recommendations")

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "NO_EMBEDDING_AVAILABLE"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_returns_list(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Returns a list of recommendations when embedding and candidates exist."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row()],
    )

    resp = client.get("/api/me/recommendations")

    assert resp.status_code == 200
    assert "items" in resp.json()
    assert len(resp.json()["items"]) == 1


def test_response_contains_correct_fields(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Each recommendation item has item_name, service, item_type, similarity_score."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[
            _make_rec_row(name="Bloodborne", service="steam", item_type="game", distance=0.3)
        ],
    )

    resp = client.get("/api/me/recommendations")

    item = resp.json()["items"][0]
    assert item["item_name"] == "Bloodborne"
    assert item["service"] == "steam"
    assert item["item_type"] == "game"
    assert "similarity_score" in item
    assert abs(item["similarity_score"] - 0.7) < 1e-4


def test_similarity_score_is_one_minus_distance(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """similarity_score = 1 - distance."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(distance=0.1)],
    )

    resp = client.get("/api/me/recommendations")
    score = resp.json()["items"][0]["similarity_score"]
    assert abs(score - 0.9) < 1e-4


def test_similarity_score_clamped_to_one(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """similarity_score is clamped to 1.0 (distance never goes below 0)."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(distance=0.0)],
    )

    resp = client.get("/api/me/recommendations")
    assert resp.json()["items"][0]["similarity_score"] == 1.0


# ---------------------------------------------------------------------------
# Cross-service dedup + owned-by-title exclusion (QA fixes)
# ---------------------------------------------------------------------------


def test_excludes_title_already_owned_on_another_service(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """A title the user owns (on any service) must not be recommended from another.

    User owns 'Disco Elysium' on steam; the ANN candidate is the same title under a
    different service — it must be filtered out by normalized-title match.
    """
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(name="Disco Elysium", service="vibe_test", distance=0.2)],
        owned_rows=[_make_owned_row(name="Disco Elysium", item_type="game")],
    )

    resp = client.get("/api/me/recommendations")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_owned_title_match_is_normalized(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Owned-title exclusion uses normalize_title (case/punctuation-insensitive)."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(name="DISCO ELYSIUM!", service="x", distance=0.2)],
        owned_rows=[_make_owned_row(name="Disco Elysium", item_type="game")],
    )

    resp = client.get("/api/me/recommendations")
    assert resp.json()["items"] == []


def test_dedupes_same_title_across_services(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """The same title appearing under multiple services collapses to one rec (best score)."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[
            _make_rec_row(name="Hades", service="steam", distance=0.20),  # better
            _make_rec_row(name="Hades", service="vibe_test", distance=0.35),
        ],
    )

    resp = client.get("/api/me/recommendations")
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["item_name"] == "Hades"
    assert items[0]["service"] == "steam"  # the higher-similarity (lower-distance) copy


def test_different_titles_same_franchise_are_kept(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Distinct titles (e.g. a franchise) are NOT collapsed — only exact title dupes are."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[
            _make_rec_row(name="Avatar", service="letterboxd", item_type="film", distance=0.2),
            _make_rec_row(
                name="Avatar: The Way of Water",
                service="letterboxd",
                item_type="film",
                distance=0.25,
            ),
        ],
    )

    resp = client.get("/api/me/recommendations")
    assert len(resp.json()["items"]) == 2


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_filters_zero_and_negative_score(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Items with distance >= 1.0 (score <= 0) are excluded from results."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[
            _make_rec_row(name="Good Game", distance=0.2),
            _make_rec_row(name="Anti-Correlated", distance=1.0),  # score == 0 → excluded
            _make_rec_row(name="Far Away", distance=1.5),  # score < 0 → excluded
        ],
    )

    resp = client.get("/api/me/recommendations")
    names = [i["item_name"] for i in resp.json()["items"]]
    assert "Good Game" in names
    assert "Anti-Correlated" not in names
    assert "Far Away" not in names


def test_item_type_filter_accepted(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """item_type query param is validated and forwarded to the SQL params."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(item_type="game")],
    )

    resp = client.get("/api/me/recommendations?item_type=game")

    assert resp.status_code == 200
    assert resp.json()["items"][0]["item_type"] == "game"
    # Verify 'game' was passed as a bind param to the ANN query (3rd db.execute call:
    # embedding, owned-titles, then ANN).
    ann_call = mock_db.execute.call_args_list[2]
    passed_params = ann_call[0][1]
    assert passed_params["item_type"] == "game"


def test_unknown_item_type_rejected(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """An item_type value not in the allowlist returns 422."""
    client, _ = rec_client

    resp = client.get("/api/me/recommendations?item_type=invalid_type")

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------


def test_default_limit_is_10(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Default limit is 10 — verified by what the SQL query receives."""
    client, _ = rec_client
    # Return 10 rows to simulate limit=10 behaviour
    rows = [_make_rec_row(name=f"Item {i}", distance=0.1 * (i + 1) / 10) for i in range(10)]
    _setup_db_for_recs(mock_db, embedding=[0.1] * 384, ann_rows=rows)

    resp = client.get("/api/me/recommendations")

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 10


def test_custom_limit_accepted(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Custom limit query param is accepted."""
    client, _ = rec_client
    rows = [_make_rec_row(name=f"Item {i}", distance=0.05 * (i + 1)) for i in range(5)]
    _setup_db_for_recs(mock_db, embedding=[0.1] * 384, ann_rows=rows)

    resp = client.get("/api/me/recommendations?limit=5")

    assert resp.status_code == 200


def test_limit_above_50_rejected(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """limit > 50 is rejected with 422."""
    client, _ = rec_client

    resp = client.get("/api/me/recommendations?limit=51")

    assert resp.status_code == 422


def test_limit_zero_rejected(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """limit < 1 is rejected with 422."""
    client, _ = rec_client

    resp = client.get("/api/me/recommendations?limit=0")

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


def test_empty_recommendations_when_no_candidates(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Returns empty list (not 404) when no items are found."""
    client, _ = rec_client
    _setup_db_for_recs(mock_db, embedding=[0.1] * 384, ann_rows=[])

    resp = client.get("/api/me/recommendations")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_all_candidates_filtered_zero_score(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Returns empty list when all candidates have score <= 0."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(distance=1.1), _make_rec_row(distance=2.0)],
    )

    resp = client.get("/api/me/recommendations")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# M5: additional coverage gaps
# ---------------------------------------------------------------------------


def test_default_limit_passed_as_sql_param(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """Default limit=10 is forwarded as db_limit bind param to the SQL query."""
    client, _ = rec_client
    _setup_db_for_recs(mock_db, embedding=[0.1] * 384, ann_rows=[])

    client.get("/api/me/recommendations")

    ann_call = mock_db.execute.call_args_list[2]
    params = ann_call[0][1]
    # db_limit is limit * 5 (oversample for score/owned/dedup post-filters),
    # default limit=10 → db_limit=50
    assert params["db_limit"] == 50


def test_similarity_score_clamped_to_zero_for_large_distance(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """distance=2.0 → score is clamped to 0.0 and the item is excluded."""
    client, _ = rec_client
    _setup_db_for_recs(
        mock_db,
        embedding=[0.1] * 384,
        ann_rows=[_make_rec_row(name="Anti-Vibes", distance=2.0)],
    )

    resp = client.get("/api/me/recommendations")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_no_item_type_param_excludes_it_from_sql_params(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """When item_type is omitted, 'item_type' key is NOT in the SQL bind params."""
    client, _ = rec_client
    _setup_db_for_recs(mock_db, embedding=[0.1] * 384, ann_rows=[])

    client.get("/api/me/recommendations")

    ann_call = mock_db.execute.call_args_list[2]
    params = ann_call[0][1]
    assert "item_type" not in params


def test_under_delivery_due_to_post_filter(
    rec_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """If half the oversampled rows are filtered out, only good rows are returned."""
    client, _ = rec_client
    rows = [_make_rec_row(name=f"Good {i}", distance=0.1 * (i + 1)) for i in range(5)] + [
        _make_rec_row(name=f"Bad {i}", distance=1.5) for i in range(5)
    ]
    _setup_db_for_recs(mock_db, embedding=[0.1] * 384, ann_rows=rows)

    resp = client.get("/api/me/recommendations?limit=10")

    assert resp.status_code == 200
    names = [i["item_name"] for i in resp.json()["items"]]
    assert len(names) == 5
    assert all(n.startswith("Good") for n in names)
