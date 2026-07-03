"""TMDB search for film and show autocomplete suggestions."""

from __future__ import annotations

import logging
from typing import ClassVar

import httpx

from syncup.ingest.search.models import SearchSuggestion

logger = logging.getLogger(__name__)

_TMDB_BASE = "https://api.themoviedb.org/3"


class TmdbSearchClient:
    """Search TMDB for films and shows. Requires a TMDB API key."""

    service_name: ClassVar[str] = "tmdb"

    def __init__(self, api_key: str | None, http: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=httpx.Timeout(10.0))

    def _search(
        self, endpoint: str, item_type: str, query: str, limit: int
    ) -> list[SearchSuggestion]:
        if not self.api_key:
            logger.debug("TMDB search skipped: no TMDB_API_KEY configured")
            return []
        if not query or not query.strip():
            return []

        try:
            resp = self.http.get(
                f"{_TMDB_BASE}{endpoint}",
                params={
                    "api_key": self.api_key,
                    "query": query.strip(),
                    "include_adult": "false",
                    "language": "en-US",
                    "page": "1",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.RequestError, ValueError) as exc:
            logger.warning("TMDB search failed: %s", exc)
            return []

        results = data.get("results") or []
        suggestions: list[SearchSuggestion] = []
        for result in results[:limit]:
            name = result.get("title") if item_type == "film" else result.get("name")
            if not name:
                continue
            year = result.get("release_date") or result.get("first_air_date") or ""
            suggestions.append(
                SearchSuggestion(
                    name=name,
                    service=self.service_name,
                    item_type=item_type,
                    external_id=str(result.get("id")) if result.get("id") is not None else None,
                    extra={
                        "year": int(year[:4]) if year and year[:4].isdigit() else None,
                        "overview": (result.get("overview") or "")[:200] or None,
                    },
                )
            )
        return suggestions

    def search_films(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        return self._search("/search/movie", "film", query, limit)

    def search_shows(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        return self._search("/search/tv", "show", query, limit)
