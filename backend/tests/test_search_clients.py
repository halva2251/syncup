"""Tests for the autocomplete search clients."""

from __future__ import annotations

import time

import httpx
import pytest

from syncup.ingest.search.anilist import AniListSearchClient
from syncup.ingest.search.google_books import GoogleBooksSearchClient
from syncup.ingest.search.musicbrainz import MusicBrainzSearchClient
from syncup.ingest.search.openlibrary import OpenLibrarySearchClient
from syncup.ingest.search.steam import SteamSearchClient
from syncup.ingest.search.tmdb import TmdbSearchClient
from tests.http_helpers import SequenceTransport, json_response, make_http


def _transport(response: httpx.Response) -> SequenceTransport:
    return SequenceTransport([response])


class TestSteamSearchClient:
    def test_search_returns_games(self) -> None:
        body = {
            "items": [
                {"id": 632470, "name": "Disco Elysium", "is_free": False},
                {"id": 753640, "name": "Outer Wilds", "is_free": False},
            ]
        }
        client = SteamSearchClient(http=make_http([json_response(body)]))
        results = client.search("disco", limit=5)

        assert len(results) == 2
        assert results[0].name == "Disco Elysium"
        assert results[0].external_id == "632470"
        assert results[0].item_type == "game"
        assert results[0].service == "steam"

    def test_search_returns_empty_for_blank_query(self) -> None:
        client = SteamSearchClient(http=httpx.Client(transport=SequenceTransport([])))
        assert client.search("   ", limit=5) == []

    def test_search_returns_empty_on_http_error(self) -> None:
        client = SteamSearchClient(
            http=httpx.Client(transport=SequenceTransport([httpx.Response(500)]))
        )
        assert client.search("disco", limit=5) == []

    def test_search_skips_items_without_name(self) -> None:
        body = {"items": [{"id": 1, "name": ""}, {"id": 2, "name": "Valid Game"}]}
        client = SteamSearchClient(http=make_http([json_response(body)]))
        results = client.search("game", limit=5)
        assert len(results) == 1
        assert results[0].name == "Valid Game"


class TestTmdbSearchClient:
    def test_search_films_requires_api_key(self) -> None:
        client = TmdbSearchClient(api_key=None)
        assert client.search_films("blade runner", limit=5) == []

    def test_search_films_returns_results(self) -> None:
        body = {
            "results": [
                {
                    "id": 335984,
                    "title": "Blade Runner 2049",
                    "release_date": "2017-10-04",
                    "overview": "Thirty years after...",
                }
            ]
        }
        client = TmdbSearchClient(api_key="test-key", http=make_http([json_response(body)]))
        results = client.search_films("blade runner", limit=5)

        assert len(results) == 1
        assert results[0].name == "Blade Runner 2049"
        assert results[0].item_type == "film"
        assert results[0].external_id == "335984"
        assert results[0].extra.get("year") == 2017

    def test_search_shows_returns_results(self) -> None:
        body = {
            "results": [
                {
                    "id": 1399,
                    "name": "The Sopranos",
                    "first_air_date": "1999-01-10",
                }
            ]
        }
        client = TmdbSearchClient(api_key="test-key", http=make_http([json_response(body)]))
        results = client.search_shows("sopranos", limit=5)

        assert len(results) == 1
        assert results[0].name == "The Sopranos"
        assert results[0].item_type == "show"


class TestAniListSearchClient:
    def test_search_anime_returns_results(self) -> None:
        body = {
            "data": {
                "Page": {
                    "media": [
                        {
                            "id": 1,
                            "title": {"english": "Cowboy Bebop", "romaji": "Cowboy Bebop"},
                            "format": "TV",
                            "seasonYear": 1998,
                            "startDate": {"year": 1998},
                        }
                    ]
                }
            }
        }
        client = AniListSearchClient(http=make_http([json_response(body)]))
        results = client.search_anime("cowboy", limit=5)

        assert len(results) == 1
        assert results[0].name == "Cowboy Bebop"
        assert results[0].item_type == "anime"
        assert results[0].external_id == "1"
        assert results[0].extra.get("year") == 1998

    def test_search_returns_empty_on_graphql_errors(self) -> None:
        body = {"errors": [{"message": "Bad query"}]}
        client = AniListSearchClient(http=make_http([json_response(body)]))
        assert client.search_anime("cowboy", limit=5) == []

    def test_search_returns_empty_on_http_error(self) -> None:
        client = AniListSearchClient(
            http=httpx.Client(transport=SequenceTransport([httpx.Response(500)]))
        )
        assert client.search_anime("cowboy", limit=5) == []


class TestMusicBrainzSearchClient:
    def test_search_artists_respects_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(MusicBrainzSearchClient, "_last_request_at", time.monotonic() - 0.1)
        body = {
            "artists": [
                {
                    "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "name": "Radiohead",
                    "country": "GB",
                }
            ]
        }
        client = MusicBrainzSearchClient(
            user_agent="SyncUpTest/0.1.0", http=make_http([json_response(body)])
        )
        start = time.monotonic()
        results = client.search_artists("radiohead", limit=5)
        elapsed = time.monotonic() - start

        assert elapsed >= 0.9  # at least 1 second from the 0.1 mark
        assert len(results) == 1
        assert results[0].name == "Radiohead"
        assert results[0].item_type == "artist"

    def test_search_returns_empty_for_blank_query(self) -> None:
        client = MusicBrainzSearchClient(user_agent="test")
        assert client.search_artists("   ", limit=5) == []


class TestOpenLibrarySearchClient:
    def test_search_books_returns_results(self) -> None:
        body = {
            "docs": [
                {
                    "key": "/works/OL12345W",
                    "title": "Blindsight",
                    "author_name": ["Peter Watts"],
                    "first_publish_year": 2006,
                }
            ]
        }
        client = OpenLibrarySearchClient(http=make_http([json_response(body)]))
        results = client.search_books("blindsight", limit=5)

        assert len(results) == 1
        assert results[0].name == "Blindsight"
        assert results[0].item_type == "book"
        assert results[0].external_id == "/works/OL12345W"
        assert results[0].extra.get("author") == "Peter Watts"

    def test_search_returns_empty_for_blank_query(self) -> None:
        client = OpenLibrarySearchClient()
        assert client.search_books("   ", limit=5) == []


class TestGoogleBooksSearchClient:
    def test_search_requires_api_key(self) -> None:
        client = GoogleBooksSearchClient(api_key="")
        assert client.search_books("dune", limit=5) == []

    def test_search_books_returns_results(self) -> None:
        body = {
            "items": [
                {
                    "id": "abc123",
                    "volumeInfo": {
                        "title": "Dune",
                        "authors": ["Frank Herbert"],
                        "publishedDate": "1965-08-01",
                    },
                }
            ]
        }
        client = GoogleBooksSearchClient(api_key="test-key", http=make_http([json_response(body)]))
        results = client.search_books("dune", limit=5)

        assert len(results) == 1
        assert results[0].name == "Dune"
        assert results[0].item_type == "book"
        assert results[0].external_id == "abc123"
        assert results[0].extra.get("author") == "Frank Herbert"
        assert results[0].extra.get("year") == 1965

    def test_search_returns_empty_for_blank_query(self) -> None:
        client = GoogleBooksSearchClient(api_key="test-key")
        assert client.search_books("   ", limit=5) == []
