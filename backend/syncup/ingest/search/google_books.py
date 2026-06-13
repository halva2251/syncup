"""Google Books search for book autocomplete suggestions."""

from __future__ import annotations

import logging
from typing import ClassVar

import httpx

from syncup.ingest.search.models import SearchSuggestion

logger = logging.getLogger(__name__)

_GOOGLE_BOOKS_BASE = "https://www.googleapis.com/books/v1"


class GoogleBooksSearchClient:
    """Search Google Books. Requires a Google Books API key."""

    service_name: ClassVar[str] = "google_books"
    item_type: ClassVar[str] = "book"

    def __init__(self, api_key: str | None, http: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=httpx.Timeout(5.0))

    def search_books(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        """Return up to `limit` book suggestions matching `query`."""
        if not self.api_key:
            logger.debug("Google Books search skipped: no GOOGLE_BOOKS_API_KEY configured")
            return []
        if not query or not query.strip():
            return []

        try:
            resp = self.http.get(
                f"{_GOOGLE_BOOKS_BASE}/volumes",
                params={
                    "q": query.strip(),
                    "maxResults": str(min(limit, 20)),
                    "printType": "books",
                    "langRestrict": "en",
                    "key": self.api_key,
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.RequestError, ValueError) as exc:
            logger.warning("Google Books search failed: %s", exc)
            return []

        items = data.get("items") or []
        suggestions: list[SearchSuggestion] = []
        for item in items[:limit]:
            volume = item.get("volumeInfo") or {}
            title = volume.get("title")
            if not title:
                continue
            authors = volume.get("authors") or []
            first_author = authors[0] if authors else None
            year = None
            published = volume.get("publishedDate") or ""
            if published and published[:4].isdigit():
                year = int(published[:4])
            suggestions.append(
                SearchSuggestion(
                    name=title,
                    service=self.service_name,
                    item_type=self.item_type,
                    external_id=item.get("id"),
                    extra={
                        "author": first_author,
                        "year": year,
                    },
                )
            )
        return suggestions
