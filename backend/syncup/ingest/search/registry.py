"""Dispatch obsession category to the right search client."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable

import httpx

from syncup.ingest.search.anilist import AniListSearchClient
from syncup.ingest.search.google_books import GoogleBooksSearchClient
from syncup.ingest.search.models import SearchSuggestion
from syncup.ingest.search.musicbrainz import MusicBrainzSearchClient
from syncup.ingest.search.openlibrary import OpenLibrarySearchClient
from syncup.ingest.search.steam import SteamSearchClient
from syncup.ingest.search.tmdb import TmdbSearchClient

# In-memory TTL cache for search results: {(category, query, limit): (expires_at, results)}.
_cache: dict[tuple[str, str, int], tuple[float, list[SearchSuggestion]]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class SearchConfig:
    """Simple container for search client dependencies."""

    def __init__(
        self,
        *,
        tmdb_api_key: str | None = None,
        musicbrainz_user_agent: str = "SyncUp/0.1.0",
        google_books_api_key: str | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        self.http = http or httpx.Client(timeout=httpx.Timeout(10.0))
        self.steam = SteamSearchClient(http=self.http)
        self.tmdb = TmdbSearchClient(api_key=tmdb_api_key, http=self.http)
        self.anilist = AniListSearchClient(http=self.http)
        self.musicbrainz = MusicBrainzSearchClient(
            user_agent=musicbrainz_user_agent, http=self.http
        )
        self.google_books = GoogleBooksSearchClient(api_key=google_books_api_key, http=self.http)
        self.openlibrary = OpenLibrarySearchClient(http=self.http)


def _book_search_fn(
    config: SearchConfig,
) -> Callable[[str, int], list[SearchSuggestion]]:
    """Use Google Books when an API key is available, otherwise Open Library."""
    if config.google_books.api_key:
        return config.google_books.search_books
    return config.openlibrary.search_books


def _registry(
    config: SearchConfig,
) -> dict[str, Callable[[str, int], list[SearchSuggestion]]]:
    """Return a mapping from obsession category to search function."""
    return {
        "game": config.steam.search,
        "film": config.tmdb.search_films,
        "show": config.tmdb.search_shows,
        "anime": config.anilist.search_anime,
        "manga": config.anilist.search_manga,
        "music": config.musicbrainz.search_artists,
        "book": _book_search_fn(config),
    }


# Module-level default clients populated on first use. This keeps the route simple
# while still allowing tests to inject a custom SearchConfig.
_default_config: SearchConfig | None = None


def get_default_config(
    *,
    tmdb_api_key: str | None = None,
    musicbrainz_user_agent: str = "SyncUp/0.1.0",
    google_books_api_key: str | None = None,
    http: httpx.Client | None = None,
) -> SearchConfig:
    """Return the singleton default search config, creating it if needed."""
    global _default_config
    if _default_config is None:
        _default_config = SearchConfig(
            tmdb_api_key=tmdb_api_key,
            musicbrainz_user_agent=musicbrainz_user_agent,
            google_books_api_key=google_books_api_key,
            http=http,
        )
    return _default_config


def set_default_config(config: SearchConfig) -> None:
    """Override the default config, primarily for tests."""
    global _default_config
    _default_config = config


def clear_cache() -> None:
    """Clear the in-memory search suggestion cache."""
    _cache.clear()


@functools.lru_cache(maxsize=1)
def allowed_categories() -> frozenset[str]:
    return frozenset(
        {"game", "music", "film", "book", "show", "anime", "manga", "community", "other"}
    )


def search_category(
    category: str,
    query: str,
    *,
    limit: int = 10,
    config: SearchConfig | None = None,
    use_cache: bool = True,
) -> list[SearchSuggestion]:
    """Return autocomplete suggestions for an obsession category and query.

    Args:
        category: One of the allowed obsession categories.
        query: User-typed search string.
        limit: Maximum number of suggestions to return.
        config: Optional SearchConfig for dependency injection.
        use_cache: Whether to read/write the in-memory result cache.

    Returns:
        A list of SearchSuggestion objects. Empty list if the category has no
        search client, the query is blank, or the upstream request fails.

    Raises:
        ValueError: If the category is not a recognized obsession category.
    """
    if category not in allowed_categories():
        raise ValueError(f"Unknown obsession category: {category!r}")

    if not query or not query.strip():
        return []

    normalized_query = query.strip()
    cache_key = (category, normalized_query, limit)
    now = time.monotonic()

    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None and cached[0] > now:
            return cached[1]

    search_fn = _registry(config or get_default_config()).get(category)
    if search_fn is None:
        # Categories like 'community' and 'other' intentionally have no upstream search.
        return []

    results = search_fn(normalized_query, limit)

    if use_cache:
        _cache[cache_key] = (now + _CACHE_TTL_SECONDS, results)

    return results
