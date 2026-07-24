"""Tests for Block H — semantic ANN matching path and matching_mode field.

Covers:
- matching_mode field present in GET /api/matches and GET /api/matches/{id} responses
- _compute_semantic_scores: score = 1 - distance, breakdown, uuid ordering, clamping
- _compute_match_scores: sets matching_mode='heuristic'
- _refresh_match_cache: semantic path taken when combined embedding exists,
  heuristic fallback otherwise
- _read_semantic_data: returns None when user has no combined embedding
- POST /api/me/recompute: triggers embedding build before cache refresh
- _SEMANTIC_CANDIDATE_LIMIT constant
"""

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
# Builders (same pattern as test_matches.py)
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
    matching_mode: str = "heuristic",
) -> MatchCache:
    a, b = (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)
    row = MatchCache()
    row.user_a_id = a
    row.user_b_id = b
    row.score = score
    row.breakdown = {"steam": score}
    row.highlights = [{"service": "steam", "item_name": "Disco Elysium"}]
    row.computed_at = datetime.now(UTC)
    row.matching_mode = matching_mode
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def match_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[tuple[TestClient, User], None, None]:
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


# ---------------------------------------------------------------------------
# matching_mode in API responses
# ---------------------------------------------------------------------------


def test_matching_mode_field_present_in_match_list(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """GET /api/matches includes matching_mode in each match item."""
    client, user = match_client
    other = _make_user(display_name="Sam")
    row = _make_cache_row(user.id, other.id, matching_mode="heuristic")
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)):
        resp = client.get("/api/matches")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["matching_mode"] == "heuristic"


def test_matching_mode_semantic_in_match_list(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """matching_mode='semantic' propagates to response when cache row has semantic mode."""
    client, user = match_client
    other = _make_user()
    row = _make_cache_row(user.id, other.id, matching_mode="semantic")
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)):
        resp = client.get("/api/matches")

    assert resp.json()["items"][0]["matching_mode"] == "semantic"


def test_matching_mode_field_present_in_match_detail(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """GET /api/matches/{user_id} includes matching_mode in response."""
    client, user = match_client
    other = _make_user(display_name="Sam")
    row = _make_cache_row(user.id, other.id, score=0.88, matching_mode="semantic")
    mock_db.get.side_effect = lambda model, pk: row if model is MatchCache else other

    resp = client.get(f"/api/matches/{other.id}")

    assert resp.status_code == 200
    assert resp.json()["matching_mode"] == "semantic"


# ---------------------------------------------------------------------------
# _compute_semantic_scores — pure function tests
# ---------------------------------------------------------------------------


def test_compute_semantic_scores_sets_semantic_mode() -> None:
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    now = datetime.now(UTC)

    results = _compute_semantic_scores(user_id, [(other_id, 0.2)], [], [], now)

    assert len(results) == 1
    assert results[0].matching_mode == "semantic"


def test_compute_semantic_scores_score_is_one_minus_distance() -> None:
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    distance = 0.3
    now = datetime.now(UTC)

    results = _compute_semantic_scores(user_id, [(other_id, distance)], [], [], now)

    assert abs(results[0].score - (1.0 - distance)) < 1e-9


def test_compute_semantic_scores_breakdown_is_combined() -> None:
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    distance = 0.25
    now = datetime.now(UTC)

    results = _compute_semantic_scores(user_id, [(other_id, distance)], [], [], now)

    expected_score = 1.0 - distance
    assert results[0].breakdown == {"combined": pytest.approx(expected_score)}


def test_compute_semantic_scores_uuid_pair_ordered() -> None:
    """user_a_id < user_b_id invariant is maintained."""
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.UUID("ffffffff-ffff-ffff-ffff-000000000001")
    other_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert other_id < user_id

    results = _compute_semantic_scores(user_id, [(other_id, 0.1)], [], [], datetime.now(UTC))

    assert len(results) == 1
    assert results[0].user_a_id < results[0].user_b_id


def test_compute_semantic_scores_clamps_score_above_one() -> None:
    """Distance can theoretically be negative for identical L2-normalised vectors;
    score is clamped to [0, 1]."""
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    # distance=-0.1 → 1 - (-0.1) = 1.1 → clamped to 1.0
    results = _compute_semantic_scores(user_id, [(other_id, -0.1)], [], [], datetime.now(UTC))

    assert results[0].score == pytest.approx(1.0)


def test_compute_semantic_scores_filters_non_positive_similarity() -> None:
    """Candidates with distance >= 1.0 (cosine similarity <= 0) are filtered out."""
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    good_id = uuid.uuid4()
    # distance=1.5 → raw_similarity=-0.5 → filtered
    # distance=1.0 → raw_similarity=0.0 → filtered (boundary)
    # distance=0.0 → kept with score=1.0
    results = _compute_semantic_scores(
        user_id, [(other_id, 1.5), (good_id, 0.0), (uuid.uuid4(), 1.0)], [], [], datetime.now(UTC)
    )

    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0)


def test_compute_semantic_scores_multiple_candidates() -> None:
    """All candidate pairs produce a MatchCache row."""
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    candidates = [(uuid.uuid4(), 0.1 * i) for i in range(5)]
    now = datetime.now(UTC)

    results = _compute_semantic_scores(user_id, candidates, [], [], now)

    assert len(results) == 5
    for row in results:
        assert row.matching_mode == "semantic"
        assert 0.0 <= row.score <= 1.0


def test_compute_semantic_scores_includes_highlights_from_shared_items() -> None:
    """Highlights are computed from shared items even in semantic mode."""
    from syncup.api.routes.matches import _compute_semantic_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    item_id = uuid.uuid4()

    item_row_me = MagicMock()
    item_row_me.user_id = user_id
    item_row_me.item_id = item_id
    item_row_me.service = "steam"
    item_row_me.name = "Disco Elysium"

    item_row_other = MagicMock()
    item_row_other.user_id = other_id
    item_row_other.item_id = item_id
    item_row_other.service = "steam"
    item_row_other.name = "Disco Elysium"

    pop_row = MagicMock()
    pop_row.item_id = item_id
    pop_row.pop = 2

    results = _compute_semantic_scores(
        user_id,
        [(other_id, 0.2)],
        [item_row_me, item_row_other],
        [pop_row],
        datetime.now(UTC),
    )

    assert len(results) == 1
    assert results[0].highlights == [{"service": "steam", "item_name": "Disco Elysium"}]


def test_compute_semantic_scores_empty_candidates() -> None:
    """Empty candidate list produces empty results."""
    from syncup.api.routes.matches import _compute_semantic_scores

    results = _compute_semantic_scores(uuid.uuid4(), [], [], [], datetime.now(UTC))

    assert results == []


# ---------------------------------------------------------------------------
# _compute_match_scores — heuristic mode tag
# ---------------------------------------------------------------------------


def test_compute_match_scores_sets_heuristic_mode() -> None:
    """_compute_match_scores tags cache rows with matching_mode='heuristic'."""
    from syncup.api.routes.matches import _compute_match_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    item_id = uuid.uuid4()
    now = datetime.now(UTC)

    r1, r2 = MagicMock(), MagicMock()
    r1.user_id, r1.item_id, r1.service, r1.name = user_id, item_id, "steam", "CS2"
    r2.user_id, r2.item_id, r2.service, r2.name = other_id, item_id, "steam", "CS2"

    pop = MagicMock()
    pop.item_id, pop.pop = item_id, 2

    results = _compute_match_scores(user_id, [user_id, other_id], [r1, r2], [pop], now)

    assert len(results) == 1
    assert results[0].matching_mode == "heuristic"


def test_compute_match_scores_highlights_only_mutual_visible_taste() -> None:
    """A shared low-ranked item is not presented as a top-taste highlight."""
    from syncup.api.routes.matches import _compute_match_scores

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    shared_top = uuid.uuid4()
    shared_low_ranked = uuid.uuid4()

    rows = []
    for owner, unique_prefix in ((user_id, "Mine"), (other_id, "Theirs")):
        item_ids = [shared_top, *(uuid.uuid4() for _ in range(4)), shared_low_ranked]
        for rank, item_id in enumerate(item_ids, start=1):
            row = MagicMock()
            row.user_id = owner
            row.item_id = item_id
            row.service = "lastfm"
            row.item_type = "artist"
            row.name = (
                "Shared top artist"
                if item_id == shared_top
                else "Shared lower-ranked artist"
                if item_id == shared_low_ranked
                else f"{unique_prefix} artist {rank}"
            )
            row.engagement_score = float(7 - rank)
            rows.append(row)

    pop_rows = []
    for item_id in (shared_top, shared_low_ranked):
        pop = MagicMock()
        pop.item_id = item_id
        pop.pop = 2
        pop_rows.append(pop)

    results = _compute_match_scores(
        user_id,
        [user_id, other_id],
        rows,
        pop_rows,
        datetime.now(UTC),
    )

    assert results[0].highlights == [
        {"service": "lastfm", "item_name": "Shared top artist"}
    ]


# ---------------------------------------------------------------------------
# _refresh_match_cache — path selection
# ---------------------------------------------------------------------------


def test_refresh_takes_semantic_path_when_embedding_exists() -> None:
    """_refresh_match_cache uses semantic path when _read_semantic_data returns data."""
    from syncup.api.routes.matches import _refresh_match_cache

    user_id = uuid.uuid4()
    candidate = (uuid.uuid4(), 0.3)

    with (
        patch(
            "syncup.api.routes.matches._read_semantic_data",
            return_value=([candidate], [], []),
        ) as mock_sem,
        patch("syncup.api.routes.matches._read_match_data") as mock_heuristic,
        patch("syncup.api.routes.matches._write_match_results"),
    ):
        _refresh_match_cache(MagicMock(), user_id)

    mock_sem.assert_called_once()
    mock_heuristic.assert_not_called()


def test_refresh_falls_back_to_heuristic_when_no_embedding() -> None:
    """_refresh_match_cache uses heuristic when _read_semantic_data returns None."""
    from syncup.api.routes.matches import _refresh_match_cache

    user_id = uuid.uuid4()

    with (
        patch("syncup.api.routes.matches._read_semantic_data", return_value=None) as mock_sem,
        patch("syncup.api.routes.matches._read_match_data", return_value=None) as mock_heuristic,
    ):
        _refresh_match_cache(MagicMock(), user_id)

    mock_sem.assert_called_once()
    mock_heuristic.assert_called_once()


def test_refresh_semantic_path_writes_results() -> None:
    """Semantic path calls _write_match_results when candidates are found."""
    from syncup.api.routes.matches import _refresh_match_cache

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    candidate = (other_id, 0.2)

    with (
        patch(
            "syncup.api.routes.matches._read_semantic_data",
            return_value=([candidate], [], []),
        ),
        patch("syncup.api.routes.matches._write_match_results") as mock_write,
    ):
        _refresh_match_cache(MagicMock(), user_id)

    mock_write.assert_called_once()
    written_results = mock_write.call_args[0][1]
    assert len(written_results) == 1
    assert written_results[0].matching_mode == "semantic"


def test_refresh_heuristic_path_writes_results() -> None:
    """Heuristic fallback path calls _write_match_results when matches are found."""
    from syncup.api.routes.matches import _refresh_match_cache

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    item_id = uuid.uuid4()

    r1, r2 = MagicMock(), MagicMock()
    r1.user_id, r1.item_id, r1.service, r1.name = user_id, item_id, "steam", "CS2"
    r2.user_id, r2.item_id, r2.service, r2.name = other_id, item_id, "steam", "CS2"
    pop = MagicMock()
    pop.item_id, pop.pop = item_id, 2

    with (
        patch("syncup.api.routes.matches._read_semantic_data", return_value=None),
        patch(
            "syncup.api.routes.matches._read_match_data",
            return_value=([user_id, other_id], [r1, r2], [pop]),
        ),
        patch("syncup.api.routes.matches._write_match_results") as mock_write,
    ):
        _refresh_match_cache(MagicMock(), user_id)

    mock_write.assert_called_once()
    written_results = mock_write.call_args[0][1]
    assert all(r.matching_mode == "heuristic" for r in written_results)


# ---------------------------------------------------------------------------
# _read_semantic_data — DB interaction
# ---------------------------------------------------------------------------


def test_read_semantic_data_returns_none_when_no_combined_embedding() -> None:
    """_read_semantic_data returns None when user has no combined embedding row."""
    from syncup.api.routes.matches import _read_semantic_data

    user_id = uuid.uuid4()
    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db
    db.execute.return_value.scalar_one_or_none.return_value = None

    result = _read_semantic_data(factory, user_id)

    assert result is None
    db.close.assert_called_once()


def test_read_semantic_data_always_closes_session_on_error() -> None:
    """_read_semantic_data always closes its session even when an exception is raised."""
    from syncup.api.routes.matches import _read_semantic_data

    user_id = uuid.uuid4()
    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db
    db.execute.side_effect = RuntimeError("DB exploded")

    result = _read_semantic_data(factory, user_id)

    assert result is None
    db.close.assert_called_once()


def test_read_semantic_data_happy_path() -> None:
    """_read_semantic_data returns candidate pairs, item rows, and pop rows."""
    from syncup.api.routes.matches import _read_semantic_data

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db

    # First execute: scalar_one_or_none returns the embedding
    # Second execute: ANN query returns candidates
    # Third execute: item rows
    # Fourth execute: pop rows
    embed_scalar = MagicMock()
    embed_scalar.scalar_one_or_none.return_value = [0.1] * 384

    ann_row = MagicMock()
    ann_row.user_id = str(other_id)
    ann_row.distance = 0.25
    ann_result = MagicMock()
    ann_result.all.return_value = [ann_row]

    item_row = MagicMock()
    item_row.user_id = user_id
    item_row.item_id = uuid.uuid4()
    item_row.service = "steam"
    item_row.name = "Disco Elysium"
    item_result = MagicMock()
    item_result.all.return_value = [item_row]

    pop_row = MagicMock()
    pop_row.item_id = item_row.item_id
    pop_row.pop = 2
    pop_result = MagicMock()
    pop_result.all.return_value = [pop_row]

    db.execute.side_effect = [embed_scalar, ann_result, item_result, pop_result]

    result = _read_semantic_data(factory, user_id)

    assert result is not None
    candidate_pairs, item_rows, pop_rows = result
    assert len(candidate_pairs) == 1
    assert candidate_pairs[0][0] == other_id
    assert candidate_pairs[0][1] == pytest.approx(0.25)
    assert len(item_rows) == 1
    assert len(pop_rows) == 1
    db.close.assert_called_once()


# ---------------------------------------------------------------------------
# _SEMANTIC_CANDIDATE_LIMIT constant
# ---------------------------------------------------------------------------


def test_semantic_candidate_limit_is_fifty() -> None:
    from syncup.api.routes.matches import _SEMANTIC_CANDIDATE_LIMIT

    assert _SEMANTIC_CANDIDATE_LIMIT == 50


# ---------------------------------------------------------------------------
# POST /api/me/recompute — embedding build + cache refresh ordering
# ---------------------------------------------------------------------------


def test_recompute_triggers_embedding_build_before_cache_refresh(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """POST /api/me/recompute triggers _build_embedding_bg before _refresh_match_cache."""
    client, _ = match_client
    from syncup.api.app import app
    from syncup.limiter import limiter

    limiter._storage.reset()

    fake_settings = MagicMock()
    fake_settings.llm_api_key = None

    call_order: list[str] = []

    def mock_build_bg(*args: object, **kwargs: object) -> None:
        call_order.append("build")

    def mock_refresh(*args: object, **kwargs: object) -> None:
        call_order.append("refresh")

    with patch.object(app.state, "settings", fake_settings):
        with (
            patch("syncup.api.routes.matches._build_embedding_bg", mock_build_bg),
            patch("syncup.api.routes.matches._refresh_match_cache", mock_refresh),
        ):
            resp = client.post("/api/me/recompute")

    assert resp.status_code == 204
    assert call_order == ["build", "refresh"]


def test_build_embedding_bg_swallows_sync_up_error_gracefully() -> None:
    """_build_embedding_bg does not raise when build_user_embedding raises SyncUpError."""
    from syncup.api.routes.matches import _build_embedding_bg
    from syncup.exceptions import SyncUpError

    user_id = uuid.uuid4()
    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db

    with patch(
        "syncup.api.routes.matches.build_user_embedding",
        side_effect=SyncUpError("NO_EMBEDDINGS_AVAILABLE", "none", 422),
    ):
        _build_embedding_bg(factory, user_id)

    db.close.assert_called_once()


def test_build_embedding_bg_always_closes_session() -> None:
    """_build_embedding_bg closes its session even when an unexpected exception occurs."""
    from syncup.api.routes.matches import _build_embedding_bg

    user_id = uuid.uuid4()
    factory = MagicMock()
    db = MagicMock(spec=DbSession)
    factory.return_value = db

    with patch(
        "syncup.api.routes.matches.build_user_embedding",
        side_effect=RuntimeError("unexpected"),
    ):
        _build_embedding_bg(factory, user_id)

    db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Fix #4 — semantic mode is authoritative: no heuristic fallthrough when a
# combined embedding exists but every ANN neighbour scores <= 0.
# ---------------------------------------------------------------------------


def test_refresh_semantic_authoritative_no_heuristic_fallthrough() -> None:
    """When an embedding exists but all ANN candidates score <= 0, the refresh must
    NOT fall through to the heuristic path (would churn symmetric pairs / flip mode)."""
    from syncup.api.routes.matches import _refresh_match_cache

    user_id = uuid.uuid4()
    other_id = uuid.uuid4()
    # distance 1.5 → similarity -0.5 → filtered out by _compute_semantic_scores
    far_candidate = (other_id, 1.5)

    with (
        patch(
            "syncup.api.routes.matches._read_semantic_data",
            return_value=([far_candidate], [], []),
        ) as mock_sem,
        patch("syncup.api.routes.matches._read_match_data") as mock_heuristic,
        patch("syncup.api.routes.matches._write_match_results") as mock_write,
    ):
        _refresh_match_cache(MagicMock(), user_id)

    mock_sem.assert_called_once()
    mock_heuristic.assert_not_called()  # authoritative — no fallthrough
    mock_write.assert_not_called()  # nothing positive to write


# ---------------------------------------------------------------------------
# Fix #3 — in-flight refresh guard (dedupe redundant background refreshes)
# ---------------------------------------------------------------------------


def test_refresh_releases_in_flight_flag_on_success() -> None:
    from syncup.api.routes import matches as m

    user_id = uuid.uuid4()
    m._refresh_in_flight.add(user_id)
    with (
        patch("syncup.api.routes.matches._read_semantic_data", return_value=None),
        patch("syncup.api.routes.matches._read_match_data", return_value=None),
    ):
        m._refresh_match_cache(MagicMock(), user_id)
    assert user_id not in m._refresh_in_flight


def test_refresh_releases_in_flight_flag_on_exception() -> None:
    from syncup.api.routes import matches as m

    user_id = uuid.uuid4()
    m._refresh_in_flight.add(user_id)
    with (
        patch("syncup.api.routes.matches._read_semantic_data", return_value=None),
        patch(
            "syncup.api.routes.matches._read_match_data",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError),
    ):
        m._refresh_match_cache(MagicMock(), user_id)
    assert user_id not in m._refresh_in_flight


def test_empty_page_skips_refresh_when_already_in_flight(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """A second empty-page request while a refresh is in flight must not schedule another."""
    from syncup.api.routes import matches as m

    client, user = match_client
    m._refresh_in_flight.add(user.id)
    try:
        with (
            patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)),
            patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh,
        ):
            resp = client.get("/api/matches")
        assert resp.status_code == 200
        mock_refresh.assert_not_called()
    finally:
        m._refresh_in_flight.discard(user.id)


def test_empty_page_schedules_refresh_when_not_in_flight(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    from syncup.api.routes import matches as m

    client, user = match_client
    m._refresh_in_flight.discard(user.id)
    try:
        with (
            patch("syncup.api.routes.matches._load_cached_matches", return_value=([], False)),
            patch("syncup.api.routes.matches._refresh_match_cache") as mock_refresh,
        ):
            resp = client.get("/api/matches")
        assert resp.status_code == 200
        mock_refresh.assert_called_once()
    finally:
        m._refresh_in_flight.discard(user.id)


# ---------------------------------------------------------------------------
# Fix #4 — match list tolerates malformed highlight JSON without 500
# ---------------------------------------------------------------------------


def test_match_list_skips_malformed_highlight(
    match_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    """A drifted/legacy cache row with a malformed highlight must not 500 the list."""
    client, user = match_client
    other = _make_user(display_name="Sam")
    row = _make_cache_row(user.id, other.id)
    # One good highlight, one malformed (missing 'item_name'), one wrong type
    row.highlights = [
        {"service": "steam", "item_name": "Disco Elysium"},
        {"service": "steam"},
        "not-a-dict",
    ]
    mock_db.scalars.return_value.all.return_value = [other]

    with patch("syncup.api.routes.matches._load_cached_matches", return_value=([row], False)):
        resp = client.get("/api/matches")

    assert resp.status_code == 200
    highlights = resp.json()["items"][0]["shared_highlights"]
    assert highlights == [{"service": "steam", "item_name": "Disco Elysium"}]
