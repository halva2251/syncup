"""AniList GraphQL search for anime and manga autocomplete suggestions."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import httpx

from syncup.ingest.search.models import SearchSuggestion

logger = logging.getLogger(__name__)

_ANILIST_GRAPHQL = "https://graphql.anilist.co"


class AniListSearchClient:
    """Search AniList for anime and manga. No authentication required for search."""

    service_name: ClassVar[str] = "anilist"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(timeout=httpx.Timeout(10.0))

    def _search(self, item_type: str, query: str, limit: int) -> list[SearchSuggestion]:
        if not query or not query.strip():
            return []

        media_type = "ANIME" if item_type == "anime" else "MANGA"
        graphql_query = """
        query Search($search: String!, $type: MediaType!, $perPage: Int!) {
            Page(perPage: $perPage) {
                media(search: $search, type: $type, sort: SEARCH_MATCH) {
                    id
                    title { english romaji native }
                    format
                    seasonYear
                    startDate { year }
                }
            }
        }
        """
        variables: dict[str, Any] = {
            "search": query.strip(),
            "type": media_type,
            "perPage": min(limit, 20),
        }

        try:
            resp = self.http.post(
                _ANILIST_GRAPHQL,
                json={"query": graphql_query, "variables": variables},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.RequestError, ValueError) as exc:
            logger.warning("AniList search failed: %s", exc)
            return []

        if data.get("errors"):
            logger.warning("AniList search returned errors: %s", data["errors"])
            return []

        results = data.get("data", {}).get("Page", {}).get("media") or []
        suggestions: list[SearchSuggestion] = []
        for media in results[:limit]:
            title = media.get("title") or {}
            name = (
                title.get("english")
                or title.get("romaji")
                or title.get("native")
                or f"Media {media.get('id')}"
            )
            year = media.get("seasonYear") or media.get("startDate", {}).get("year")
            suggestions.append(
                SearchSuggestion(
                    name=name,
                    service=self.service_name,
                    item_type=item_type,
                    external_id=str(media.get("id")) if media.get("id") is not None else None,
                    extra={
                        "year": year,
                        "format": media.get("format"),
                    },
                )
            )
        return suggestions

    def search_anime(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        return self._search("anime", query, limit)

    def search_manga(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        return self._search("manga", query, limit)
