"""Enrich film and show items with genre metadata from the TMDB API.

Usage (from backend/):
    python scripts/enrich_tmdb_metadata.py

Requires TMDB_API_KEY in .env. If unset, the script exits cleanly — films
and shows will embed with name+year only (acceptable fallback).

Queries all items WHERE item_type IN ('film', 'show') AND genres not yet set,
fetches TMDB genre lists once, then searches per item and maps genre_ids.

Rate-limited to ~4 req/s (0.25 s between calls by default).
Incremental and safe to re-run — already-enriched items are skipped.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from syncup.config import Settings
from syncup.db.models import Item
from syncup.db.session import get_session, sessionmaker_for

logger = logging.getLogger(__name__)

_TMDB_BASE = "https://api.themoviedb.org/3"


def _normalize_for_match(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for fuzzy title comparison."""
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _fetch_genre_map(endpoint: str, api_key: str, http: httpx.Client) -> dict[int, str]:
    """Fetch TMDB genre list and return {id: name} mapping."""
    try:
        resp = http.get(f"{_TMDB_BASE}{endpoint}", params={"api_key": api_key})
        resp.raise_for_status()
        return {g["id"]: g["name"] for g in resp.json().get("genres", [])}
    except (httpx.HTTPError, httpx.RequestError, ValueError):
        logger.warning("Failed to fetch TMDB genre list from %s", endpoint)
        return {}


def fetch_tmdb_genres(
    title: str,
    year: int | None,
    item_type: str,
    api_key: str,
    http: httpx.Client,
    genre_map: dict[int, str],
) -> list[str] | None:
    """Search TMDB for a film or show and return a list of genre names.

    Args:
        title: Item display name (used as search query).
        year: Release year for narrowing the search; None omits the year filter.
        item_type: 'film' or 'show' — determines the TMDB search endpoint.
        api_key: TMDB API key.
        http: httpx.Client for API calls.
        genre_map: Pre-fetched {genre_id: genre_name} mapping.

    Returns:
        List of genre name strings, or None if not found / request failed.
    """
    endpoint = "/search/movie" if item_type == "film" else "/search/tv"
    params: dict[str, str | int] = {"api_key": api_key, "query": title}
    if year:
        params["year"] = year

    try:
        resp = http.get(f"{_TMDB_BASE}{endpoint}", params=params)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (httpx.HTTPError, httpx.RequestError, ValueError):
        logger.warning("TMDB search failed for %r (%s)", title, item_type)
        return None

    if not results:
        return None

    # Verify the top result actually matches our title to avoid persisting wrong genres.
    result_title_key = "title" if item_type == "film" else "name"
    result_title = results[0].get(result_title_key, "")
    if _normalize_for_match(result_title) != _normalize_for_match(title):
        logger.warning(
            "TMDB top result %r does not match query %r — skipping",
            result_title,
            title,
        )
        return None

    genre_ids: list[int] = results[0].get("genre_ids", [])
    names = [genre_map[gid] for gid in genre_ids if gid in genre_map]
    return names if names else None


def enrich_tmdb_items(
    session: Session,
    api_key: str,
    http: httpx.Client,
    *,
    sleep_s: float = 0.25,
) -> int:
    """Enrich all unenriched film/show items in the given session.

    Fetches TMDB genre lists once upfront, then searches per item.

    Args:
        session: SQLAlchemy session.
        api_key: TMDB API key.
        http: httpx.Client for API calls.
        sleep_s: seconds to sleep between search calls (set to 0 in tests).

    Returns:
        Number of items successfully enriched.
    """
    movie_genres = _fetch_genre_map("/genre/movie/list", api_key, http)
    tv_genres = _fetch_genre_map("/genre/tv/list", api_key, http)

    if not movie_genres and not tv_genres:
        logger.error("Both TMDB genre lists failed to load — aborting enrichment.")
        return 0

    items = (
        session.query(Item)
        .filter(
            Item.item_type.in_(["film", "show"]),
            Item.meta["genres"].is_(None),
        )
        .all()
    )

    enriched = 0
    for item in items:
        safe_meta = item.meta or {}
        year: int | None = safe_meta.get("release_year") or None
        genre_map = movie_genres if item.item_type == "film" else tv_genres
        genres = fetch_tmdb_genres(item.name, year, item.item_type, api_key, http, genre_map)

        if genres:
            item.meta = {**safe_meta, "genres": genres}
            session.commit()
            enriched += 1
            logger.info("Enriched %r (%s): %s", item.name, item.item_type, genres)
        else:
            logger.warning("No genres found for %r (%s) — skipping", item.name, item.item_type)

        if sleep_s > 0:
            time.sleep(sleep_s)

    return enriched


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()  # type: ignore[call-arg]
    if not settings.tmdb_api_key:
        logger.info(
            "TMDB_API_KEY not set — skipping TMDB enrichment (films will embed with name+year only)."
        )
        return

    factory = sessionmaker_for(settings.database_url)

    with httpx.Client(timeout=httpx.Timeout(10.0)) as http:
        for session in get_session(factory):
            total = enrich_tmdb_items(session, settings.tmdb_api_key, http)
            logger.info("Done — enriched %d film/show items.", total)


if __name__ == "__main__":
    main()
