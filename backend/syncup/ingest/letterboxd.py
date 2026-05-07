"""Letterboxd CSV import client (no OAuth — diary export upload only)."""
from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, ClassVar

from syncup.ingest._text import normalize_title
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

if TYPE_CHECKING:
    from syncup.db.models import ServiceConnection

_REQUIRED_COLUMNS = {"Name", "Year", "Rating"}


class LetterboxdClient:
    """ServiceClient for Letterboxd data imported via CSV diary export.

    Letterboxd has no public API; users export their diary as CSV and upload
    it to POST /api/connect/letterboxd/import.  The sync route raises a
    SyncClientError if called (re-sync is not possible without a new upload).
    """

    service_name: ClassVar[str] = "letterboxd"

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Not supported — Letterboxd data must be re-imported via CSV upload."""
        raise SyncClientError(
            "Letterboxd data must be re-imported via CSV — "
            "use POST /api/connect/letterboxd/import"
        )

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """No OAuth tokens for Letterboxd CSV import."""
        return None

    def parse_csv(self, content: str) -> list[RawItem]:
        """Parse a Letterboxd diary CSV export and return RawItems.

        Skips rows with an empty Rating column.  Raises SyncClientError if
        required columns (Name, Year, Rating) are missing or a rating value
        cannot be parsed as a float.
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
            name = (row.get("Name") or "").strip()
            year_str = (row.get("Year") or "").strip()
            rating_str = (row.get("Rating") or "").strip()

            if not rating_str:
                continue
            if not name:
                continue

            try:
                rating = float(rating_str)
            except ValueError:
                raise SyncClientError(f"Invalid rating value: {rating_str!r}") from None

            try:
                release_year = int(year_str) if year_str else 0
            except ValueError:
                # Degrade gracefully — year is optional metadata. A year of 0
                # means "unknown" and produces external_id "title:0". Two films
                # with the same normalised title and no year share an items row,
                # which is the correct dedup behaviour (they're likely the same film).
                release_year = 0

            title_norm = normalize_title(name)
            engagement_score = (rating - 0.5) / 4.5
            engagement_score = max(0.0, min(1.0, engagement_score))

            result.append(
                RawItem(
                    external_id=f"{title_norm}:{release_year}",
                    name=name,
                    item_type="film",
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
