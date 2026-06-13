"""GET /api/items/search — category-aware autocomplete for obsessions."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from syncup.auth.router import RequireAuth
from syncup.config import Settings
from syncup.ingest.search.registry import (
    SearchConfig,
    get_default_config,
    search_category,
)
from syncup.limiter import limiter

router = APIRouter(prefix="/api/items", tags=["search"])

_ObsessionCategory = Literal[
    "game",
    "music",
    "film",
    "book",
    "show",
    "anime",
    "manga",
    "community",
    "other",
]


class SearchSuggestionOut(BaseModel):
    name: str
    service: str
    item_type: str
    external_id: str | None = None
    extra: dict[str, Any] | None = None


class ItemSearchOut(BaseModel):
    items: list[SearchSuggestionOut]


def _search_config(settings: Settings) -> SearchConfig:
    """Return the configured SearchConfig, creating the singleton if needed."""
    return get_default_config(
        tmdb_api_key=settings.tmdb_api_key,
        musicbrainz_user_agent=settings.musicbrainz_user_agent,
        google_books_api_key=settings.google_books_api_key,
    )


@router.get("/search", response_model=ItemSearchOut)
@limiter.limit("30/minute")
def search_items(
    request: Request,
    user: RequireAuth,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    category: Annotated[_ObsessionCategory, Query(...)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> ItemSearchOut:
    """Return autocomplete suggestions for an obsession category and query.

    Results are sourced from public search APIs per category:
      - game  → Steam Store
      - film/show → TMDB (requires TMDB_API_KEY)
      - anime/manga → AniList
      - music → MusicBrainz
      - book  → Google Books (requires GOOGLE_BOOKS_API_KEY) or Open Library fallback
      - community, other → no upstream search, empty result
    """
    settings: Settings = request.app.state.settings
    config = _search_config(settings)

    suggestions = search_category(category, q, limit=limit, config=config)
    return ItemSearchOut(
        items=[
            SearchSuggestionOut(
                name=s.name,
                service=s.service,
                item_type=s.item_type,
                external_id=s.external_id,
                extra=s.extra,
            )
            for s in suggestions
        ]
    )
