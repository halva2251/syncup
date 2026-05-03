"""Verify that all retrofitted clients conform to the ServiceClient Protocol."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from syncup.ingest.lastfm import LastfmClient
from syncup.ingest.protocol import ServiceClient
from syncup.ingest.spotify import SpotifyClient
from syncup.ingest.steam import SteamClient

# ---------------------------------------------------------------------------
# HTTP mock helpers (same pattern as test_steam.py / test_lastfm.py)
# ---------------------------------------------------------------------------


class _SequenceTransport(httpx.BaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if not self._responses:
            raise RuntimeError("No more mock responses")
        return self._responses.pop(0)


def _json_response(body: dict, status_code: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(status_code, json=body)


def _steam_client(responses: list[httpx.Response]) -> SteamClient:
    http = httpx.Client(transport=_SequenceTransport(responses))
    return SteamClient(api_key="key", http=http)


def _lastfm_client(responses: list[httpx.Response]) -> LastfmClient:
    http = httpx.Client(transport=_SequenceTransport(responses))
    return LastfmClient(api_key="key", http=http)


# ---------------------------------------------------------------------------
# Protocol conformance (isinstance check)
# ---------------------------------------------------------------------------


def test_steam_client_conforms_to_protocol() -> None:
    client = SteamClient(api_key="key")
    assert isinstance(client, ServiceClient)


def test_lastfm_client_conforms_to_protocol() -> None:
    client = LastfmClient(api_key="key")
    assert isinstance(client, ServiceClient)


def test_spotify_client_conforms_to_protocol() -> None:
    client = SpotifyClient(client_id="id", redirect_uri="http://localhost/cb")
    assert isinstance(client, ServiceClient)


# ---------------------------------------------------------------------------
# service_name values
# ---------------------------------------------------------------------------


def test_steam_service_name() -> None:
    assert SteamClient.service_name == "steam"


def test_lastfm_service_name() -> None:
    assert LastfmClient.service_name == "lastfm"


def test_spotify_service_name() -> None:
    assert SpotifyClient.service_name == "spotify"


# ---------------------------------------------------------------------------
# refresh_token returns None for non-OAuth clients
# ---------------------------------------------------------------------------


def test_steam_refresh_token_returns_none() -> None:
    client = SteamClient(api_key="key")
    conn = MagicMock()
    assert client.refresh_token(conn) is None


def test_lastfm_refresh_token_returns_none() -> None:
    client = LastfmClient(api_key="key")
    conn = MagicMock()
    assert client.refresh_token(conn) is None


# ---------------------------------------------------------------------------
# fetch_items shape — SteamClient
# ---------------------------------------------------------------------------


def test_steam_fetch_items_returns_raw_items() -> None:
    conn = MagicMock()
    conn.external_user_id = "76561198000000001"
    client = _steam_client(
        [
            _json_response(
                {
                    "response": {
                        "games": [
                            {
                                "appid": 730,
                                "name": "Counter-Strike 2",
                                "playtime_forever": 3600,
                                "img_icon_url": "cs2.png",
                                "rtime_last_played": 0,
                            },
                            {
                                "appid": 570,
                                "name": "Dota 2",
                                "playtime_forever": 1800,
                                "img_icon_url": "dota.png",
                                "rtime_last_played": 0,
                            },
                        ]
                    }
                }
            )
        ]
    )
    items = client.fetch_items(conn)

    assert len(items) == 2
    cs2 = next(i for i in items if i["external_id"] == "730")
    assert cs2["item_type"] == "game"
    assert cs2["raw_type"] == "consumption"
    assert cs2["engagement_score"] == pytest.approx(1.0)
    assert cs2["raw_value"] == pytest.approx(3600.0)
    assert cs2["metadata"]["img_icon_url"] == "cs2.png"


def test_steam_fetch_items_empty_library() -> None:
    conn = MagicMock()
    conn.external_user_id = "76561198000000001"
    client = _steam_client([_json_response({"response": {}})])
    assert client.fetch_items(conn) == []


# ---------------------------------------------------------------------------
# fetch_items shape — LastfmClient
# ---------------------------------------------------------------------------


def test_lastfm_fetch_items_returns_raw_items() -> None:
    conn = MagicMock()
    conn.external_user_id = "halva"
    client = _lastfm_client(
        [
            _json_response(
                {
                    "topartists": {
                        "artist": [
                            {"name": "Arca", "playcount": "200", "mbid": "arca-mbid"},
                        ]
                    }
                }
            ),
            _json_response(
                {
                    "toptracks": {
                        "track": [
                            {
                                "name": "Anoche",
                                "playcount": "50",
                                "mbid": "anoche-mbid",
                                "artist": {"name": "Arca"},
                            }
                        ]
                    }
                }
            ),
        ]
    )
    items = client.fetch_items(conn)

    assert len(items) == 2
    artist = next(i for i in items if i["item_type"] == "artist")
    assert artist["name"] == "Arca"
    assert artist["raw_type"] == "consumption"
    assert artist["engagement_score"] == pytest.approx(1.0)

    track = next(i for i in items if i["item_type"] == "track")
    assert track["name"] == "Anoche"
    assert track["metadata"]["artist"] == "Arca"


# ---------------------------------------------------------------------------
# Spotify refresh_token: no refresh needed when token still valid
# ---------------------------------------------------------------------------


def test_spotify_refresh_token_returns_none_when_token_still_valid() -> None:
    from datetime import UTC, datetime, timedelta

    client = SpotifyClient(client_id="id", redirect_uri="http://localhost/cb")
    conn = MagicMock()
    conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    assert client.refresh_token(conn) is None


def test_spotify_refresh_token_returns_none_when_no_expiry() -> None:
    client = SpotifyClient(client_id="id", redirect_uri="http://localhost/cb")
    conn = MagicMock()
    conn.token_expires_at = None
    assert client.refresh_token(conn) is None
