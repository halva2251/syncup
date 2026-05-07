"""Tests for ServiceClient Protocol, RawItem TypedDict, and TokenPair dataclass."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import pytest

from syncup.ingest.protocol import RawItem, ServiceClient, SyncClientError, TokenPair

# ---------------------------------------------------------------------------
# Minimal conforming client for Protocol tests
# ---------------------------------------------------------------------------


class _ConformingClient:
    service_name: ClassVar[str] = "dummy"

    def fetch_items(self, connection: object) -> list[RawItem]:
        return []

    def refresh_token(self, connection: object) -> TokenPair | None:
        return None


# ---------------------------------------------------------------------------
# TokenPair
# ---------------------------------------------------------------------------


def test_token_pair_is_frozen() -> None:
    tp = TokenPair(access_token="tok", refresh_token=None, expires_at=None)
    with pytest.raises((AttributeError, TypeError)):
        tp.access_token = "other"  # type: ignore[misc]


def test_token_pair_stores_all_fields() -> None:
    now = datetime.now(UTC)
    tp = TokenPair(access_token="acc", refresh_token="ref", expires_at=now)
    assert tp.access_token == "acc"
    assert tp.refresh_token == "ref"
    assert tp.expires_at == now


def test_token_pair_allows_none_refresh_and_expiry() -> None:
    tp = TokenPair(access_token="acc", refresh_token=None, expires_at=None)
    assert tp.refresh_token is None
    assert tp.expires_at is None


# ---------------------------------------------------------------------------
# RawItem (TypedDict — structural checks only)
# ---------------------------------------------------------------------------


def test_raw_item_consumption_shape() -> None:
    item: RawItem = {
        "external_id": "730",
        "name": "Counter-Strike 2",
        "item_type": "game",
        "engagement_score": 0.85,
        "raw_value": 3600.0,
        "raw_type": "consumption",
        "metadata": {"img_icon_url": "abc.png"},
        "last_engaged_at": None,
    }
    assert item["raw_type"] == "consumption"
    assert item["engagement_score"] == pytest.approx(0.85)
    assert item["raw_value"] == pytest.approx(3600.0)
    assert item["last_engaged_at"] is None


def test_raw_item_rating_shape() -> None:
    item: RawItem = {
        "external_id": "disco-elysium",
        "name": "Disco Elysium",
        "item_type": "film",
        "engagement_score": 1.0,
        "raw_value": 5.0,
        "raw_type": "rating",
        "metadata": {"title_normalized": "disco elysium", "release_year": 2019},
        "last_engaged_at": None,
    }
    assert item["raw_type"] == "rating"
    assert item["metadata"]["release_year"] == 2019


def test_raw_item_allows_none_raw_value() -> None:
    item: RawItem = {
        "external_id": "x",
        "name": "X",
        "item_type": "community",
        "engagement_score": 0.5,
        "raw_value": None,
        "raw_type": "consumption",
        "metadata": {},
        "last_engaged_at": None,
    }
    assert item["raw_value"] is None


def test_raw_item_allows_datetime_last_engaged_at() -> None:
    now = datetime.now(UTC)
    item: RawItem = {
        "external_id": "x",
        "name": "X",
        "item_type": "game",
        "engagement_score": 0.1,
        "raw_value": 60.0,
        "raw_type": "consumption",
        "metadata": {},
        "last_engaged_at": now,
    }
    assert item["last_engaged_at"] == now


# ---------------------------------------------------------------------------
# ServiceClient Protocol
# ---------------------------------------------------------------------------


def test_conforming_client_passes_isinstance_check() -> None:
    client = _ConformingClient()
    assert isinstance(client, ServiceClient)


def test_missing_fetch_items_fails_isinstance_check() -> None:
    class _NoFetch:
        service_name: ClassVar[str] = "bad"

        def refresh_token(self, connection: object) -> None:
            return None

    assert not isinstance(_NoFetch(), ServiceClient)


def test_missing_refresh_token_fails_isinstance_check() -> None:
    class _NoRefresh:
        service_name: ClassVar[str] = "bad"

        def fetch_items(self, connection: object) -> list[RawItem]:
            return []

    assert not isinstance(_NoRefresh(), ServiceClient)


def test_service_name_accessible_on_class() -> None:
    assert _ConformingClient.service_name == "dummy"


def test_service_name_accessible_on_instance() -> None:
    assert _ConformingClient().service_name == "dummy"


# ---------------------------------------------------------------------------
# SyncClientError
# ---------------------------------------------------------------------------


def test_sync_client_error_is_exception() -> None:
    assert issubclass(SyncClientError, Exception)


def test_sync_client_error_message() -> None:
    exc = SyncClientError("token expired — reconnect the service")
    assert str(exc) == "token expired — reconnect the service"


def test_sync_client_error_is_catchable_as_exception() -> None:
    with pytest.raises(Exception):
        raise SyncClientError("oops")
