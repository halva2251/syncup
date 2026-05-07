"""Tests for Steam API client using httpx mock transport."""
from __future__ import annotations

import httpx
import pytest

from syncup.ingest.protocol import SyncClientError
from syncup.ingest.steam import SteamClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(responses: list[httpx.Response]) -> SteamClient:
    """Return a SteamClient backed by a sequence of canned responses."""
    transport = _SequenceTransport(responses)
    http = httpx.Client(transport=transport)
    return SteamClient(api_key="test-api-key", http=http)


class _SequenceTransport(httpx.BaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self._index = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._index >= len(self._responses):
            raise RuntimeError("No more mock responses")
        resp = self._responses[self._index]
        self._index += 1
        return resp


def _json_response(body: dict, status_code: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(status_code, json=body)


# ---------------------------------------------------------------------------
# resolve_vanity_url
# ---------------------------------------------------------------------------

_VANITY_SUCCESS_BODY = {
    "response": {
        "steamid": "76561198000000001",
        "success": 1,
    }
}

_VANITY_NOT_FOUND_BODY = {
    "response": {
        "success": 42,
        "message": "No match",
    }
}


def test_resolve_vanity_url_returns_steam_id() -> None:
    c = _client([_json_response(_VANITY_SUCCESS_BODY)])
    steam_id = c.resolve_vanity_url("myvanity")
    assert steam_id == "76561198000000001"


def test_resolve_vanity_url_raises_sync_client_error_when_not_found() -> None:
    c = _client([_json_response(_VANITY_NOT_FOUND_BODY)])
    with pytest.raises(SyncClientError, match="not found"):
        c.resolve_vanity_url("unknownvanity")


# ---------------------------------------------------------------------------
# get_owned_games
# ---------------------------------------------------------------------------

_OWNED_GAMES_BODY = {
    "response": {
        "game_count": 2,
        "games": [
            {"appid": 730, "name": "Counter-Strike 2", "playtime_forever": 1200},
            {"appid": 570, "name": "Dota 2", "playtime_forever": 5400},
        ],
    }
}


def test_get_owned_games_returns_game_list() -> None:
    c = _client([_json_response(_OWNED_GAMES_BODY)])
    games = c.get_owned_games("76561198000000001")
    assert len(games) == 2
    assert games[0]["appid"] == 730
    assert games[0]["name"] == "Counter-Strike 2"
    assert games[0]["playtime_forever"] == 1200


def test_get_owned_games_raises_on_4xx() -> None:
    c = _client([httpx.Response(403, json={"error": "Forbidden"})])
    with pytest.raises(httpx.HTTPStatusError):
        c.get_owned_games("76561198000000001")


# ---------------------------------------------------------------------------
# get_player_summary
# ---------------------------------------------------------------------------

_PLAYER_SUMMARY_BODY = {
    "response": {
        "players": [
            {
                "steamid": "76561198000000001",
                "personaname": "GabeN",
                "avatarfull": "https://avatars.steamstatic.com/full.jpg",
                "profileurl": "https://steamcommunity.com/id/gaben/",
            }
        ]
    }
}


def test_get_player_summary_returns_player_dict() -> None:
    c = _client([_json_response(_PLAYER_SUMMARY_BODY)])
    player = c.get_player_summary("76561198000000001")
    assert player["personaname"] == "GabeN"
    assert player["steamid"] == "76561198000000001"


def test_get_player_summary_raises_sync_client_error_on_empty_steam_id() -> None:
    c = _client([])
    with pytest.raises(SyncClientError, match="steam_id"):
        c.get_player_summary("")


def test_get_player_summary_raises_on_5xx() -> None:
    c = _client([httpx.Response(503, text="Service Unavailable")])
    with pytest.raises(httpx.HTTPStatusError):
        c.get_player_summary("76561198000000001")
