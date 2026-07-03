"""Tests for the search registry and dispatch logic."""

from __future__ import annotations

import httpx
import pytest

from syncup.ingest.search.registry import (
    SearchConfig,
    allowed_categories,
    clear_cache,
    close_all,
    get_default_config,
    search_category,
    set_default_config,
)
from tests.http_helpers import SequenceTransport, json_response, make_http


@pytest.fixture(autouse=True)
def _clear_cache_and_config() -> None:
    clear_cache()
    set_default_config(SearchConfig())


def test_allowed_categories_includes_all_obsession_categories() -> None:
    assert allowed_categories() == {
        "game",
        "music",
        "film",
        "book",
        "show",
        "anime",
        "manga",
        "community",
        "other",
    }


def test_search_category_rejects_unknown_category() -> None:
    with pytest.raises(ValueError, match="Unknown obsession category"):
        search_category("invalid", "query")


def test_search_category_returns_empty_for_blank_query() -> None:
    assert search_category("game", "   ") == []


def test_search_category_returns_empty_for_unsupported_category() -> None:
    assert search_category("community", "anything") == []
    assert search_category("other", "anything") == []


def test_search_category_uses_config() -> None:
    body = {
        "items": [
            {"id": 632470, "name": "Disco Elysium", "is_free": False},
        ]
    }
    config = SearchConfig(http=make_http([json_response(body)]))
    results = search_category("game", "disco", limit=5, config=config)

    assert len(results) == 1
    assert results[0].name == "Disco Elysium"


def test_search_category_caches_results() -> None:
    body = {
        "items": [
            {"id": 632470, "name": "Disco Elysium", "is_free": False},
        ]
    }
    config = SearchConfig(http=make_http([json_response(body)]))

    # First call hits the mock (consumes the one response).
    results1 = search_category("game", "disco", limit=5, config=config)
    assert len(results1) == 1

    # Second call with the same args should be served from cache.
    results2 = search_category("game", "disco", limit=5, config=config)
    assert len(results2) == 1


def test_search_category_without_config_uses_default() -> None:
    # Default config has no API keys, so film/book/music return empty.
    assert search_category("film", "blade runner") == []


def test_search_category_returns_empty_on_upstream_failure() -> None:
    config = SearchConfig(http=httpx.Client(transport=SequenceTransport([httpx.Response(500)])))
    assert search_category("game", "disco", limit=5, config=config) == []


def test_search_category_uses_google_books_when_key_set() -> None:
    body = {
        "items": [
            {
                "id": "abc123",
                "volumeInfo": {
                    "title": "Dune",
                    "authors": ["Frank Herbert"],
                    "publishedDate": "1965",
                },
            }
        ]
    }
    config = SearchConfig(
        google_books_api_key="test-key",
        http=make_http([json_response(body)]),
    )
    results = search_category("book", "dune", limit=5, config=config)

    assert len(results) == 1
    assert results[0].name == "Dune"
    assert results[0].service == "google_books"


def test_close_all_closes_default_config_and_clears_cache() -> None:
    body = {
        "items": [
            {"id": 632470, "name": "Disco Elysium", "is_free": False},
        ]
    }
    config = SearchConfig(http=make_http([json_response(body)]))
    set_default_config(config)
    search_category("game", "disco", limit=5)

    close_all()

    assert config.http.is_closed
    assert get_default_config() is not config
