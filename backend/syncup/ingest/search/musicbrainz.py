"""MusicBrainz search for music artist autocomplete suggestions."""

from __future__ import annotations

import logging
import time
from typing import ClassVar

import httpx

from syncup.ingest.search.models import SearchSuggestion

logger = logging.getLogger(__name__)

_MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"


class MusicBrainzSearchClient:
    """Search MusicBrainz for artists. No API key required; custom User-Agent is mandatory."""

    service_name: ClassVar[str] = "musicbrainz"
    item_type: ClassVar[str] = "artist"
    # MusicBrainz asks for 1 request per second for unauthenticated clients.
    _last_request_at: ClassVar[float] = 0.0

    def __init__(self, user_agent: str, http: httpx.Client | None = None) -> None:
        self.user_agent = user_agent
        self.http = http or httpx.Client(timeout=httpx.Timeout(10.0))

    def _rate_limited_get(self, url: str, params: dict[str, str]) -> httpx.Response:
        """Ensure at least 1 second between MusicBrainz requests."""
        now = time.monotonic()
        elapsed = now - MusicBrainzSearchClient._last_request_at
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        resp = self.http.get(url, params=params, headers={"User-Agent": self.user_agent})
        MusicBrainzSearchClient._last_request_at = time.monotonic()
        return resp

    def search_artists(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        """Return up to `limit` artist suggestions matching `query`."""
        if not query or not query.strip():
            return []

        try:
            resp = self._rate_limited_get(
                f"{_MUSICBRAINZ_BASE}/artist/",
                {
                    "query": query.strip(),
                    "fmt": "json",
                    "limit": str(min(limit, 20)),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.RequestError, ValueError) as exc:
            logger.warning("MusicBrainz search failed: %s", exc)
            return []

        artists = data.get("artists") or []
        suggestions: list[SearchSuggestion] = []
        for artist in artists[:limit]:
            name = artist.get("name")
            if not name:
                continue
            suggestions.append(
                SearchSuggestion(
                    name=name,
                    service=self.service_name,
                    item_type=self.item_type,
                    external_id=artist.get("id"),
                    extra={
                        "disambiguation": artist.get("disambiguation"),
                        "country": artist.get("country"),
                    },
                )
            )
        return suggestions
