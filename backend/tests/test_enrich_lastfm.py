"""Tests for scripts/enrich_lastfm_metadata.py."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from tests.http_helpers import json_response, make_http, make_session


def _make_artist(name: str = "Nick Cave", meta: dict | None = None) -> SimpleNamespace:  # type: ignore[type-arg]
    return SimpleNamespace(
        id=uuid.uuid4(),
        external_id=name.lower().replace(" ", "_"),
        name=name,
        item_type="artist",
        service="lastfm",
        meta=meta if meta is not None else {},
    )


_ARTIST_TAGS_RESPONSE = {
    "artist": {
        "name": "Nick Cave",
        "tags": {
            "tag": [
                {"name": "post-punk", "url": "https://last.fm/tag/post-punk"},
                {"name": "gothic rock", "url": "https://last.fm/tag/gothic-rock"},
                {"name": "alternative", "url": "https://last.fm/tag/alternative"},
            ]
        },
    }
}

_ARTIST_NOT_FOUND_RESPONSE = {
    "error": 6,
    "message": "The artist you supplied could not be found",
}


from scripts.enrich_lastfm_metadata import enrich_lastfm_items, fetch_lastfm_tags


def test_fetch_lastfm_tags_returns_tag_names() -> None:
    http = make_http([json_response(_ARTIST_TAGS_RESPONSE)])
    result = fetch_lastfm_tags("Nick Cave", "test-api-key", http)
    assert result == ["post-punk", "gothic rock", "alternative"]


def test_fetch_lastfm_tags_returns_none_on_artist_not_found() -> None:
    http = make_http([json_response(_ARTIST_NOT_FOUND_RESPONSE)])
    result = fetch_lastfm_tags("Unknown Artist", "test-api-key", http)
    assert result is None


def test_fetch_lastfm_tags_returns_none_on_http_error() -> None:
    http = make_http([httpx.Response(500)])
    result = fetch_lastfm_tags("Nick Cave", "test-api-key", http)
    assert result is None


def test_fetch_lastfm_tags_returns_none_on_network_error() -> None:
    transport = MagicMock(spec=httpx.BaseTransport)
    transport.handle_request.side_effect = httpx.RequestError("timeout")
    http = httpx.Client(transport=transport)
    result = fetch_lastfm_tags("Nick Cave", "test-api-key", http)
    assert result is None


def test_fetch_lastfm_tags_returns_none_when_no_tags() -> None:
    body = {"artist": {"name": "Obscure Artist", "tags": {"tag": []}}}
    http = make_http([json_response(body)])
    result = fetch_lastfm_tags("Obscure Artist", "test-api-key", http)
    assert result is None


def test_fetch_lastfm_tags_caps_at_five_tags() -> None:
    body = {"artist": {"tags": {"tag": [{"name": f"tag{i}", "url": ""} for i in range(10)]}}}
    http = make_http([json_response(body)])
    result = fetch_lastfm_tags("Some Artist", "test-api-key", http)
    assert result is not None
    assert len(result) == 5


def test_enrich_lastfm_items_updates_meta() -> None:
    item = _make_artist()
    session = make_session([item])
    http = make_http([json_response(_ARTIST_TAGS_RESPONSE)])

    count = enrich_lastfm_items(session, "test-api-key", http, sleep_s=0.0)

    assert count == 1
    assert item.meta["genres"] == ["post-punk", "gothic rock", "alternative"]
    session.commit.assert_called()


def test_enrich_lastfm_items_skips_on_not_found() -> None:
    item = _make_artist("Unknown")
    session = make_session([item])
    http = make_http([json_response(_ARTIST_NOT_FOUND_RESPONSE)])

    count = enrich_lastfm_items(session, "test-api-key", http, sleep_s=0.0)

    assert count == 0
    assert "genres" not in item.meta


def test_enrich_lastfm_items_preserves_existing_meta() -> None:
    item = _make_artist(meta={"mbid": "abc-123"})
    session = make_session([item])
    http = make_http([json_response(_ARTIST_TAGS_RESPONSE)])

    enrich_lastfm_items(session, "test-api-key", http, sleep_s=0.0)

    assert item.meta["mbid"] == "abc-123"
    assert "genres" in item.meta


def test_enrich_lastfm_items_continues_after_failure() -> None:
    items = [_make_artist("Artist A"), _make_artist("Artist B")]
    session = make_session(items)
    success_body = {"artist": {"tags": {"tag": [{"name": "jazz", "url": ""}]}}}
    http = make_http([json_response(_ARTIST_NOT_FOUND_RESPONSE), json_response(success_body)])

    count = enrich_lastfm_items(session, "test-api-key", http, sleep_s=0.0)

    assert count == 1
    assert "genres" not in items[0].meta
    assert items[1].meta["genres"] == ["jazz"]


def test_enrich_lastfm_items_empty_returns_zero() -> None:
    session = make_session([])
    http = make_http([])

    count = enrich_lastfm_items(session, "test-api-key", http, sleep_s=0.0)

    assert count == 0
