"""Tests for GET /api/matches, GET /api/matches/{user_id}, POST /api/me/recompute."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import MatchCache, User


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


def _make_cache_row(
    user_a_id: uuid.UUID,
    user_b_id: uuid.UUID,
    score: float = 0.75,
) -> MatchCache:
    a, b = (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)
    row = MatchCache()
    row.user_a_id = a
    row.user_b_id = b
    row.score = score
    row.breakdown = {"steam": score}
    row.highlights = [{"service": "steam", "item_name": "Disco Elysium"}]
    row.computed_at = datetime.now(UTC)
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
def match_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[tuple[TestClient, User], None, None]:
    """Authenticated client with is_matchable=True."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    user = _make_user()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c, user
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def not_matchable_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Authenticated client with is_matchable=False."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    user = _make_user(is_matchable=False)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_get_matches_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/matches")
    assert resp.status_code == 401


def test_get_match_detail_requires_auth(client: TestClient) -> None:
    resp = client.get(f"/api/matches/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_recompute_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/me/recompute")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# is_matchable guard
# ---------------------------------------------------------------------------


def test_get_matches_returns_403_when_not_matchable(
    not_matchable_client: TestClient,
) -> None:
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=[]):
        resp = not_matchable_client.get("/api/matches")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_MATCHABLE"


def test_get_match_detail_returns_403_when_not_matchable(
    not_matchable_client: TestClient,
) -> None:
    resp = not_matchable_client.get(f"/api/matches/{uuid.uuid4()}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/matches — cache hit
# ---------------------------------------------------------------------------


def test_get_matches_returns_empty_list_when_no_matches(
    match_client: tuple[TestClient, User],
) -> None:
    client, _ = match_client
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=[]), \
         patch("syncup.api.routes.matches._refresh_match_cache"):
        resp = client.get("/api/matches")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "next_cursor": None}


def test_get_matches_returns_match_shape(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    other = _make_user(display_name="Sam", discord_handle="sam#1234")
    row = _make_cache_row(user.id, other.id, score=0.75)
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=[row]):
        resp = client.get("/api/matches")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    m = items[0]
    assert m["score"] == pytest.approx(0.75)
    assert m["user"]["display_name"] == "Sam"
    assert m["user"]["discord_handle"] == "sam#1234"
    assert "breakdown" in m
    assert "shared_highlights" in m
    assert "computed_at" in m


def test_get_matches_shared_highlights_in_response(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    other = _make_user()
    row = _make_cache_row(user.id, other.id)
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=[row]):
        resp = client.get("/api/matches")

    highlights = resp.json()["items"][0]["shared_highlights"]
    assert highlights == [{"service": "steam", "item_name": "Disco Elysium"}]


def test_get_matches_does_not_trigger_refresh_on_cache_hit(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    other = _make_user()
    row = _make_cache_row(user.id, other.id)
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=[row]), \
         patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh:
        client.get("/api/matches")

    mock_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/matches — cache miss triggers refresh
# ---------------------------------------------------------------------------


def test_get_matches_triggers_refresh_on_cache_miss(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    other = _make_user()
    row = _make_cache_row(user.id, other.id)
    mock_db.scalars.return_value.all.return_value = [other]

    # First call returns empty (cache miss), second returns results (after refresh).
    with patch(
        "syncup.api.routes.matches._load_cached_matches",
        side_effect=[[], [row]],
    ), patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh:
        resp = client.get("/api/matches")

    mock_refresh.assert_called_once()
    assert len(resp.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_get_matches_respects_limit(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    others = [_make_user(display_name=f"User {i}") for i in range(5)]
    rows = [_make_cache_row(user.id, o.id, score=0.9 - i * 0.1) for i, o in enumerate(others)]
    mock_db.scalars.return_value.all.return_value = others[:2]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=rows):
        resp = client.get("/api/matches?limit=2")

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2
    assert resp.json()["next_cursor"] is not None


def test_get_matches_cursor_advances_page(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    others = [_make_user(display_name=f"User {i}") for i in range(4)]
    rows = [_make_cache_row(user.id, o.id, score=0.9 - i * 0.1) for i, o in enumerate(others)]
    mock_db.scalars.return_value.all.return_value = others[2:]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=rows):
        # Get first page to obtain cursor.
        with patch("syncup.api.routes.matches._load_cached_matches", return_value=rows):
            first_resp = client.get("/api/matches?limit=2")
        cursor = first_resp.json()["next_cursor"]
        assert cursor is not None

        resp = client.get(f"/api/matches?limit=2&cursor={cursor}")

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_get_matches_no_next_cursor_on_last_page(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    other = _make_user()
    row = _make_cache_row(user.id, other.id)
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=[row]):
        resp = client.get("/api/matches?limit=20")

    assert resp.json()["next_cursor"] is None


# ---------------------------------------------------------------------------
# GET /api/matches/{user_id}
# ---------------------------------------------------------------------------


def test_get_match_detail_returns_match(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    other = _make_user(display_name="Sam")
    row = _make_cache_row(user.id, other.id, score=0.88)
    mock_db.get.side_effect = lambda model, pk: row if model is MatchCache else other

    resp = client.get(f"/api/matches/{other.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == pytest.approx(0.88)
    assert data["user"]["display_name"] == "Sam"
    assert "shared_highlights" in data


def test_get_match_detail_404_when_not_cached(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, user = match_client
    mock_db.get.return_value = None

    resp = client.get(f"/api/matches/{uuid.uuid4()}")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/me/recompute
# ---------------------------------------------------------------------------


def test_recompute_invalidates_cache_and_returns_204(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, _ = match_client
    with patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh:
        resp = client.post("/api/me/recompute")
    assert resp.status_code == 204
    mock_refresh.assert_called_once()
