"""Tests for TraktClient — REST OAuth client, Protocol conformance, fetch_items."""
from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest

from syncup.ingest.protocol import ServiceClient, SyncClientError


# ---------------------------------------------------------------------------
# httpx mock transport helpers
# ---------------------------------------------------------------------------


class _SequenceTransport(httpx.BaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self._index = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._index >= len(self._responses):
            raise RuntimeError(f"No more mock responses (index={self._index})")
        resp = self._responses[self._index]
        self._index += 1
        return resp


def _json_resp(body: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


def _client(responses: list[httpx.Response]):  # type: ignore[return]
    from syncup.ingest.trakt import TraktClient

    transport = _SequenceTransport(responses)
    http = httpx.Client(transport=transport)
    return TraktClient(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://127.0.0.1:3000/api/connect/trakt/oauth/callback",
        http=http,
    )


def _make_connection(
    access_token_bytes: bytes | None = b"fake-encrypted-token",
    refresh_token_bytes: bytes | None = b"fake-encrypted-refresh",
) -> MagicMock:
    conn = MagicMock()
    conn.access_token_encrypted = access_token_bytes
    conn.refresh_token_encrypted = refresh_token_bytes
    conn.external_user_id = "testuser"
    return conn


# ---------------------------------------------------------------------------
# Canned API responses
# ---------------------------------------------------------------------------

_TOKEN_BODY = {
    "access_token": "trakt-access-token",
    "token_type": "Bearer",
    "expires_in": 7776000,
    "refresh_token": "trakt-refresh-token",
    "scope": "public",
    "created_at": 1700000000,
}

_ME_BODY = {
    "username": "halva",
    "private": False,
    "name": "Halva",
    "ids": {"slug": "halva", "uuid": "abc-123"},
}

_MOVIES_BODY = [
    {
        "plays": 3,
        "last_watched_at": "2024-01-15T10:30:00.000Z",
        "last_updated_at": "2024-01-15T10:30:00.000Z",
        "movie": {
            "title": "The Dark Knight",
            "year": 2008,
            "ids": {"trakt": 16, "slug": "the-dark-knight-2008", "imdb": "tt0468569", "tmdb": 155},
        },
    },
    {
        "plays": 1,
        "last_watched_at": "2024-02-01T00:00:00.000Z",
        "last_updated_at": "2024-02-01T00:00:00.000Z",
        "movie": {
            "title": "Blade Runner 2049",
            "year": 2017,
            "ids": {"trakt": 235, "slug": "blade-runner-2049-2017", "imdb": "tt1856101", "tmdb": 335984},
        },
    },
]

_SHOWS_BODY = [
    {
        "plays": 62,
        "last_watched_at": "2024-03-01T00:00:00.000Z",
        "last_updated_at": "2024-03-01T00:00:00.000Z",
        "show": {
            "title": "Breaking Bad",
            "year": 2008,
            "ids": {"trakt": 1, "slug": "breaking-bad", "tvdb": 81189, "imdb": "tt0903747"},
        },
        "seasons": [],
    },
    {
        "plays": 31,
        "last_watched_at": "2024-04-01T00:00:00.000Z",
        "last_updated_at": "2024-04-01T00:00:00.000Z",
        "show": {
            "title": "Severance",
            "year": 2022,
            "ids": {"trakt": 152374, "slug": "severance", "tvdb": 400782, "imdb": "tt11280740"},
        },
        "seasons": [],
    },
]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_trakt_client_conforms_to_protocol() -> None:
    from syncup.ingest.trakt import TraktClient

    assert isinstance(
        TraktClient(
            client_id="x",
            client_secret="y",
            redirect_uri="http://localhost/callback",
        ),
        ServiceClient,
    )


def test_trakt_service_name() -> None:
    from syncup.ingest.trakt import TraktClient

    assert TraktClient.service_name == "trakt"


# ---------------------------------------------------------------------------
# get_authorize_url
# ---------------------------------------------------------------------------


def test_get_authorize_url_contains_client_id() -> None:
    from syncup.ingest.trakt import TraktClient

    url = TraktClient(
        client_id="my-client-id", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="abc123")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["client_id"] == "my-client-id"


def test_get_authorize_url_contains_redirect_uri() -> None:
    from syncup.ingest.trakt import TraktClient

    redirect = "http://127.0.0.1:3000/api/connect/trakt/oauth/callback"
    url = TraktClient(
        client_id="x", client_secret="s", redirect_uri=redirect
    ).get_authorize_url(state="xyz")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["redirect_uri"] == redirect


def test_get_authorize_url_contains_state() -> None:
    from syncup.ingest.trakt import TraktClient

    url = TraktClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="random-state-xyz")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["state"] == "random-state-xyz"


def test_get_authorize_url_points_to_trakt() -> None:
    from syncup.ingest.trakt import TraktClient

    url = TraktClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="s")
    assert "trakt.tv" in url


def test_get_authorize_url_response_type_code() -> None:
    from syncup.ingest.trakt import TraktClient

    url = TraktClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="s")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["response_type"] == "code"


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


def test_exchange_code_returns_token_pair() -> None:
    client = _client([_json_resp(_TOKEN_BODY)])

    from syncup.ingest.protocol import TokenPair

    result = client.exchange_code("some-code")
    assert isinstance(result, TokenPair)
    assert result.access_token == "trakt-access-token"
    assert result.refresh_token == "trakt-refresh-token"


def test_exchange_code_sets_expires_at() -> None:
    client = _client([_json_resp(_TOKEN_BODY)])
    result = client.exchange_code("some-code")
    # Trakt tokens expire; expires_at must not be None.
    assert result.expires_at is not None


def test_exchange_code_raises_on_http_error() -> None:
    client = _client([_json_resp({"error": "bad"}, status=400)])
    with pytest.raises(SyncClientError, match="Trakt token exchange failed"):
        client.exchange_code("bad-code")


def test_exchange_code_raises_on_request_error() -> None:
    from syncup.ingest.trakt import TraktClient

    class _FailTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no network")

    http = httpx.Client(transport=_FailTransport())
    client = TraktClient(
        client_id="x", client_secret="y", redirect_uri="z", http=http
    )
    with pytest.raises(SyncClientError, match="Could not reach Trakt"):
        client.exchange_code("code")


# ---------------------------------------------------------------------------
# fetch_me
# ---------------------------------------------------------------------------


def test_fetch_me_returns_username() -> None:
    client = _client([_json_resp(_ME_BODY)])
    result = client.fetch_me("access-token")
    assert result["username"] == "halva"


def test_fetch_me_raises_on_http_error() -> None:
    client = _client([_json_resp({"error": "unauthorized"}, status=401)])
    with pytest.raises(SyncClientError):
        client.fetch_me("bad-token")


def test_fetch_me_raises_on_request_error() -> None:
    from syncup.ingest.trakt import TraktClient

    class _FailTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no network")

    http = httpx.Client(transport=_FailTransport())
    client = TraktClient(client_id="x", client_secret="y", redirect_uri="z", http=http)
    with pytest.raises(SyncClientError, match="Could not reach Trakt"):
        client.fetch_me("token")


# ---------------------------------------------------------------------------
# fetch_items
# ---------------------------------------------------------------------------


def test_fetch_items_returns_movies_and_shows(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())

    film_items = [i for i in items if i["item_type"] == "film"]
    show_items = [i for i in items if i["item_type"] == "show"]
    assert len(film_items) == 2
    assert len(show_items) == 2


def test_fetch_items_film_name_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    film_names = {i["name"] for i in items if i["item_type"] == "film"}
    assert "The Dark Knight" in film_names
    assert "Blade Runner 2049" in film_names


def test_fetch_items_show_name_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    show_names = {i["name"] for i in items if i["item_type"] == "show"}
    assert "Breaking Bad" in show_names
    assert "Severance" in show_names


def test_fetch_items_raw_type_is_consumption(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert all(i["raw_type"] == "consumption" for i in items)


def test_fetch_items_film_raw_value_is_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    dark_knight = next(i for i in items if i["name"] == "The Dark Knight")
    assert dark_knight["raw_value"] == 3


def test_fetch_items_show_raw_value_is_episodes_watched(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    breaking_bad = next(i for i in items if i["name"] == "Breaking Bad")
    assert breaking_bad["raw_value"] == 62


def test_fetch_items_engagement_score_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most-watched item in each type should have engagement_score == 1.0."""
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())

    dark_knight = next(i for i in items if i["name"] == "The Dark Knight")
    blade_runner = next(i for i in items if i["name"] == "Blade Runner 2049")
    assert dark_knight["engagement_score"] == pytest.approx(1.0)
    assert blade_runner["engagement_score"] == pytest.approx(1 / 3)

    breaking_bad = next(i for i in items if i["name"] == "Breaking Bad")
    severance = next(i for i in items if i["name"] == "Severance")
    assert breaking_bad["engagement_score"] == pytest.approx(1.0)
    assert severance["engagement_score"] == pytest.approx(31 / 62)


def test_fetch_items_engagement_score_within_range(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    for item in items:
        assert 0.0 <= item["engagement_score"] <= 1.0


def test_fetch_items_metadata_has_title_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    for item in items:
        assert "title_normalized" in item["metadata"]
        assert isinstance(item["metadata"]["title_normalized"], str)


def test_fetch_items_metadata_has_release_year(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    dark_knight = next(i for i in items if i["name"] == "The Dark Knight")
    assert dark_knight["metadata"]["release_year"] == 2008


def test_fetch_items_external_id_is_trakt_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    dark_knight = next(i for i in items if i["name"] == "The Dark Knight")
    assert dark_knight["external_id"] == "16"


def test_fetch_items_skips_zero_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    movies_with_zero = [
        *_MOVIES_BODY,
        {
            "plays": 0,
            "last_watched_at": None,
            "last_updated_at": None,
            "movie": {
                "title": "Unplayed Movie",
                "year": 2020,
                "ids": {"trakt": 999, "slug": "unplayed-movie-2020"},
            },
        },
    ]
    client = _client([_json_resp(movies_with_zero), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert all(i["name"] != "Unplayed Movie" for i in items)


def test_fetch_items_empty_watched_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp([]), _json_resp([])])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items == []


def test_fetch_items_raises_on_missing_token() -> None:
    from syncup.ingest.trakt import TraktClient

    client = TraktClient(client_id="x", client_secret="y", redirect_uri="z")
    with pytest.raises(SyncClientError, match="Missing access token"):
        client.fetch_items(_make_connection(access_token_bytes=None))


def test_fetch_items_raises_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp({"error": "unauthorized"}, status=401)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    with pytest.raises(SyncClientError, match="reconnect"):
        client.fetch_items(_make_connection())


def test_fetch_items_raises_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from syncup.ingest.trakt import TraktClient

    class _FailTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no network")

    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")
    http = httpx.Client(transport=_FailTransport())
    client = TraktClient(client_id="x", client_secret="y", redirect_uri="z", http=http)

    with pytest.raises(SyncClientError, match="Could not reach Trakt"):
        client.fetch_items(_make_connection())


def test_fetch_items_last_watched_at_set(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_MOVIES_BODY), _json_resp(_SHOWS_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    dark_knight = next(i for i in items if i["name"] == "The Dark Knight")
    assert dark_knight["last_engaged_at"] is not None
    assert isinstance(dark_knight["last_engaged_at"], datetime)


def test_fetch_items_single_movie_score_is_1(monkeypatch: pytest.MonkeyPatch) -> None:
    single_movie = [_MOVIES_BODY[0]]
    client = _client([_json_resp(single_movie), _json_resp([])])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert len(items) == 1
    assert items[0]["engagement_score"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# refresh_token
# ---------------------------------------------------------------------------


def test_refresh_token_returns_new_token_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_TOKEN_BODY)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "refresh-token")

    from syncup.ingest.protocol import TokenPair

    result = client.refresh_token(_make_connection())
    assert isinstance(result, TokenPair)
    assert result.access_token == "trakt-access-token"
    assert result.refresh_token == "trakt-refresh-token"
    assert result.expires_at is not None


def test_refresh_token_raises_on_missing_refresh_token() -> None:
    from syncup.ingest.trakt import TraktClient

    client = TraktClient(client_id="x", client_secret="y", redirect_uri="z")
    with pytest.raises(SyncClientError, match="Missing refresh token"):
        client.refresh_token(_make_connection(refresh_token_bytes=None))


def test_refresh_token_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp({"error": "invalid_grant"}, status=400)])
    monkeypatch.setattr("syncup.ingest.trakt.decrypt_token", lambda _: "refresh-token")

    with pytest.raises(SyncClientError, match="Trakt token refresh failed"):
        client.refresh_token(_make_connection())


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager_closes_http() -> None:
    from syncup.ingest.trakt import TraktClient

    http = MagicMock()
    http.close = MagicMock()
    client = TraktClient(client_id="x", client_secret="y", redirect_uri="z", http=http)
    with client:
        pass
    http.close.assert_called_once()
