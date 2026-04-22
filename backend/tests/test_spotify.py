"""Tests for Spotify OAuth client using httpx mock transport."""
from __future__ import annotations

import base64
import hashlib
import urllib.parse

import httpx
import pytest

from syncup.ingest.spotify import SCOPES, SpotifyClient, TokenResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client(responses: list[httpx.Response]) -> SpotifyClient:
    """Return a SpotifyClient backed by a sequence of canned responses."""
    transport = _SequenceTransport(responses)
    http = httpx.Client(transport=transport)
    return SpotifyClient(
        client_id="test-client-id",
        redirect_uri="http://127.0.0.1:3000/api/auth/spotify/callback",
        http=http,
    )


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
# PKCE helpers
# ---------------------------------------------------------------------------

def test_generate_pkce_pair_lengths() -> None:
    c = _client([])
    verifier, challenge = c.generate_pkce_pair()
    # verifier: 32 random bytes → 43 base64url chars (no padding)
    assert len(verifier) == 43
    # challenge: sha256 → 32 bytes → 43 base64url chars
    assert len(challenge) == 43


def test_generate_pkce_pair_unique() -> None:
    c = _client([])
    v1, _ = c.generate_pkce_pair()
    v2, _ = c.generate_pkce_pair()
    assert v1 != v2


def test_pkce_challenge_is_sha256_of_verifier() -> None:
    c = _client([])
    verifier, challenge = c.generate_pkce_pair()
    digest = hashlib.sha256(verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert challenge == expected


# ---------------------------------------------------------------------------
# get_authorize_url
# ---------------------------------------------------------------------------

def test_authorize_url_base() -> None:
    c = _client([])
    url = c.get_authorize_url(state="xyz", code_challenge="ch")
    assert url.startswith("https://accounts.spotify.com/authorize?")


def test_authorize_url_required_params() -> None:
    c = _client([])
    url = c.get_authorize_url(state="xyz", code_challenge="ch")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))

    assert params["client_id"] == "test-client-id"
    assert params["response_type"] == "code"
    assert params["redirect_uri"] == "http://127.0.0.1:3000/api/auth/spotify/callback"
    assert params["state"] == "xyz"
    assert params["code_challenge"] == "ch"
    assert params["code_challenge_method"] == "S256"


def test_authorize_url_contains_all_scopes() -> None:
    c = _client([])
    url = c.get_authorize_url(state="s", code_challenge="c")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    granted = set(params["scope"].split())
    assert granted == set(SCOPES)


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------

_TOKEN_BODY = {
    "access_token": "acc-tok",
    "refresh_token": "ref-tok",
    "expires_in": 3600,
    "token_type": "Bearer",
}


def test_exchange_code_returns_token_response() -> None:
    c = _client([_json_response(_TOKEN_BODY)])
    result = c.exchange_code(code="auth-code", code_verifier="verifier")
    assert isinstance(result, TokenResponse)
    assert result.access_token == "acc-tok"
    assert result.refresh_token == "ref-tok"
    assert result.expires_in == 3600


def test_exchange_code_raises_on_4xx() -> None:
    c = _client([httpx.Response(400, json={"error": "invalid_grant"})])
    with pytest.raises(httpx.HTTPStatusError):
        c.exchange_code(code="bad", code_verifier="v")


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------

def test_refresh_returns_new_access_token() -> None:
    body = {**_TOKEN_BODY, "access_token": "new-acc-tok", "refresh_token": "new-ref-tok"}
    c = _client([_json_response(body)])
    result = c.refresh_access_token("old-ref-tok")
    assert result.access_token == "new-acc-tok"
    assert result.refresh_token == "new-ref-tok"


def test_refresh_keeps_old_refresh_token_when_not_rotated() -> None:
    body = {**_TOKEN_BODY, "access_token": "new-acc"}
    body.pop("refresh_token")
    c = _client([_json_response(body)])
    result = c.refresh_access_token("stable-ref-tok")
    assert result.refresh_token == "stable-ref-tok"


# ---------------------------------------------------------------------------
# fetch_top_artists
# ---------------------------------------------------------------------------

_ARTISTS_BODY = {
    "items": [
        {"id": "a1", "name": "Radiohead", "genres": ["art rock"]},
        {"id": "a2", "name": "Portishead", "genres": ["trip hop"]},
    ]
}


def test_fetch_top_artists_returns_items() -> None:
    c = _client([_json_response(_ARTISTS_BODY)])
    artists = c.fetch_top_artists("tok")
    assert len(artists) == 2
    assert artists[0]["name"] == "Radiohead"


def test_fetch_top_artists_custom_time_range() -> None:
    c = _client([_json_response(_ARTISTS_BODY)])
    artists = c.fetch_top_artists("tok", time_range="long_term")
    assert len(artists) == 2


def test_fetch_top_artists_invalid_limit_raises() -> None:
    c = _client([])
    with pytest.raises(ValueError, match="limit"):
        c.fetch_top_artists("tok", limit=0)


def test_fetch_top_artists_invalid_time_range_raises() -> None:
    c = _client([])
    with pytest.raises(ValueError, match="time_range"):
        c.fetch_top_artists("tok", time_range="bad_value")


def test_fetch_top_artists_raises_on_401() -> None:
    c = _client([httpx.Response(401, json={"error": {"status": 401, "message": "Unauthorized"}})])
    with pytest.raises(httpx.HTTPStatusError):
        c.fetch_top_artists("bad-tok")


# ---------------------------------------------------------------------------
# fetch_recently_played
# ---------------------------------------------------------------------------

_RECENT_BODY = {
    "items": [
        {"track": {"id": "t1", "name": "Karma Police"}, "played_at": "2026-04-21T20:00:00Z"},
        {"track": {"id": "t2", "name": "Glory Box"}, "played_at": "2026-04-21T19:00:00Z"},
    ]
}


def test_fetch_recently_played_returns_items() -> None:
    c = _client([_json_response(_RECENT_BODY)])
    tracks = c.fetch_recently_played("tok")
    assert len(tracks) == 2
    assert tracks[0]["track"]["name"] == "Karma Police"


def test_fetch_recently_played_invalid_limit_raises() -> None:
    c = _client([])
    with pytest.raises(ValueError, match="limit"):
        c.fetch_recently_played("tok", limit=51)


def test_fetch_recently_played_raises_on_5xx() -> None:
    c = _client([httpx.Response(503, text="Service Unavailable")])
    with pytest.raises(httpx.HTTPStatusError):
        c.fetch_recently_played("tok")


# ---------------------------------------------------------------------------
# context manager
# ---------------------------------------------------------------------------

def test_context_manager_closes_client() -> None:
    with _client([]) as c:
        assert isinstance(c, SpotifyClient)
