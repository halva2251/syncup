"""Search clients for category-aware autocomplete suggestions."""

from __future__ import annotations

from syncup.ingest.search.models import SearchSuggestion
from syncup.ingest.search.registry import search_category

__all__ = ["SearchSuggestion", "search_category"]
