"""Tests for LetterboxdClient — CSV parsing and Protocol conformance."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from syncup.ingest.letterboxd import LetterboxdClient
from syncup.ingest.protocol import ServiceClient, SyncClientError

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_letterboxd_client_conforms_to_protocol() -> None:
    assert isinstance(LetterboxdClient(), ServiceClient)


def test_letterboxd_service_name() -> None:
    assert LetterboxdClient.service_name == "letterboxd"


def test_letterboxd_refresh_token_returns_none() -> None:
    conn = MagicMock()
    assert LetterboxdClient().refresh_token(conn) is None


def test_letterboxd_fetch_items_raises_sync_client_error() -> None:
    conn = MagicMock()
    with pytest.raises(SyncClientError):
        LetterboxdClient().fetch_items(conn)


# ---------------------------------------------------------------------------
# parse_csv — happy path
# ---------------------------------------------------------------------------

_VALID_CSV = """\
Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date
2024-01-15,The Substance,2024,https://letterboxd.com/film/the-substance/,4.5,No,,2024-01-15
2024-01-10,Stalker,1979,https://letterboxd.com/film/stalker/,5.0,Yes,,2024-01-10
2024-01-05,Interstellar,2014,https://letterboxd.com/film/interstellar/,3.5,No,,2024-01-05
"""


def test_parse_csv_returns_raw_items() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    assert len(items) == 3


def test_parse_csv_item_type_is_film() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    assert all(i["item_type"] == "film" for i in items)


def test_parse_csv_raw_type_is_rating() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    assert all(i["raw_type"] == "rating" for i in items)


def test_parse_csv_preserves_name() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    names = {i["name"] for i in items}
    assert names == {"The Substance", "Stalker", "Interstellar"}


def test_parse_csv_normalizes_engagement_score() -> None:
    # 4.5 stars → (4.5 - 0.5) / 4.5 ≈ 0.8889
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    substance = next(i for i in items if i["name"] == "The Substance")
    assert substance["engagement_score"] == pytest.approx((4.5 - 0.5) / 4.5)
    assert substance["raw_value"] == pytest.approx(4.5)


def test_parse_csv_max_rating_gives_score_one() -> None:
    # 5.0 stars → (5.0 - 0.5) / 4.5 = 1.0
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    stalker = next(i for i in items if i["name"] == "Stalker")
    assert stalker["engagement_score"] == pytest.approx(1.0)


def test_parse_csv_metadata_has_title_normalized_and_release_year() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    stalker = next(i for i in items if i["name"] == "Stalker")
    assert stalker["metadata"]["title_normalized"] == "stalker"
    assert stalker["metadata"]["release_year"] == 1979


def test_parse_csv_external_id_is_stable() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    stalker = next(i for i in items if i["name"] == "Stalker")
    # external_id is deterministic so repeated imports produce the same item row
    assert stalker["external_id"] == "stalker:1979"


def test_parse_csv_last_engaged_at_is_none() -> None:
    items = LetterboxdClient().parse_csv(_VALID_CSV)
    assert all(i["last_engaged_at"] is None for i in items)


# ---------------------------------------------------------------------------
# parse_csv — skipping rows
# ---------------------------------------------------------------------------

_CSV_WITH_UNRATED = """\
Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date
2024-01-15,The Substance,2024,,4.5,No,,2024-01-15
2024-01-10,Stalker,1979,,,No,,2024-01-10
2024-01-05,Interstellar,2014,,,No,,2024-01-05
"""


def test_parse_csv_skips_rows_with_empty_rating() -> None:
    items = LetterboxdClient().parse_csv(_CSV_WITH_UNRATED)
    assert len(items) == 1
    assert items[0]["name"] == "The Substance"


def test_parse_csv_empty_returns_empty_list() -> None:
    # Only header row — no data
    csv = "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
    assert LetterboxdClient().parse_csv(csv) == []


def test_parse_csv_completely_empty_returns_empty_list() -> None:
    assert LetterboxdClient().parse_csv("") == []


# ---------------------------------------------------------------------------
# parse_csv — error cases
# ---------------------------------------------------------------------------


def test_parse_csv_missing_name_column_raises_sync_client_error() -> None:
    bad_csv = "Date,Year,Rating\n2024-01-01,2024,4.5\n"
    with pytest.raises(SyncClientError, match="missing required columns"):
        LetterboxdClient().parse_csv(bad_csv)


def test_parse_csv_missing_year_column_raises_sync_client_error() -> None:
    bad_csv = "Date,Name,Rating\n2024-01-01,Stalker,5.0\n"
    with pytest.raises(SyncClientError, match="missing required columns"):
        LetterboxdClient().parse_csv(bad_csv)


def test_parse_csv_missing_rating_column_raises_sync_client_error() -> None:
    bad_csv = "Date,Name,Year\n2024-01-01,Stalker,1979\n"
    with pytest.raises(SyncClientError, match="missing required columns"):
        LetterboxdClient().parse_csv(bad_csv)


def test_parse_csv_invalid_rating_value_raises_sync_client_error() -> None:
    bad_csv = "Date,Name,Year,Rating\n2024-01-01,Stalker,1979,not-a-number\n"
    with pytest.raises(SyncClientError, match="Invalid rating"):
        LetterboxdClient().parse_csv(bad_csv)


# ---------------------------------------------------------------------------
# parse_csv — edge cases
# ---------------------------------------------------------------------------


def test_parse_csv_title_with_special_chars_normalizes() -> None:
    csv = "Date,Name,Year,Rating\n2024-01-01,Nausicaä of the Valley of the Wind,1984,5.0\n"
    items = LetterboxdClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["metadata"]["title_normalized"] == "nausicaa of the valley of the wind"


def test_parse_csv_missing_year_stored_as_zero() -> None:
    csv = "Date,Name,Year,Rating\n2024-01-01,Unknown Film,,4.0\n"
    items = LetterboxdClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["metadata"]["release_year"] == 0


def test_parse_csv_out_of_range_rating_is_clamped_not_rejected() -> None:
    # Edge case: a manually edited CSV might have rating < 0.5 or > 5.0.
    # The client clamps silently — the import succeeds with a valid score.
    csv = "Date,Name,Year,Rating\n2024-01-01,Weird Film,2024,6.0\n"
    items = LetterboxdClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["engagement_score"] == pytest.approx(1.0)  # clamped to max


def test_parse_csv_zero_rating_clamps_to_zero_score() -> None:
    # Rating of 0.0 (below Letterboxd minimum of 0.5) → clamped to 0.0
    csv = "Date,Name,Year,Rating\n2024-01-01,Boring Film,2024,0.0\n"
    items = LetterboxdClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["engagement_score"] == pytest.approx(0.0)


def test_parse_csv_empty_name_row_is_silently_skipped() -> None:
    # A row with no Name but a valid Rating is dropped — the film can't be
    # identified, so storing it would pollute the catalog with empty-name items.
    csv = "Date,Name,Year,Rating\n2024-01-01,,2024,4.0\n2024-01-02,Stalker,1979,5.0\n"
    items = LetterboxdClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["name"] == "Stalker"
