"""RateYourMusic CSV import client (no OAuth — ratings export upload only)."""
from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, ClassVar

from syncup.ingest._text import normalize_title
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

if TYPE_CHECKING:
    from syncup.db.models import ServiceConnection

_REQUIRED_COLUMNS = {"Title", "Release_Date", "Rating"}


def _extract_year(date_str: str) -> int:
    """Return the 4-digit year from a release date string, or 0 if unparseable.

    Handles plain years ("1997"), year-month ("1997-05"), and full dates
    ("1997-05-21") by taking the first four characters. Returns 0 for empty,
    non-numeric, or negative values (0 is the sentinel for "unknown year").
    """
    if not date_str or len(date_str) < 4:
        return 0
    try:
        year = int(date_str[:4])
        return year if year > 0 else 0
    except ValueError:
        return 0


class RateYourMusicClient:
    """ServiceClient for RateYourMusic data imported via CSV ratings export.

    RateYourMusic has no public API; users export their ratings as CSV and
    upload it to POST /api/connect/rateyourmusic/import.  The sync route
    raises a SyncClientError if called (re-sync requires a new upload).
    """

    service_name: ClassVar[str] = "rateyourmusic"

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Not supported — RateYourMusic data must be re-imported via CSV upload."""
        raise SyncClientError(
            "RateYourMusic data must be re-imported via CSV — "
            "use POST /api/connect/rateyourmusic/import"
        )

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """No OAuth tokens for RateYourMusic CSV import."""
        return None

    def parse_csv(self, content: str) -> list[RawItem]:
        """Parse a RateYourMusic ratings CSV export and return RawItems.

        Required columns: Title, Release_Date, Rating.
        Optional columns: First Name, Last Name (artist) — included in the
        external_id and metadata when present to prevent title collisions
        across albums with identical names by different artists.

        Skips rows with an empty Rating or empty Title.  Ratings outside the
        [0.5, 5.0] range are clamped silently.  Raises SyncClientError if
        required columns are missing or a rating cannot be parsed as a float.
        """
        if not content.strip():
            return []

        reader = csv.DictReader(io.StringIO(content))
        fieldnames = set(reader.fieldnames or [])
        missing = _REQUIRED_COLUMNS - fieldnames
        if missing:
            raise SyncClientError(
                f"CSV missing required columns: {sorted(missing)}"
            )

        result: list[RawItem] = []
        for row in reader:
            title = (row.get("Title") or "").strip()
            date_str = (row.get("Release_Date") or "").strip()
            rating_str = (row.get("Rating") or "").strip()

            if not rating_str:
                continue
            if not title:
                continue

            try:
                rating = float(rating_str)
            except ValueError:
                raise SyncClientError(f"Invalid rating value: {rating_str!r}") from None

            # Artist is optional — present in full RYM exports but absent in
            # minimal CSV formats. Including it in external_id prevents
            # collision between e.g. "Greatest Hits" by different artists.
            first_name = (row.get("First Name") or "").strip()
            last_name = (row.get("Last Name") or "").strip()
            artist_raw = f"{first_name} {last_name}".strip()
            artist_norm = normalize_title(artist_raw) if artist_raw else ""

            release_year = _extract_year(date_str)
            title_norm = normalize_title(title)
            engagement_score = (rating - 0.5) / 4.5
            engagement_score = max(0.0, min(1.0, engagement_score))

            if artist_norm:
                external_id = f"{artist_norm}:{title_norm}:{release_year}"
            else:
                external_id = f"{title_norm}:{release_year}"

            result.append(
                RawItem(
                    external_id=external_id,
                    name=title,
                    item_type="album",
                    engagement_score=engagement_score,
                    raw_value=rating,
                    raw_type="rating",
                    metadata={
                        "title_normalized": title_norm,
                        "release_year": release_year,
                        "artist_normalized": artist_norm,
                    },
                    last_engaged_at=None,
                )
            )

        return result
