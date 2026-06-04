"""Enrich Last.fm artist items with genre tags from the Last.fm API.

Usage (from backend/):
    python scripts/enrich_lastfm_metadata.py

Queries all items WHERE service='lastfm' AND item_type='artist' AND genres not
yet set, then calls Last.fm artist.getInfo to fetch top tags as genre names.

Rate-limited to ~5 req/s (0.2 s between calls by default).
Incremental and safe to re-run — already-enriched items are skipped.
"""

from __future__ import annotations

import logging
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

_LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
_MAX_TAGS = 5


def fetch_lastfm_tags(artist_name: str, api_key: str, http: httpx.Client) -> list[str] | None:
    """Call Last.fm artist.getInfo and return up to 5 top tag names.

    Returns None if the artist is not found, has no tags, or the request fails.
    """
    try:
        resp = http.get(
            _LASTFM_API,
            params={
                "method": "artist.getinfo",
                "artist": artist_name,
                "api_key": api_key,
                "format": "json",
            },
        )
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, httpx.RequestError, ValueError):
        logger.warning("Last.fm request failed for artist=%r", artist_name)
        return None

    # Last.fm returns {"error": N, "message": "..."} on failure, even with HTTP 200
    if "error" in body:
        logger.warning("Last.fm error for artist=%r: %s", artist_name, body.get("message", ""))
        return None

    tags_raw = body.get("artist", {}).get("tags", {}).get("tag", [])
    names = [t["name"] for t in tags_raw if t.get("name")][:_MAX_TAGS]
    return names if names else None


def enrich_lastfm_items(
    session: Session,
    api_key: str,
    http: httpx.Client,
    *,
    sleep_s: float = 0.2,
) -> int:
    """Enrich all unenriched Last.fm artist items in the given session.

    Args:
        session: SQLAlchemy session.
        api_key: Last.fm API key.
        http: httpx.Client for API calls.
        sleep_s: seconds to sleep between API calls (set to 0 in tests).

    Returns:
        Number of items successfully enriched.
    """
    items = (
        session.query(Item)
        .filter(
            Item.service == "lastfm",
            Item.item_type == "artist",
            Item.meta["genres"].is_(None),
        )
        .all()
    )

    enriched = 0
    for item in items:
        tags = fetch_lastfm_tags(item.name, api_key, http)
        if tags:
            safe_meta = item.meta or {}
            item.meta = {**safe_meta, "genres": tags}
            session.commit()
            enriched += 1
            logger.info("Enriched %r: %s", item.name, tags)
        else:
            logger.warning("No tags found for %r — skipping", item.name)

        if sleep_s > 0:
            time.sleep(sleep_s)

    return enriched


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()  # type: ignore[call-arg]
    if not settings.lastfm_api_key:
        logger.error("LASTFM_API_KEY is not set — cannot enrich Last.fm artists.")
        sys.exit(1)

    factory = sessionmaker_for(settings.database_url)

    with httpx.Client(timeout=httpx.Timeout(10.0)) as http:
        for session in get_session(factory):
            total = enrich_lastfm_items(session, settings.lastfm_api_key, http)
            logger.info("Done — enriched %d Last.fm artist items.", total)


if __name__ == "__main__":
    main()
