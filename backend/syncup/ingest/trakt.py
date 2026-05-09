"""Trakt.tv REST OAuth client."""
from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, cast

import httpx

logger = logging.getLogger(__name__)

from syncup.ingest._text import normalize_title
from syncup.ingest.crypto import decrypt_token
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

if TYPE_CHECKING:
    from syncup.db.models import ServiceConnection

_AUTHORIZE_URL = "https://trakt.tv/oauth/authorize"
_TOKEN_URL = "https://api.trakt.tv/oauth/token"  # nosec B105
_API_BASE = "https://api.trakt.tv"

# Trakt tokens expire in 90 days (7 776 000 seconds).
# Trakt tokens expire in 90 days per https://trakt.docs.apiary.io/#reference/authentication-oauth
_TOKEN_LIFETIME_SECONDS = 7_776_000  # 90 * 24 * 60 * 60


@dataclass
class TraktClient:
    """ServiceClient for Trakt.tv — REST OAuth 2.0.

    Fetches watched movies and shows from the authenticated user's account.
    Tokens expire every 90 days; refresh_token exchanges the refresh token.
    """

    service_name: ClassVar[str] = "trakt"

    client_id: str
    client_secret: str
    redirect_uri: str
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(15.0)), repr=False
    )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> TraktClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _trakt_headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id,
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _token_expires_at(self, expires_in: int | None) -> datetime:
        seconds = expires_in if expires_in is not None else _TOKEN_LIFETIME_SECONDS
        return datetime.now(UTC) + timedelta(seconds=seconds)

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def get_authorize_url(self, state: str) -> str:
        """Return the Trakt authorization URL for the OAuth flow."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> TokenPair:
        """Exchange an authorization code for an access + refresh token.

        Raises SyncClientError on HTTP or network error.
        """
        try:
            resp = self.http.post(
                _TOKEN_URL,
                json={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers=self._trakt_headers(),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Trakt token exchange failed (status=%s): %s", exc.response.status_code, exc.response.text)
            raise SyncClientError("Trakt token exchange failed — please reconnect") from exc
        except httpx.RequestError as exc:
            logger.warning("Trakt token exchange network error: %s", exc)
            raise SyncClientError("Could not reach Trakt — please retry") from exc

        try:
            data = resp.json()
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=self._token_expires_at(data.get("expires_in")),
            )
        except (ValueError, KeyError) as exc:
            raise SyncClientError(
                "Trakt returned an invalid token response — please retry"
            ) from exc

    def fetch_me(self, access_token: str) -> dict[str, Any]:
        """Return the authenticated user's profile dict (contains at least 'username').

        Used during the OAuth callback to store the real Trakt username.
        Raises SyncClientError on failure.
        """
        try:
            resp = self.http.get(
                f"{_API_BASE}/users/me",
                headers=self._trakt_headers(access_token),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Trakt profile fetch failed (status=%s): %s", exc.response.status_code, exc.response.text)
            raise SyncClientError("Trakt profile fetch failed — please reconnect") from exc
        except httpx.RequestError as exc:
            logger.warning("Trakt profile fetch network error: %s", exc)
            raise SyncClientError("Could not reach Trakt — please retry") from exc
        try:
            return cast(dict[str, Any], resp.json())
        except ValueError as exc:
            raise SyncClientError(
                "Trakt returned an invalid profile response — please retry"
            ) from exc

    # ------------------------------------------------------------------
    # ServiceClient protocol
    # ------------------------------------------------------------------

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch the authenticated user's watched movies and shows.

        Normalizes engagement_score within each type (films and shows separately).
        Skips entries with plays == 0.
        Raises SyncClientError for expected failures.
        """
        token_bytes: bytes | None = connection.access_token_encrypted
        if token_bytes is None:
            raise SyncClientError("Missing access token — reconnect Trakt via OAuth")
        access_token = decrypt_token(token_bytes)

        movies = self._fetch_watched(access_token, "movies")
        shows = self._fetch_watched(access_token, "shows")

        film_items = self._parse_movies(movies)
        show_items = self._parse_shows(shows)
        return film_items + show_items

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """Exchange the stored refresh token for a fresh access token.

        Returns None if the token is still valid (expires more than 5 minutes from now).
        Raises SyncClientError on failure.
        """
        expires_at = connection.token_expires_at
        if expires_at is not None and expires_at > datetime.now(UTC) + timedelta(minutes=5):
            return None

        refresh_bytes: bytes | None = connection.refresh_token_encrypted
        if refresh_bytes is None:
            raise SyncClientError("Missing refresh token — reconnect Trakt via OAuth")
        refresh = decrypt_token(refresh_bytes)

        try:
            resp = self.http.post(
                _TOKEN_URL,
                json={
                    "refresh_token": refresh,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "refresh_token",
                },
                headers=self._trakt_headers(),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Trakt token refresh failed (status=%s): %s", exc.response.status_code, exc.response.text)
            raise SyncClientError("Trakt token refresh failed — please reconnect") from exc
        except httpx.RequestError as exc:
            logger.warning("Trakt token refresh network error: %s", exc)
            raise SyncClientError("Could not reach Trakt — please retry") from exc

        try:
            data = resp.json()
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=self._token_expires_at(data.get("expires_in")),
            )
        except (ValueError, KeyError) as exc:
            raise SyncClientError(
                "Trakt returned an invalid token response — please retry"
            ) from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_watched(self, access_token: str, media_type: str) -> list[dict[str, Any]]:
        """Fetch the full watched list for 'movies' or 'shows'.

        Raises SyncClientError on HTTP or network error.
        """
        try:
            resp = self.http.get(
                f"{_API_BASE}/users/me/watched/{media_type}",
                headers=self._trakt_headers(access_token),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise SyncClientError(
                    "Trakt token rejected — please reconnect your Trakt account"
                ) from exc
            logger.warning("Trakt API error (status=%s): %s", exc.response.status_code, exc.response.text)
            raise SyncClientError(
                f"Trakt returned an error ({exc.response.status_code}) — please retry"
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Trakt network error: %s", exc)
            raise SyncClientError("Could not reach Trakt — please retry") from exc
        try:
            return cast(list[dict[str, Any]], resp.json())
        except ValueError as exc:
            raise SyncClientError(
                "Trakt returned an invalid response — please retry"
            ) from exc

    def _parse_movies(self, entries: list[dict[str, Any]]) -> list[RawItem]:
        valid = [e for e in entries if (e.get("plays") or 0) > 0]
        if not valid:
            return []
        max_plays = max(e["plays"] for e in valid)
        result: list[RawItem] = []
        for entry in valid:
            movie = entry.get("movie") or {}
            title = movie.get("title") or ""
            if not title:
                continue
            trakt_id = (movie.get("ids") or {}).get("trakt")
            if trakt_id is None:
                continue
            plays = entry["plays"]
            result.append(
                RawItem(
                    external_id=str(trakt_id),
                    name=title,
                    item_type="film",
                    engagement_score=plays / max_plays,
                    raw_value=float(plays),
                    raw_type="consumption",
                    metadata={
                        "title_normalized": normalize_title(title),
                        "release_year": movie.get("year") or 0,
                    },
                    last_engaged_at=_parse_ts(entry.get("last_watched_at")),
                )
            )
        return result

    def _parse_shows(self, entries: list[dict[str, Any]]) -> list[RawItem]:
        valid = [e for e in entries if (e.get("plays") or 0) > 0]
        if not valid:
            return []
        max_plays = max(e["plays"] for e in valid)
        result: list[RawItem] = []
        for entry in valid:
            show = entry.get("show") or {}
            title = show.get("title") or ""
            if not title:
                continue
            trakt_id = (show.get("ids") or {}).get("trakt")
            if trakt_id is None:
                continue
            plays = entry["plays"]
            result.append(
                RawItem(
                    external_id=str(trakt_id),
                    name=title,
                    item_type="show",
                    engagement_score=plays / max_plays,
                    raw_value=float(plays),
                    raw_type="consumption",
                    metadata={
                        "title_normalized": normalize_title(title),
                        "release_year": show.get("year") or 0,
                    },
                    last_engaged_at=_parse_ts(entry.get("last_watched_at")),
                )
            )
        return result


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
