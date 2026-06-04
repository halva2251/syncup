"""Tests for scripts/enrich_tmdb_metadata.py."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from tests.http_helpers import json_response, make_http, make_session


def _make_film(
    name: str = "Annihilation", year: int = 2018, meta: dict | None = None
) -> SimpleNamespace:  # type: ignore[type-arg]
    return SimpleNamespace(
        id=uuid.uuid4(),
        external_id="tt5580390",
        name=name,
        item_type="film",
        service="letterboxd",
        meta=meta if meta is not None else {"release_year": year, "title_normalized": name.lower()},
    )


def _make_show(
    name: str = "Twin Peaks", year: int = 1990, meta: dict | None = None
) -> SimpleNamespace:  # type: ignore[type-arg]
    return SimpleNamespace(
        id=uuid.uuid4(),
        external_id="tt0098936",
        name=name,
        item_type="show",
        service="trakt",
        meta=meta if meta is not None else {"release_year": year, "title_normalized": name.lower()},
    )


# TMDB API responses
_GENRE_MAP_MOVIE = {
    "genres": [{"id": 878, "name": "Science Fiction"}, {"id": 27, "name": "Horror"}]
}
_GENRE_MAP_TV = {"genres": [{"id": 18, "name": "Drama"}, {"id": 9648, "name": "Mystery"}]}

_MOVIE_SEARCH_RESPONSE = {
    "results": [{"id": 9988, "title": "Annihilation", "genre_ids": [878, 27]}]
}
_TV_SEARCH_RESPONSE = {"results": [{"id": 1273, "name": "Twin Peaks", "genre_ids": [18, 9648]}]}
_EMPTY_SEARCH_RESPONSE = {"results": []}


from scripts.enrich_tmdb_metadata import (
    _normalize_for_match,  # noqa: PLC2701
    enrich_tmdb_items,
    fetch_tmdb_genres,
)


def test_fetch_tmdb_genres_returns_genre_names_for_film() -> None:
    http = make_http([json_response(_MOVIE_SEARCH_RESPONSE)])
    genre_map = {878: "Science Fiction", 27: "Horror"}

    result = fetch_tmdb_genres("Annihilation", 2018, "film", "test-key", http, genre_map)

    assert result == ["Science Fiction", "Horror"]


def test_fetch_tmdb_genres_returns_genre_names_for_show() -> None:
    http = make_http([json_response(_TV_SEARCH_RESPONSE)])
    genre_map = {18: "Drama", 9648: "Mystery"}

    result = fetch_tmdb_genres("Twin Peaks", 1990, "show", "test-key", http, genre_map)

    assert result == ["Drama", "Mystery"]


def test_fetch_tmdb_genres_returns_none_on_no_results() -> None:
    http = make_http([json_response(_EMPTY_SEARCH_RESPONSE)])
    genre_map: dict[int, str] = {}

    result = fetch_tmdb_genres("Nonexistent Film", None, "film", "test-key", http, genre_map)

    assert result is None


def test_fetch_tmdb_genres_returns_none_on_http_error() -> None:
    http = make_http([httpx.Response(401)])
    genre_map: dict[int, str] = {}

    result = fetch_tmdb_genres("Annihilation", 2018, "film", "test-key", http, genre_map)

    assert result is None


def test_fetch_tmdb_genres_returns_none_on_network_error() -> None:
    transport = MagicMock(spec=httpx.BaseTransport)
    transport.handle_request.side_effect = httpx.RequestError("timeout")
    http = httpx.Client(transport=transport)
    genre_map: dict[int, str] = {}

    result = fetch_tmdb_genres("Annihilation", 2018, "film", "test-key", http, genre_map)

    assert result is None


def test_fetch_tmdb_genres_works_without_year() -> None:
    http = make_http([json_response(_MOVIE_SEARCH_RESPONSE)])
    genre_map = {878: "Science Fiction", 27: "Horror"}

    result = fetch_tmdb_genres("Annihilation", None, "film", "test-key", http, genre_map)

    assert result == ["Science Fiction", "Horror"]


def test_enrich_tmdb_items_updates_film_meta() -> None:
    item = _make_film()
    session = make_session([item])
    # genre list fetch + search
    http = make_http(
        [
            json_response(_GENRE_MAP_MOVIE),
            json_response(_GENRE_MAP_TV),
            json_response(_MOVIE_SEARCH_RESPONSE),
        ]
    )

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 1
    assert item.meta["genres"] == ["Science Fiction", "Horror"]
    session.commit.assert_called()


def test_enrich_tmdb_items_updates_show_meta() -> None:
    item = _make_show()
    session = make_session([item])
    http = make_http(
        [
            json_response(_GENRE_MAP_MOVIE),
            json_response(_GENRE_MAP_TV),
            json_response(_TV_SEARCH_RESPONSE),
        ]
    )

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 1
    assert item.meta["genres"] == ["Drama", "Mystery"]


def test_enrich_tmdb_items_skips_on_no_results() -> None:
    item = _make_film("Unknown Film")
    session = make_session([item])
    http = make_http(
        [
            json_response(_GENRE_MAP_MOVIE),
            json_response(_GENRE_MAP_TV),
            json_response(_EMPTY_SEARCH_RESPONSE),
        ]
    )

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 0
    assert "genres" not in item.meta


def test_enrich_tmdb_items_preserves_existing_meta() -> None:
    item = _make_film(meta={"release_year": 2018, "title_normalized": "annihilation"})
    session = make_session([item])
    http = make_http(
        [
            json_response(_GENRE_MAP_MOVIE),
            json_response(_GENRE_MAP_TV),
            json_response(_MOVIE_SEARCH_RESPONSE),
        ]
    )

    enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert item.meta["release_year"] == 2018
    assert "genres" in item.meta


def test_enrich_tmdb_items_continues_after_failure() -> None:
    # First item gets no results; second is "Annihilation" which matches the mock response title.
    items = [_make_film("Film A"), _make_film("Annihilation")]
    session = make_session(items)
    http = make_http(
        [
            json_response(_GENRE_MAP_MOVIE),
            json_response(_GENRE_MAP_TV),
            json_response(_EMPTY_SEARCH_RESPONSE),  # Film A: no result
            json_response(_MOVIE_SEARCH_RESPONSE),  # Annihilation: success
        ]
    )

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 1
    assert "genres" not in items[0].meta
    assert "genres" in items[1].meta


def test_enrich_tmdb_items_empty_returns_zero() -> None:
    session = make_session([])
    http = make_http([json_response(_GENRE_MAP_MOVIE), json_response(_GENRE_MAP_TV)])

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 0


def test_normalize_for_match_strips_punctuation_and_lowercases() -> None:
    assert _normalize_for_match("The Dark Knight!") == "the dark knight"
    assert _normalize_for_match("  Spider-Man: No Way Home  ") == "spiderman no way home"
    assert _normalize_for_match("annihilation") == "annihilation"


def test_fetch_tmdb_genres_returns_none_on_title_mismatch() -> None:
    wrong_title_response = {"results": [{"id": 9999, "title": "Annihilation", "genre_ids": [878]}]}
    http = make_http([json_response(wrong_title_response)])
    genre_map = {878: "Science Fiction"}

    result = fetch_tmdb_genres("Interstellar", 2014, "film", "test-key", http, genre_map)

    assert result is None


def test_enrich_tmdb_items_aborts_when_both_genre_maps_fail() -> None:
    item = _make_film()
    session = make_session([item])
    http = make_http([httpx.Response(500), httpx.Response(500)])

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 0
    session.query.assert_not_called()


def test_enrich_tmdb_items_handles_null_meta() -> None:
    item = _make_film(meta=None)
    item.meta = None  # Simulate a row where the JSONB column returned NULL at the Python layer.
    session = make_session([item])
    http = make_http(
        [
            json_response(_GENRE_MAP_MOVIE),
            json_response(_GENRE_MAP_TV),
            json_response(_MOVIE_SEARCH_RESPONSE),
        ]
    )

    count = enrich_tmdb_items(session, "test-key", http, sleep_s=0.0)

    assert count == 1
    assert item.meta["genres"] == ["Science Fiction", "Horror"]
