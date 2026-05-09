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
    ("1997-05-21") by taking the first four characters.
    """
    if not date_str or len(date_str) < 4:
        return 0
    try:
        return int(date_str[:4])
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

        Skips rows with an empty Rating column or empty Title.  Raises
        SyncClientError if required columns (Title, Release_Date, Rating) are
        missing or a rating value cannot be parsed as a float.
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

            release_year = _extract_year(date_str)
            title_norm = normalize_title(title)
            engagement_score = (rating - 0.5) / 4.5
            engagement_score = max(0.0, min(1.0, engagement_score))

            result.append(
                RawItem(
                    external_id=f"{title_norm}:{release_year}",
                    name=title,
                    item_type="album",
                    engagement_score=engagement_score,
                    raw_value=rating,
                    raw_type="rating",
                    metadata={
                        "title_normalized": title_norm,
                        "release_year": release_year,
                    },
                    last_engaged_at=None,
                )
            )

        return result
