"""Tests for GET /api/me/taste."""
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


def _taste_row(
    service: str,
    item_type: str,
    name: str,
    *,
    external_id: str = "ext-1",
    user_item_id: uuid.UUID | None = None,
    engagement_score: float = 0.8,
    raw_value: float | None = None,
    meta: dict | None = None,
    excluded: bool = False,
) -> MagicMock:
    row = MagicMock()
    row.service = service
    row.item_type = item_type
    row.name = name
    row.external_id = external_id
    row.user_item_id = user_item_id or uuid.uuid4()
    row.engagement_score = engagement_score
    row.raw_value = raw_value
    row.meta = meta or {}
    row.excluded = excluded
    return row


def _override_row(
    item_name: str = "CS2",
    boost_multiplier: float = 2.0,
) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.item_name = item_name
    row.boost_multiplier = boost_multiplier
    return row


def _set_execute_results(
    mock_db: MagicMock,
    taste_rows: list,
    override_rows: list | None = None,
) -> None:
    """Wire the two db.execute() calls made by GET /api/me/taste."""
    taste_result = MagicMock()
    taste_result.all.return_value = taste_rows
    override_result = MagicMock()
    override_result.all.return_value = override_rows or []
    mock_db.execute.side_effect = [taste_result, override_result]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
def taste_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Authenticated client with all DB calls mocked to return empty results."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    _set_execute_results(mock_db, [])
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


def test_taste_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/me/taste")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_public_taste_card_returns_matchable_user_taste(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    user = _make_user(
        is_matchable=True,
        archetype="The Night Listener",
        vibe_summary="A patient listener with a love of atmosphere.",
        key_themes=["ambient", "indie"],
    )
    mock_db.get.return_value = user
    _set_execute_results(mock_db, [_taste_row("steam", "game", "Disco Elysium")])

    resp = taste_client.get(f"/api/users/{user.id}/taste-card")

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["archetype"] == "The Night Listener"
    assert body["taste"]["services"]["steam"]["top_games"][0]["name"] == "Disco Elysium"
    assert body["taste"]["overrides"] == []
    taste_query = str(mock_db.execute.call_args_list[0].args[0])
    assert "user_items.excluded IS false" in taste_query


def test_public_taste_card_hides_non_matchable_users(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    user = _make_user(is_matchable=False)
    mock_db.get.return_value = user

    resp = taste_client.get(f"/api/users/{user.id}/taste-card")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


def test_taste_returns_empty_profile(taste_client: TestClient) -> None:
    resp = taste_client.get("/api/me/taste")
    assert resp.status_code == 200
    body = resp.json()
    assert body["services"] == {}
    assert body["manual_obsessions"] == []
    assert body["overrides"] == []


# ---------------------------------------------------------------------------
# Steam
# ---------------------------------------------------------------------------


def test_taste_returns_steam_top_games(taste_client: TestClient, mock_db: MagicMock) -> None:
    user_item_id = uuid.uuid4()
    row = _taste_row(
        "steam",
        "game",
        "Disco Elysium",
        user_item_id=user_item_id,
        external_id="2136",
        engagement_score=0.9,
        raw_value=720.0,
    )
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    assert resp.status_code == 200
    games = resp.json()["services"]["steam"]["top_games"]
    assert len(games) == 1
    assert games[0]["id"] == str(user_item_id)
    assert games[0]["name"] == "Disco Elysium"
    assert games[0]["score"] == pytest.approx(0.9)
    assert games[0]["hours"] == pytest.approx(12.0)  # 720 min / 60


def test_taste_includes_excluded_items_for_recovery(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    _set_execute_results(
        mock_db,
        [_taste_row("steam", "game", "Disco Elysium", excluded=True)],
    )

    resp = taste_client.get("/api/me/taste")

    assert resp.status_code == 200
    game = resp.json()["services"]["steam"]["top_games"][0]
    assert game["excluded"] is True


def test_taste_steam_hours_calculated_from_raw_value(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row("steam", "game", "Half-Life 2", raw_value=90.0)
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    hours = resp.json()["services"]["steam"]["top_games"][0]["hours"]
    assert hours == pytest.approx(1.5)


def test_taste_steam_hours_zero_when_no_raw_value(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row("steam", "game", "CS2", raw_value=None)
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    hours = resp.json()["services"]["steam"]["top_games"][0]["hours"]
    assert hours == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Last.fm
# ---------------------------------------------------------------------------


def test_taste_returns_lastfm_top_artists(taste_client: TestClient, mock_db: MagicMock) -> None:
    row = _taste_row(
        "lastfm", "artist", "Arca", external_id="arca-mbid", engagement_score=0.85, raw_value=1500.0
    )
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    artists = resp.json()["services"]["lastfm"]["top_artists"]
    assert len(artists) == 1
    assert artists[0]["name"] == "Arca"
    assert artists[0]["play_count"] == pytest.approx(1500.0)


def test_taste_returns_lastfm_top_tracks_with_artist(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row(
        "lastfm",
        "track",
        "Nonbinary",
        external_id="nonbinary-id",
        engagement_score=0.7,
        raw_value=300.0,
        meta={"artist": "Arca"},
    )
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    tracks = resp.json()["services"]["lastfm"]["top_tracks"]
    assert len(tracks) == 1
    assert tracks[0]["name"] == "Nonbinary"
    assert tracks[0]["artist"] == "Arca"
    assert tracks[0]["play_count"] == pytest.approx(300.0)


def test_taste_lastfm_top_tags_always_empty(taste_client: TestClient, mock_db: MagicMock) -> None:
    row = _taste_row("lastfm", "artist", "Burial", engagement_score=0.6)
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    assert resp.json()["services"]["lastfm"]["top_tags"] == []


# ---------------------------------------------------------------------------
# Spotify
# ---------------------------------------------------------------------------


def test_taste_returns_spotify_top_artists(taste_client: TestClient, mock_db: MagicMock) -> None:
    row = _taste_row(
        "spotify", "artist", "FKA twigs", external_id="twigs-id", engagement_score=0.95
    )
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    artists = resp.json()["services"]["spotify"]["top_artists"]
    assert len(artists) == 1
    assert artists[0]["name"] == "FKA twigs"
    assert artists[0]["score"] == pytest.approx(0.95)


def test_taste_returns_spotify_top_tracks_with_artists_list(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row(
        "spotify",
        "track",
        "cellophane",
        external_id="cell-id",
        engagement_score=0.88,
        meta={"artists": ["FKA twigs"]},
    )
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    tracks = resp.json()["services"]["spotify"]["top_tracks"]
    assert tracks[0]["artists"] == ["FKA twigs"]


# ---------------------------------------------------------------------------
# Service filtering
# ---------------------------------------------------------------------------


def test_taste_excludes_services_with_no_items(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row("steam", "game", "Half-Life 2", engagement_score=0.9)
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    services = resp.json()["services"]
    assert "steam" in services
    assert "spotify" not in services
    assert "lastfm" not in services


# ---------------------------------------------------------------------------
# Ordering and limits
# ---------------------------------------------------------------------------


def test_taste_items_ordered_by_score_descending(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    rows = [
        _taste_row("steam", "game", "High Score", external_id="high", engagement_score=0.9),
        _taste_row("steam", "game", "Low Score", external_id="low", engagement_score=0.1),
    ]
    _set_execute_results(mock_db, rows)

    resp = taste_client.get("/api/me/taste")
    games = resp.json()["services"]["steam"]["top_games"]
    assert games[0]["name"] == "High Score"
    assert games[1]["name"] == "Low Score"


def test_taste_limits_to_top_20_per_item_type(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    # D3: SQL ROW_NUMBER() OVER (...) caps rows before Python sees them.
    # The mock returns exactly 20 rows (simulating what the window function emits).
    rows = [
        _taste_row(
            "steam", "game", f"Game {i}", external_id=str(i), engagement_score=1.0 - i * 0.01
        )
        for i in range(20)
    ]
    _set_execute_results(mock_db, rows)

    resp = taste_client.get("/api/me/taste")
    games = resp.json()["services"]["steam"]["top_games"]
    assert len(games) == 20


def test_taste_top_20_limit_is_per_group_not_global(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    # D3: each partition (steam/game, spotify/artist) gets its own ROW_NUMBER() window.
    # Mock returns exactly 20 per group as the SQL would.
    steam_rows = [
        _taste_row(
            "steam", "game", f"Game {i}", external_id=f"g{i}", engagement_score=1.0 - i * 0.01
        )
        for i in range(20)
    ]
    spotify_rows = [
        _taste_row(
            "spotify", "artist", f"Artist {i}", external_id=f"a{i}", engagement_score=0.5 - i * 0.01
        )
        for i in range(20)
    ]
    _set_execute_results(mock_db, steam_rows + spotify_rows)

    resp = taste_client.get("/api/me/taste")
    services = resp.json()["services"]
    assert len(services["steam"]["top_games"]) == 20
    assert len(services["spotify"]["top_artists"]) == 20


def test_taste_ignores_unknown_service_item_type_combinations(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    known_row = _taste_row("steam", "game", "Half-Life 2", engagement_score=0.9)
    unknown_row = _taste_row("anilist", "character", "Rei", engagement_score=0.8)
    _set_execute_results(mock_db, [known_row, unknown_row])

    resp = taste_client.get("/api/me/taste")
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert "steam" in services
    assert "anilist" not in services


def test_taste_returns_anilist_anime_and_manga(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    anime = _taste_row("anilist", "anime", "Serial Experiments Lain", engagement_score=0.9)
    manga = _taste_row("anilist", "manga", "Berserk", engagement_score=1.0)
    _set_execute_results(mock_db, [anime, manga])

    resp = taste_client.get("/api/me/taste")

    assert resp.status_code == 200
    service = resp.json()["services"]["anilist"]
    assert service["top_anime"][0]["name"] == "Serial Experiments Lain"
    assert service["top_anime"][0]["score"] == pytest.approx(0.9)
    assert service["top_manga"][0]["name"] == "Berserk"


def test_taste_returns_letterboxd_films(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row("letterboxd", "film", "Stalker", engagement_score=1.0)
    row.meta = {"title_normalized": "stalker", "release_year": 1979}
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert "letterboxd" in services
    films = services["letterboxd"]["top_films"]
    assert len(films) == 1
    assert films[0]["name"] == "Stalker"
    assert films[0]["release_year"] == 1979
    assert films[0]["score"] == pytest.approx(1.0)


def test_taste_returns_rateyourmusic_albums_with_rating_and_artist(
    taste_client: TestClient, mock_db: MagicMock
) -> None:
    row = _taste_row(
        "rateyourmusic",
        "album",
        "Eyes of the Mind",
        engagement_score=0.89,
        raw_value=9.0,
        meta={
            "title_normalized": "eyes of the mind",
            "release_year": 1981,
            "artist_normalized": "casiopea",
        },
    )
    _set_execute_results(mock_db, [row])

    resp = taste_client.get("/api/me/taste")
    assert resp.status_code == 200
    services = resp.json()["services"]
    assert "rateyourmusic" in services
    albums = services["rateyourmusic"]["top_albums"]
    assert len(albums) == 1
    assert albums[0]["name"] == "Eyes of the Mind"
    assert albums[0]["artist"] == "casiopea"
    assert albums[0]["rating"] == pytest.approx(9.0)
    assert albums[0]["release_year"] == 1981


# ---------------------------------------------------------------------------
# Manual obsessions
# ---------------------------------------------------------------------------


def test_taste_returns_manual_obsessions(taste_client: TestClient, mock_db: MagicMock) -> None:
    obs = _make_obsession(category="book", name="Blindsight", weight=2.0)
    mock_db.scalars.return_value.all.return_value = [obs]

    resp = taste_client.get("/api/me/taste")
    assert resp.status_code == 200
    obsessions = resp.json()["manual_obsessions"]
    assert len(obsessions) == 1
    assert obsessions[0]["category"] == "book"
    assert obsessions[0]["name"] == "Blindsight"
    assert obsessions[0]["weight"] == pytest.approx(2.0)
    assert "id" in obsessions[0]


# ---------------------------------------------------------------------------
# Preference overrides
# ---------------------------------------------------------------------------


def test_taste_returns_preference_overrides(taste_client: TestClient, mock_db: MagicMock) -> None:
    override = _override_row(item_name="Disco Elysium", boost_multiplier=3.0)
    _set_execute_results(mock_db, [], [override])

    resp = taste_client.get("/api/me/taste")
    overrides = resp.json()["overrides"]
    assert len(overrides) == 1
    assert overrides[0]["item"]["name"] == "Disco Elysium"
    assert overrides[0]["boost_multiplier"] == pytest.approx(3.0)
    assert "id" in overrides[0]
