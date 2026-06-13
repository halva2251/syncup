"""Steam Store search for game autocomplete suggestions."""

from __future__ import annotations

import logging
from typing import ClassVar

import httpx

from syncup.ingest.search.models import SearchSuggestion

logger = logging.getLogger(__name__)

_STEAM_STORE_SEARCH = "https://store.steampowered.com/api/storesearch/"


class SteamSearchClient:
    """Search the Steam store catalog. No API key required."""

    service_name: ClassVar[str] = "steam"
    item_type: ClassVar[str] = "game"

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(timeout=httpx.Timeout(10.0))

    def search(self, query: str, limit: int = 10) -> list[SearchSuggestion]:
        """Return up to `limit` game suggestions matching `query`."""
        if not query or not query.strip():
            return []

        try:
            resp = self.http.get(
                _STEAM_STORE_SEARCH,
                params={
                    "term": query.strip(),
                    "l": "english",
                    "cc": "US",
                    "count": str(min(limit, 20)),
                },
                headers={
                    # Steam returns JSON when an Accept header is present.
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.RequestError, ValueError) as exc:
            logger.warning("Steam store search failed: %s", exc)
            return []

        items = data.get("items") or []
        suggestions: list[SearchSuggestion] = []
        for item in items[:limit]:
            appid = item.get("id")
            name = item.get("name")
            if not name:
                continue
            suggestions.append(
                SearchSuggestion(
                    name=name,
                    service=self.service_name,
                    item_type=self.item_type,
                    external_id=str(appid) if appid is not None else None,
                    extra={
                        "is_free": item.get("is_free"),
                        "type": item.get("type"),
                    },
                )
            )
        return suggestions
