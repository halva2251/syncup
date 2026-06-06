"""Tests for GET /api/matches, GET /api/matches/{user_id}, POST /api/me/recompute."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
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
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)), \
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

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)):
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

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)):
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

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)), \
         patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh:
        client.get("/api/matches")

    mock_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/matches — cache miss triggers refresh
# ---------------------------------------------------------------------------


def test_get_matches_triggers_refresh_on_cache_miss(
    match_client: tuple[TestClient, User],
) -> None:
    client, _ = match_client
    # Any empty page (offset=0 or mid-session expiry) triggers a background refresh.
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)), \
         patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh:
        resp = client.get("/api/matches")

    mock_refresh.assert_called_once()
    assert resp.json() == {"items": [], "next_cursor": None}


def test_get_matches_triggers_refresh_on_deep_page_cache_expiry(
    match_client: tuple[TestClient, User],
) -> None:
    """Empty page at offset>0 (cache expired mid-session) also schedules a refresh."""
    import base64

    client, _ = match_client
    deep_cursor = base64.b64encode(b"40").decode()
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)), \
         patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh:
        resp = client.get(f"/api/matches?cursor={deep_cursor}")

    mock_refresh.assert_called_once()
    assert resp.json() == {"items": [], "next_cursor": None}


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

    # has_more=True means there are rows beyond what was returned
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=(rows[:2], True)):
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

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=(rows[:2], True)):
        mock_db.scalars.return_value.all.return_value = others[:2]
        first_resp = client.get("/api/matches?limit=2")
        cursor = first_resp.json()["next_cursor"]
        assert cursor is not None

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=(rows[2:], False)):
        mock_db.scalars.return_value.all.return_value = others[2:]
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

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)):
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


def _noop_limiter(*args: Any, **kwargs: Any) -> Any:
    return lambda f: f


def test_recompute_schedules_vibe_when_key_present(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, _ = match_client
    from syncup.api.app import app
    from syncup.limiter import limiter

    limiter._storage.reset()

    fake_settings = MagicMock()
    fake_settings.llm_api_key = "sk-real"
    fake_settings.llm_base_url = "https://api.deepseek.com"
    fake_settings.llm_model = "deepseek-chat"

    with patch.object(app.state, "settings", fake_settings):
        with (
            patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh,
            patch("syncup.api.routes.matches.synthesize_vibe") as mock_vibe,
        ):
            resp = client.post("/api/me/recompute")

    assert resp.status_code == 204
    mock_refresh.assert_called_once()
    mock_vibe.assert_called_once()


def test_recompute_skips_vibe_when_no_key(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    client, _ = match_client
    from syncup.api.app import app
    from syncup.limiter import limiter

    limiter._storage.reset()

    fake_settings = MagicMock()
    fake_settings.llm_api_key = None

    with patch.object(app.state, "settings", fake_settings):
        with (
            patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh,
            patch("syncup.api.routes.matches.synthesize_vibe") as mock_vibe,
        ):
            resp = client.post("/api/me/recompute")

    assert resp.status_code == 204
    mock_refresh.assert_called_once()
    mock_vibe.assert_not_called()


# ---------------------------------------------------------------------------
# Cache expiry
# ---------------------------------------------------------------------------


def test_load_cached_matches_queries_db_with_cutoff() -> None:
    """D2: _load_cached_matches returns (rows, has_more) tuple."""
    from syncup.api.routes.matches import _load_cached_matches

    user_id = uuid.uuid4()
    mock_db = MagicMock(spec=DbSession)
    mock_db.scalars.return_value.all.return_value = []

    rows, has_more = _load_cached_matches(user_id, mock_db)

    assert rows == []
    assert has_more is False
    mock_db.scalars.assert_called_once()


def test_load_cached_matches_returns_rows_from_db() -> None:
    """D2: _load_cached_matches returns the rows and has_more flag."""
    from syncup.api.routes.matches import _load_cached_matches

    user_id = uuid.uuid4()
    row = _make_cache_row(user_id, uuid.uuid4())
    mock_db = MagicMock(spec=DbSession)
    mock_db.scalars.return_value.all.return_value = [row]

    rows, has_more = _load_cached_matches(user_id, mock_db)

    assert rows == [row]
    assert has_more is False


def test_load_cached_matches_has_more_true_when_extra_row() -> None:
    """D2: has_more=True when DB returned more rows than the limit."""
    from syncup.api.routes.matches import _load_cached_matches

    user_id = uuid.uuid4()
    # When limit=2 the function fetches 3 (limit+1); if 3 rows come back → has_more=True
    rows = [_make_cache_row(user_id, uuid.uuid4()) for _ in range(3)]
    mock_db = MagicMock(spec=DbSession)
    mock_db.scalars.return_value.all.return_value = rows

    result_rows, has_more = _load_cached_matches(user_id, mock_db, limit=2)

    assert len(result_rows) == 2  # trimmed to limit
    assert has_more is True


def test_load_cached_matches_has_more_false_on_last_page() -> None:
    """D2: has_more=False when DB returned fewer rows than limit+1."""
    from syncup.api.routes.matches import _load_cached_matches

    user_id = uuid.uuid4()
    rows = [_make_cache_row(user_id, uuid.uuid4()) for _ in range(2)]
    mock_db = MagicMock(spec=DbSession)
    mock_db.scalars.return_value.all.return_value = rows

    result_rows, has_more = _load_cached_matches(user_id, mock_db, limit=5)

    assert len(result_rows) == 2
    assert has_more is False


# ---------------------------------------------------------------------------
# D7 — _refresh_match_cache phase split
# ---------------------------------------------------------------------------


def test_refresh_match_cache_always_closes_read_session() -> None:
    """D7: the read session is always closed, even when no matchable users exist."""
    from syncup.api.routes.matches import _refresh_match_cache

    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db
    db.scalars.return_value.all.return_value = []  # no matchable users

    _refresh_match_cache(factory, uuid.uuid4())

    db.close.assert_called()


def test_refresh_match_cache_uses_separate_write_session() -> None:
    """D7: factory() is called twice — once for read, once for write."""
    from syncup.api.routes.matches import _refresh_match_cache

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    item_id = uuid.uuid4()

    read_db = MagicMock(spec=DbSession)
    write_db = MagicMock(spec=DbSession)

    sessions: list[MagicMock] = [read_db, write_db]
    factory = MagicMock(side_effect=sessions)

    # Read-phase data: two matchable users who share an item
    read_db.scalars.return_value.all.return_value = [user_id, other_id]

    r1, r2 = MagicMock(), MagicMock()
    r1.user_id, r1.item_id, r1.service, r1.name = user_id, item_id, "steam", "CS2"
    r2.user_id, r2.item_id, r2.service, r2.name = other_id, item_id, "steam", "CS2"

    pop = MagicMock()
    pop.item_id, pop.pop = item_id, 2

    read_db.execute.return_value.all.side_effect = [[r1, r2], [pop]]

    _refresh_match_cache(factory, user_id)

    assert factory.call_count == 2  # read session + write session
    read_db.close.assert_called()
    write_db.commit.assert_called()
    write_db.close.assert_called()


# ---------------------------------------------------------------------------
# D10 — UUID pair ordering invariant
# ---------------------------------------------------------------------------


def test_match_cache_uuid_pair_always_has_a_less_than_b() -> None:
    """D10: _refresh_match_cache always stores user_a_id < user_b_id in MatchCache."""
    from syncup.api.routes.matches import _refresh_match_cache

    # user_id > other_id — the function must swap them
    user_id = uuid.UUID("ffffffff-ffff-ffff-ffff-000000000001")
    other_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert other_id < user_id  # sanity check for the test setup
    item_id = uuid.uuid4()

    read_db = MagicMock(spec=DbSession)
    write_db = MagicMock(spec=DbSession)
    factory = MagicMock(side_effect=[read_db, write_db])

    read_db.scalars.return_value.all.return_value = [user_id, other_id]

    r1, r2 = MagicMock(), MagicMock()
    r1.user_id, r1.item_id, r1.service, r1.name = user_id, item_id, "steam", "CS2"
    r2.user_id, r2.item_id, r2.service, r2.name = other_id, item_id, "steam", "CS2"

    pop = MagicMock()
    pop.item_id, pop.pop = item_id, 2

    read_db.execute.return_value.all.side_effect = [[r1, r2], [pop]]

    _refresh_match_cache(factory, user_id)

    write_db.merge.assert_called_once()
    merged_row = write_db.merge.call_args[0][0]
    assert merged_row.user_a_id < merged_row.user_b_id, (
        f"Expected user_a_id < user_b_id but got "
        f"{merged_row.user_a_id} >= {merged_row.user_b_id}"
    )


# ---------------------------------------------------------------------------
# D1 — match_cache cleanup task
# ---------------------------------------------------------------------------


def test_cleanup_stale_match_cache_deletes_old_rows() -> None:
    """D1: _cleanup_stale_match_cache executes a DELETE and commits."""
    from syncup.api.routes.matches import _cleanup_stale_match_cache

    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db

    _cleanup_stale_match_cache(factory)

    db.execute.assert_called_once()
    db.commit.assert_called_once()
    db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Empty matchable pool
# ---------------------------------------------------------------------------


def test_get_matches_returns_empty_when_only_user_in_pool(
    match_client: tuple[TestClient, User],
) -> None:
    """When the requesting user is the only matchable user, return empty gracefully."""
    client, _ = match_client
    # Cache miss (empty first page at offset 0) → triggers refresh, returns empty.
    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)), \
         patch("syncup.api.routes.matches._refresh_match_cache"):
        resp = client.get("/api/matches")

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "next_cursor": None}


# ---------------------------------------------------------------------------
# A3 — keyset cursor on (score, user_b_id)
# ---------------------------------------------------------------------------


def test_cursor_encode_decode_roundtrip() -> None:
    """A3: keyset cursor encodes (score, user_a_id, user_b_id) and decodes back exactly."""
    from syncup.api.routes.matches import _decode_cursor, _encode_cursor

    score = 0.854321
    user_a_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_b_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    cursor = _encode_cursor(score, user_a_id, user_b_id)
    decoded = _decode_cursor(cursor)

    assert decoded is not None
    decoded_score, decoded_a, decoded_b = decoded
    assert abs(decoded_score - score) < 1e-5
    assert decoded_a == user_a_id
    assert decoded_b == user_b_id


def test_cursor_decode_returns_none_for_invalid_cursor() -> None:
    """A3: invalid cursor string is gracefully ignored (returns None)."""
    from syncup.api.routes.matches import _decode_cursor

    assert _decode_cursor("not-valid-base64!!") is None
    assert _decode_cursor(None) is None


def test_get_matches_next_cursor_encodes_last_row_position(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """A3: next_cursor encodes (score, user_a_id, user_b_id) of the last returned row."""
    from syncup.api.routes.matches import _decode_cursor

    client, user = match_client
    other = _make_user()
    row = _make_cache_row(user.id, other.id, score=0.75)
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], True)):
        resp = client.get("/api/matches?limit=1")

    cursor = resp.json()["next_cursor"]
    assert cursor is not None
    decoded = _decode_cursor(cursor)
    assert decoded is not None
    decoded_score, decoded_a, decoded_b = decoded
    assert abs(decoded_score - 0.75) < 1e-5
    assert decoded_a == row.user_a_id
    assert decoded_b == row.user_b_id


def test_get_matches_passes_decoded_cursor_to_load_function(
    match_client: tuple[TestClient, User],
) -> None:
    """A3: cursor from request is decoded and forwarded as cursor_score/cursor_user_a_id/cursor_user_b_id."""
    import base64

    client, _ = match_client
    score = 0.75
    a_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    b_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    cursor_str = base64.b64encode(f"{score:.6f}:{a_id}:{b_id}".encode()).decode()

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)) as mock_load, \
         patch("syncup.api.routes.matches._refresh_match_cache"):
        client.get(f"/api/matches?cursor={cursor_str}")

    _, kwargs = mock_load.call_args
    assert kwargs.get("cursor_score") == pytest.approx(score, abs=1e-5)
    assert kwargs.get("cursor_user_a_id") == a_id
    assert kwargs.get("cursor_user_b_id") == b_id
