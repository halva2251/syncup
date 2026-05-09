"""Tests for RateYourMusicClient — CSV parsing and Protocol conformance."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from syncup.ingest.rateyourmusic import RateYourMusicClient
from syncup.ingest.protocol import ServiceClient, SyncClientError

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_rateyourmusic_client_conforms_to_protocol() -> None:
    assert isinstance(RateYourMusicClient(), ServiceClient)


def test_rateyourmusic_service_name() -> None:
    assert RateYourMusicClient.service_name == "rateyourmusic"


def test_rateyourmusic_refresh_token_returns_none() -> None:
    conn = MagicMock()
    assert RateYourMusicClient().refresh_token(conn) is None


def test_rateyourmusic_fetch_items_raises_sync_client_error() -> None:
    conn = MagicMock()
    with pytest.raises(SyncClientError):
        RateYourMusicClient().fetch_items(conn)


# ---------------------------------------------------------------------------
# parse_csv — happy path
# ---------------------------------------------------------------------------

_VALID_CSV = """\
RYM Album,First Name,Last Name,Title,Release_Date,Rating,Ownership
1234,Radiohead,,OK Computer,1997,5.0,Own
5678,Portishead,,Dummy,1994,4.5,Own
9012,Boards of Canada,,Music Has the Right to Children,1998,4.0,Own
"""


def test_parse_csv_returns_raw_items() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    assert len(items) == 3


def test_parse_csv_item_type_is_album() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    assert all(i["item_type"] == "album" for i in items)


def test_parse_csv_raw_type_is_rating() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    assert all(i["raw_type"] == "rating" for i in items)


def test_parse_csv_preserves_title() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    titles = {i["name"] for i in items}
    assert titles == {"OK Computer", "Dummy", "Music Has the Right to Children"}


def test_parse_csv_normalizes_engagement_score() -> None:
    # 4.5 stars → (4.5 - 0.5) / 4.5 ≈ 0.8889
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    dummy = next(i for i in items if i["name"] == "Dummy")
    assert dummy["engagement_score"] == pytest.approx((4.5 - 0.5) / 4.5)
    assert dummy["raw_value"] == pytest.approx(4.5)


def test_parse_csv_max_rating_gives_score_one() -> None:
    # 5.0 stars → (5.0 - 0.5) / 4.5 = 1.0
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    ok_computer = next(i for i in items if i["name"] == "OK Computer")
    assert ok_computer["engagement_score"] == pytest.approx(1.0)


def test_parse_csv_metadata_has_title_normalized_and_release_year() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    dummy = next(i for i in items if i["name"] == "Dummy")
    assert dummy["metadata"]["title_normalized"] == "dummy"
    assert dummy["metadata"]["release_year"] == 1994


def test_parse_csv_metadata_includes_artist_normalized() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    dummy = next(i for i in items if i["name"] == "Dummy")
    assert dummy["metadata"]["artist_normalized"] == "portishead"


def test_parse_csv_external_id_includes_artist_when_present() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    ok_computer = next(i for i in items if i["name"] == "OK Computer")
    # artist prevents collisions between albums with the same normalized title
    assert ok_computer["external_id"] == "radiohead:ok computer:1997"


def test_parse_csv_external_id_is_stable() -> None:
    # Same import twice must produce the same external_id (idempotent re-import)
    items1 = RateYourMusicClient().parse_csv(_VALID_CSV)
    items2 = RateYourMusicClient().parse_csv(_VALID_CSV)
    ids1 = {i["external_id"] for i in items1}
    ids2 = {i["external_id"] for i in items2}
    assert ids1 == ids2


def test_parse_csv_last_engaged_at_is_none() -> None:
    items = RateYourMusicClient().parse_csv(_VALID_CSV)
    assert all(i["last_engaged_at"] is None for i in items)


# ---------------------------------------------------------------------------
# parse_csv — Release_Date year extraction
# ---------------------------------------------------------------------------


def test_parse_csv_extracts_year_from_full_date() -> None:
    # RYM sometimes exports "1997-05-21" — extract just the year
    csv = "Title,Release_Date,Rating\nOK Computer,1997-05-21,5.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert items[0]["metadata"]["release_year"] == 1997


def test_parse_csv_extracts_year_from_year_month() -> None:
    csv = "Title,Release_Date,Rating\nDummy,1994-08,4.5\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert items[0]["metadata"]["release_year"] == 1994


def test_parse_csv_negative_release_date_stored_as_zero() -> None:
    # Malformed strings like "-197-05" must not produce negative years
    csv = "Title,Release_Date,Rating\nSome Album,-197-05,4.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert items[0]["metadata"]["release_year"] == 0


def test_parse_csv_without_artist_columns_falls_back_to_title_only_external_id() -> None:
    # Minimal CSV (no First Name / Last Name columns) still works
    csv = "Title,Release_Date,Rating\nOK Computer,1997,5.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert items[0]["external_id"] == "ok computer:1997"
    assert items[0]["metadata"]["artist_normalized"] == ""


def test_parse_csv_without_artist_metadata_artist_normalized_is_empty_string() -> None:
    csv = "Title,Release_Date,Rating\nDummy,1994,4.5\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert items[0]["metadata"]["artist_normalized"] == ""


# ---------------------------------------------------------------------------
# parse_csv — skipping rows
# ---------------------------------------------------------------------------

_CSV_WITH_UNRATED = """\
Title,Release_Date,Rating
OK Computer,1997,5.0
Dummy,1994,
Music Has the Right to Children,1998,
"""


def test_parse_csv_skips_rows_with_empty_rating() -> None:
    items = RateYourMusicClient().parse_csv(_CSV_WITH_UNRATED)
    assert len(items) == 1
    assert items[0]["name"] == "OK Computer"


def test_parse_csv_empty_csv_returns_empty_list() -> None:
    # Only header row — no data
    csv = "Title,Release_Date,Rating\n"
    assert RateYourMusicClient().parse_csv(csv) == []


def test_parse_csv_completely_empty_returns_empty_list() -> None:
    assert RateYourMusicClient().parse_csv("") == []


# ---------------------------------------------------------------------------
# parse_csv — error cases
# ---------------------------------------------------------------------------


def test_parse_csv_missing_title_column_raises_sync_client_error() -> None:
    bad_csv = "Release_Date,Rating\n1997,5.0\n"
    with pytest.raises(SyncClientError, match="missing required columns"):
        RateYourMusicClient().parse_csv(bad_csv)


def test_parse_csv_missing_release_date_column_raises_sync_client_error() -> None:
    bad_csv = "Title,Rating\nOK Computer,5.0\n"
    with pytest.raises(SyncClientError, match="missing required columns"):
        RateYourMusicClient().parse_csv(bad_csv)


def test_parse_csv_missing_rating_column_raises_sync_client_error() -> None:
    bad_csv = "Title,Release_Date\nOK Computer,1997\n"
    with pytest.raises(SyncClientError, match="missing required columns"):
        RateYourMusicClient().parse_csv(bad_csv)


def test_parse_csv_invalid_rating_value_raises_sync_client_error() -> None:
    bad_csv = "Title,Release_Date,Rating\nOK Computer,1997,not-a-number\n"
    with pytest.raises(SyncClientError, match="Invalid rating"):
        RateYourMusicClient().parse_csv(bad_csv)


# ---------------------------------------------------------------------------
# parse_csv — edge cases
# ---------------------------------------------------------------------------


def test_parse_csv_missing_release_date_stored_as_zero() -> None:
    csv = "Title,Release_Date,Rating\nUnknown Album,,4.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["metadata"]["release_year"] == 0


def test_parse_csv_unparseable_release_date_stored_as_zero() -> None:
    csv = "Title,Release_Date,Rating\nSome Album,unknown,4.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["metadata"]["release_year"] == 0


def test_parse_csv_out_of_range_rating_is_clamped_not_rejected() -> None:
    # A manually edited CSV might have rating > 5.0 — clamp silently.
    csv = "Title,Release_Date,Rating\nWeird Album,2024,6.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["engagement_score"] == pytest.approx(1.0)


def test_parse_csv_zero_rating_clamps_to_zero_score() -> None:
    csv = "Title,Release_Date,Rating\nBoring Album,2024,0.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["engagement_score"] == pytest.approx(0.0)


def test_parse_csv_empty_title_row_is_silently_skipped() -> None:
    csv = "Title,Release_Date,Rating\n,2024,4.0\nDummy,1994,4.5\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["name"] == "Dummy"


def test_parse_csv_title_with_special_chars_normalizes() -> None:
    csv = "Title,Release_Date,Rating\nNausicaä of the Valley of the Wind,1984,5.0\n"
    items = RateYourMusicClient().parse_csv(csv)
    assert len(items) == 1
    assert items[0]["metadata"]["title_normalized"] == "nausicaa of the valley of the wind"
