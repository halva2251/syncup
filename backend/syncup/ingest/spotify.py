"""Spotify OAuth 2.0 + PKCE client and API fetchers."""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import httpx

from syncup.db.models import ServiceConnection
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"  # nosec B105
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
    service_name: ClassVar[str] = "spotify"

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

    def __exit__(self, *_: object) -> None:
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

    def fetch_me(self, access_token: str) -> dict:  # type: ignore[type-arg]
        """Return the current user's Spotify profile (includes ``id``)."""
        resp = self.http.get(
            f"{_API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # ServiceClient Protocol implementation
    # ------------------------------------------------------------------

    _TOKEN_REFRESH_BUFFER: ClassVar[timedelta] = timedelta(seconds=60)

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch top artists and recently played tracks for the connected account."""
        from syncup.ingest.crypto import decrypt_token

        token_bytes: bytes | None = connection.access_token_encrypted
        if token_bytes is None:
            raise SyncClientError("Missing access token — reconnect Spotify via OAuth")
        access_token = decrypt_token(token_bytes)

        top_artists = self.fetch_top_artists(
            access_token, limit=50, time_range="medium_term"
        )
        recently_played = self.fetch_recently_played(access_token, limit=50)

        result: list[RawItem] = []
        n_artists = len(top_artists)
        for i, artist in enumerate(top_artists):
            result.append(
                RawItem(
                    external_id=artist["id"],
                    name=artist["name"],
                    item_type="artist",
                    engagement_score=(n_artists - i) / n_artists if n_artists else 0.0,
                    raw_value=float(n_artists - i),
                    raw_type="consumption",
                    metadata={"genres": artist.get("genres", [])},
                    last_engaged_at=None,
                )
            )

        track_occurrences: dict[str, dict] = {}  # type: ignore[type-arg]
        for event in recently_played:
            track = event["track"]
            tid = track["id"]
            if tid not in track_occurrences:
                track_occurrences[tid] = {
                    "name": track["name"],
                    "artists": [a["name"] for a in track.get("artists", [])],
                    "count": 0,
                    "played_at": event.get("played_at"),
                }
            track_occurrences[tid]["count"] += 1

        max_count = max((info["count"] for info in track_occurrences.values()), default=1) or 1
        for tid, info in track_occurrences.items():
            last_at: datetime | None = None
            if info["played_at"]:
                try:
                    last_at = datetime.fromisoformat(info["played_at"])
                except (ValueError, TypeError):
                    pass
            result.append(
                RawItem(
                    external_id=tid,
                    name=info["name"],
                    item_type="track",
                    engagement_score=info["count"] / max_count,
                    raw_value=float(info["count"]),
                    raw_type="consumption",
                    metadata={"artists": info["artists"]},
                    last_engaged_at=last_at,
                )
            )

        return result

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """Refresh the Spotify access token if it is expired or within the buffer window.

        Returns None if the token is still valid; returns a TokenPair if a new
        token was obtained. The caller is responsible for persisting the new tokens.
        """
        from syncup.ingest.crypto import decrypt_token

        expires_at: datetime | None = connection.token_expires_at
        now = datetime.now(UTC)

        if expires_at is None or expires_at > now + self._TOKEN_REFRESH_BUFFER:
            return None

        refresh_bytes: bytes | None = connection.refresh_token_encrypted
        if refresh_bytes is None:
            raise SyncClientError("Missing refresh token — reconnect Spotify via OAuth")

        old_refresh = decrypt_token(refresh_bytes)
        new_tokens = self.refresh_access_token(old_refresh)
        return TokenPair(
            access_token=new_tokens.access_token,
            refresh_token=new_tokens.refresh_token,
            expires_at=now + timedelta(seconds=new_tokens.expires_in),
        )
