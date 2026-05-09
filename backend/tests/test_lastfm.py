"""Tests for the Last.fm API client."""
from __future__ import annotations

import httpx
import pytest

from syncup.ingest.lastfm import LastfmClient
from syncup.ingest.protocol import SyncClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _client(responses: list[httpx.Response]) -> LastfmClient:
    """Return a LastfmClient backed by a sequence of canned responses."""
    transport = _SequenceTransport(responses)
    http = httpx.Client(transport=transport)
    return LastfmClient(api_key="test-api-key", http=http)


def _json_response(body: dict, status_code: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(status_code, json=body)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MBID_RH = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
_MBID_PH = "8f6bd1e4-fbe1-4f50-aa9b-94c450ec0f11"

_TOP_ARTISTS_BODY = {
    "topartists": {
        "artist": [
            {"name": "Radiohead", "playcount": "1234", "mbid": _MBID_RH},
            {"name": "Portishead", "playcount": "567", "mbid": _MBID_PH},
        ]
    }
}

_TOP_TRACKS_BODY = {
    "toptracks": {
        "track": [
            {"name": "Karma Police", "playcount": "99", "mbid": ""},
            {"name": "Glory Box", "playcount": "88", "mbid": "some-mbid"},
        ]
    }
}


# ---------------------------------------------------------------------------
# get_top_artists
# ---------------------------------------------------------------------------


def test_get_top_artists_returns_list_of_dicts() -> None:
    c = _client([_json_response(_TOP_ARTISTS_BODY)])
    artists = c.get_top_artists("rj")
    assert isinstance(artists, list)
    assert len(artists) == 2
    assert artists[0]["name"] == "Radiohead"
    assert artists[0]["playcount"] == "1234"
    assert "mbid" in artists[0]


def test_get_top_artists_raises_on_invalid_period() -> None:
    c = _client([])
    with pytest.raises(SyncClientError, match="period"):
        c.get_top_artists("rj", period="badperiod")


def test_get_top_artists_raises_on_limit_zero() -> None:
    c = _client([])
    with pytest.raises(SyncClientError, match="limit"):
        c.get_top_artists("rj", limit=0)


def test_get_top_artists_raises_on_limit_over_max() -> None:
    c = _client([])
    with pytest.raises(SyncClientError, match="limit"):
        c.get_top_artists("rj", limit=1001)


def test_get_top_artists_raises_on_lastfm_error_envelope() -> None:
    error_body = {"error": 6, "message": "User not found"}
    c = _client([_json_response(error_body)])
    with pytest.raises(SyncClientError, match="Last.fm API error 6"):
        c.get_top_artists("nonexistent_user_xyz")


def test_get_top_artists_raises_on_empty_username() -> None:
    c = _client([])
    with pytest.raises(SyncClientError, match="username"):
        c.get_top_artists("")


# ---------------------------------------------------------------------------
# get_top_tracks
# ---------------------------------------------------------------------------


def test_get_top_tracks_returns_list_of_dicts() -> None:
    c = _client([_json_response(_TOP_TRACKS_BODY)])
    tracks = c.get_top_tracks("rj")
    assert isinstance(tracks, list)
    assert len(tracks) == 2
    assert tracks[0]["name"] == "Karma Police"


def test_get_top_tracks_raises_on_5xx() -> None:
    c = _client([httpx.Response(503, text="Service Unavailable")])
    with pytest.raises(httpx.HTTPStatusError):
        c.get_top_tracks("rj")


# ---------------------------------------------------------------------------
# I5 — validators reachable from fetch_items must raise SyncClientError
# ---------------------------------------------------------------------------


def test_invalid_period_raises_sync_client_error_not_value_error() -> None:
    """_validate_period must raise SyncClientError so the sync task handles it correctly."""
    c = _client([])
    with pytest.raises(SyncClientError):
        c.get_top_artists("rj", period="badperiod")


def test_invalid_limit_raises_sync_client_error_not_value_error() -> None:
    """_validate_limit must raise SyncClientError so the sync task handles it correctly."""
    c = _client([])
    with pytest.raises(SyncClientError):
        c.get_top_artists("rj", limit=0)


# ---------------------------------------------------------------------------
# I6 — Last.fm external_id fallback must use normalize_title, not raw name
# ---------------------------------------------------------------------------


def test_fetch_items_artist_external_id_falls_back_to_normalized_name() -> None:
    """When MBID is absent, external_id must use normalize_title(name), not raw name."""
    artist_no_mbid = {"name": "Sigur Rós", "playcount": "100", "mbid": ""}
    artists_body = {"topartists": {"artist": [artist_no_mbid]}}
    tracks_body = {"toptracks": {"track": []}}
    c = _client([_json_response(artists_body), _json_response(tracks_body)])

    from unittest.mock import MagicMock

    conn = MagicMock()
    conn.external_user_id = "rj"
    items = c.fetch_items(conn)

    assert len(items) == 1
    assert items[0]["external_id"] == "sigur ros", (
        f"external_id should be normalized name, got {items[0]['external_id']!r}"
    )
