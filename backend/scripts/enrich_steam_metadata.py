"""Enrich Steam game items with genre metadata from the Steam Store API.

Usage (from backend/):
    python scripts/enrich_steam_metadata.py

Queries all items WHERE service='steam' AND item_type='game' AND genres not
yet set, then calls the Steam Store appdetails API to fetch genre names and
writes them into items.metadata["genres"].

Rate-limited to ~200 req/5 min (1.5 s between calls by default).
Incremental and safe to re-run — already-enriched items are skipped.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import httpx

# Allow running as `python scripts/enrich_steam_metadata.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from syncup.config import Settings
from syncup.db.models import Item
from syncup.db.session import get_session, sessionmaker_for

logger = logging.getLogger(__name__)

_STORE_API = "https://store.steampowered.com/api/appdetails"


def fetch_steam_genres(appid: str, http: httpx.Client) -> list[str] | None:
    """Call Steam Store appdetails API and return a list of genre names.

    Returns None if the item has no genre data or the request fails.
    """
    try:
        resp = http.get(_STORE_API, params={"appids": appid, "filters": "genres"})
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, httpx.RequestError, ValueError):
        logger.warning("Steam appdetails request failed for appid=%s", appid)
        return None

    entry = body.get(appid) or body.get(str(appid))
    if not entry or not entry.get("success"):
        return None

    genres = entry.get("data", {}).get("genres") or []
    names = [g["description"] for g in genres if g.get("description")]
    return names if names else None


def enrich_steam_items(
    session: Session,
    http: httpx.Client,
    *,
    sleep_s: float = 1.5,
) -> int:
    """Enrich all unenriched Steam game items in the given session.

    Args:
        session: SQLAlchemy session.
        http: httpx.Client for Steam Store API calls.
        sleep_s: seconds to sleep between API calls (set to 0 in tests).

    Returns:
        Number of items successfully enriched.
    """
    items = (
        session.query(Item)
        .filter(
            Item.service == "steam",
            Item.item_type == "game",
            Item.meta["genres"].is_(None),
        )
        .all()
    )

    enriched = 0
    for item in items:
        genres = fetch_steam_genres(item.external_id, http)
        if genres:
            safe_meta = item.meta or {}
            item.meta = {**safe_meta, "genres": genres}
            # Commit per-item so a crash mid-run doesn't lose all progress; the
            # HTTP rate limit (1.5 s between calls) makes commit frequency negligible.
            session.commit()
            enriched += 1
            logger.info("Enriched %r (%s): %s", item.name, item.external_id, genres)
        else:
            logger.warning("No genres found for %r (%s) — skipping", item.name, item.external_id)

        if sleep_s > 0:
            time.sleep(sleep_s)

    return enriched


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()  # type: ignore[call-arg]
    factory = sessionmaker_for(settings.database_url)

    with httpx.Client(timeout=httpx.Timeout(15.0)) as http:
        for session in get_session(factory):
            total = enrich_steam_items(session, http)
            logger.info("Done — enriched %d Steam items.", total)


if __name__ == "__main__":
    main()
