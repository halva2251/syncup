"""AniList GraphQL OAuth client."""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import httpx

logger = logging.getLogger(__name__)

from syncup.ingest._text import normalize_title
from syncup.ingest.crypto import decrypt_token
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

if TYPE_CHECKING:
    from syncup.db.models import ServiceConnection

_AUTHORIZE_URL = "https://anilist.co/api/v2/oauth/authorize"
_TOKEN_URL = "https://anilist.co/api/v2/oauth/token"  # nosec B105
_GRAPHQL_URL = "https://graphql.anilist.co"

# Score divisors per AniList scoreFormat — maps raw score to 0–1.
_SCORE_MAX: dict[str, float] = {
    "POINT_100": 100.0,
    "POINT_10_DECIMAL": 10.0,
    "POINT_10": 10.0,
    "POINT_5": 5.0,
    "POINT_3": 3.0,
}

_FETCH_QUERY = """
query {
  Viewer {
    id
    mediaListOptions { scoreFormat }
  }
  animeList: MediaListCollection(type: ANIME) {
    lists {
      entries {
        media {
          id
          title { romaji english }
          startDate { year }
          format
          genres
        }
        score
        updatedAt
      }
    }
  }
  mangaList: MediaListCollection(type: MANGA) {
    lists {
      entries {
        media {
          id
          title { romaji english }
          startDate { year }
          format
          genres
        }
        score
        updatedAt
      }
    }
  }
}
"""


@dataclass
class AniListClient:
    """ServiceClient for AniList — GraphQL OAuth 2.0.

    Fetches both ANIME and MANGA lists from the authenticated user's account.
    Tokens do not expire; refresh_token always returns None.
    """

    service_name: ClassVar[str] = "anilist"

    client_id: str
    client_secret: str
    redirect_uri: str
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(15.0)), repr=False
    )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> AniListClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def get_authorize_url(self, state: str) -> str:
        """Return the AniList authorization URL for the OAuth flow."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> TokenPair:
        """Exchange an authorization code for an access token.

        AniList tokens do not have an expiry, so expires_at is always None.
        Raises SyncClientError on HTTP or API error.
        """
        try:
            resp = self.http.post(
                _TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "AniList token exchange failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise SyncClientError("AniList token exchange failed — please reconnect") from exc
        except httpx.RequestError as exc:
            logger.warning("AniList token exchange network error: %s", exc)
            raise SyncClientError("Could not reach AniList — please retry") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise SyncClientError("AniList returned an invalid response — please retry") from exc
        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=None,
        )

    # ------------------------------------------------------------------
    # ServiceClient protocol
    # ------------------------------------------------------------------

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch the authenticated user's anime and manga lists.

        Returns combined RawItems for both ANIME and MANGA.
        Skips entries with score == 0 (unrated).
        Raises SyncClientError for expected failures.
        """
        token_bytes: bytes | None = connection.access_token_encrypted
        if token_bytes is None:
            raise SyncClientError("Missing access token — reconnect AniList via OAuth")
        access_token = decrypt_token(token_bytes)

        data = self._graphql(_FETCH_QUERY, {}, access_token)

        viewer = data.get("Viewer") or {}
        score_format = (viewer.get("mediaListOptions") or {}).get("scoreFormat", "POINT_100")
        score_max = _SCORE_MAX.get(score_format, 100.0)

        result: list[RawItem] = []
        result.extend(self._parse_entries(data.get("animeList") or {}, "anime", score_max))
        result.extend(self._parse_entries(data.get("mangaList") or {}, "manga", score_max))
        return result

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """AniList tokens do not expire — no refresh needed."""
        return None

    def fetch_me(self, access_token: str) -> dict[str, Any]:
        """Return the authenticated viewer's profile dict (contains at least 'id').

        Used during the OAuth callback to store the real AniList user ID.
        Raises SyncClientError on failure.
        """
        data = self._graphql("query { Viewer { id } }", {}, access_token)
        return data.get("Viewer") or {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _graphql(self, query: str, variables: dict[str, Any], access_token: str) -> dict[str, Any]:
        """Execute a GraphQL query and return the data dict.

        Raises SyncClientError on HTTP errors or GraphQL error responses.
        """
        try:
            resp = self.http.post(
                _GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "AniList API error (status=%s): %s", exc.response.status_code, exc.response.text
            )
            if exc.response.status_code == 401:
                raise SyncClientError(
                    "AniList token rejected — please reconnect your AniList account"
                ) from exc
            raise SyncClientError(
                f"AniList returned an error ({exc.response.status_code}) — please retry"
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("AniList network error: %s", exc)
            raise SyncClientError("Could not reach AniList — please retry") from exc

        body = resp.json()
        if "errors" in body:
            messages = "; ".join(e.get("message", "Unknown error") for e in body["errors"])
            raise SyncClientError(f"AniList GraphQL error: {messages}")

        return body.get("data") or {}

    def _parse_entries(
        self,
        collection: dict[str, Any],
        item_type: str,
        score_max: float,
    ) -> list[RawItem]:
        result: list[RawItem] = []
        for lst in collection.get("lists") or []:
            for entry in lst.get("entries") or []:
                score = float(entry.get("score") or 0)
                if score == 0:
                    continue

                media = entry.get("media") or {}
                title_obj = media.get("title") or {}
                name = title_obj.get("english") or title_obj.get("romaji") or ""
                if not name:
                    continue

                media_id = media.get("id")
                if media_id is None:
                    continue

                start_date = media.get("startDate") or {}
                release_year = int(start_date.get("year") or 0)
                fmt = media.get("format") or ""
                genres: list[str] = media.get("genres") or []
                title_norm = normalize_title(name)
                engagement_score = max(0.0, min(1.0, score / score_max))

                updated_at_ts = entry.get("updatedAt")
                last_engaged_at = (
                    datetime.fromtimestamp(updated_at_ts, UTC) if updated_at_ts else None
                )

                result.append(
                    RawItem(
                        external_id=str(media_id),
                        name=name,
                        item_type=item_type,
                        engagement_score=engagement_score,
                        raw_value=score,
                        raw_type="rating",
                        metadata={
                            "title_normalized": title_norm,
                            "release_year": release_year,
                            "format": fmt,
                            "genres": genres,
                        },
                        last_engaged_at=last_engaged_at,
                    )
                )
        return result
