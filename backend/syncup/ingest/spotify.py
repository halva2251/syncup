"""Spotify OAuth 2.0 + PKCE client and API fetchers."""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from dataclasses import dataclass, field
from types import TracebackType

import httpx

_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_BASE = "https://api.spotify.com/v1"

SCOPES = ["user-top-read", "user-library-read", "user-read-recently-played"]
_MAX_LIMIT = 50


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


@dataclass
class SpotifyClient:
    client_id: str
    redirect_uri: str
    # Not required for PKCE; kept for future flows that need it (e.g. client credentials).
    client_secret: str | None = None
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(10.0)), repr=False
    )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> SpotifyClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def generate_pkce_pair(self) -> tuple[str, str]:
        """Return (code_verifier, code_challenge) for a PKCE flow."""
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    def get_authorize_url(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(SCOPES),
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str) -> TokenResponse:
        resp = self.http.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        return TokenResponse(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=body["expires_in"],
            token_type=body["token_type"],
        )

    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        resp = self.http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        return TokenResponse(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", refresh_token),
            expires_in=body["expires_in"],
            token_type=body["token_type"],
        )

    _VALID_TIME_RANGES = frozenset({"short_term", "medium_term", "long_term"})

    def fetch_top_artists(
        self,
        access_token: str,
        limit: int = 50,
        time_range: str = "medium_term",
    ) -> list[dict]:  # type: ignore[type-arg]
        if not 1 <= limit <= _MAX_LIMIT:
            raise ValueError(f"limit must be 1–{_MAX_LIMIT}, got {limit}")
        if time_range not in self._VALID_TIME_RANGES:
            valid = sorted(self._VALID_TIME_RANGES)
            raise ValueError(f"time_range must be one of {valid}, got {time_range!r}")
        resp = self.http.get(
            f"{_API_BASE}/me/top/artists",
            params={"limit": limit, "time_range": time_range},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()["items"]  # type: ignore[no-any-return]

    def fetch_recently_played(self, access_token: str, limit: int = 50) -> list[dict]:  # type: ignore[type-arg]
        if not 1 <= limit <= _MAX_LIMIT:
            raise ValueError(f"limit must be 1–{_MAX_LIMIT}, got {limit}")
        resp = self.http.get(
            f"{_API_BASE}/me/player/recently-played",
            params={"limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()["items"]  # type: ignore[no-any-return]
