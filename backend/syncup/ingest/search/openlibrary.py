"""Open Library search for book autocomplete suggestions."""

from __future__ import annotations

import logging
from typing import ClassVar

import httpx

from syncup.ingest.search.models import SearchSuggestion

logger = logging.getLogger(__name__)

_OPENLIBRARY_BASE = "https://openlibrary.org"


class OpenLibrarySearchClient:
    """Search Open Library for books. No API key required."""

    service_name: ClassVar[str] = "openlibrary"
    item_type: ClassVar[str] = "book"

    def __init__(self, http: httpx.Client | None = None) -> None:
        # Open Library can be slow; keep a tight timeout so one slow upstream
        # does not stall the whole autocomplete request.
        self.http = http or httpx.Client(timeout=httpx.Timeout(5.0))

    def search_books(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        """Return up to `limit` book suggestions matching `query`."""
        if not query or not query.strip():
            return []

        try:
            resp = self.http.get(
                f"{_OPENLIBRARY_BASE}/search.json",
                params={
                    # Search titles specifically rather than the broad `q=` index;
                    # this is much faster for book-title autocomplete.
                    "title": query.strip(),
                    "limit": str(min(limit, 20)),
                    "language": "eng",
                    # Request only the fields we need — cuts response size/parsing time.
                    "fields": "key,title,author_name,first_publish_year",
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.RequestError, ValueError) as exc:
            logger.warning("Open Library search failed: %s", exc)
            return []

        docs = data.get("docs") or []
        suggestions: list[SearchSuggestion] = []
        for doc in docs[:limit]:
            title = doc.get("title")
            if not title:
                continue
            author_names = doc.get("author_name") or []
            first_author = author_names[0] if author_names else None
            year = doc.get("first_publish_year")
            suggestions.append(
                SearchSuggestion(
                    name=title,
                    service=self.service_name,
                    item_type=self.item_type,
                    external_id=doc.get("key"),
                    extra={
                        "author": first_author,
                        "year": year,
                    },
                )
            )
        return suggestions
