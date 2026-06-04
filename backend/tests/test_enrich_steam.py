"""Tests for scripts/enrich_steam_metadata.py."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

# ---------------------------------------------------------------------------
# HTTP transport helper (mirrors test_steam.py pattern)
# ---------------------------------------------------------------------------


class _SequenceTransport(httpx.BaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self._idx = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._idx >= len(self._responses):
            raise RuntimeError("No more mock responses")
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


def _http(responses: list[httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=_SequenceTransport(responses))


def _json(body: dict, status: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(status, json=body)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_item(
    appid: str = "730", name: str = "Counter-Strike 2", meta: dict | None = None
) -> SimpleNamespace:  # type: ignore[type-arg]
    return SimpleNamespace(
        id=uuid.uuid4(),
        external_id=appid,
        name=name,
        item_type="game",
        service="steam",
        meta=meta if meta is not None else {},
    )


def _make_session(items: list) -> MagicMock:
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = items
    return session


_APPDETAILS_SUCCESS = {
    "730": {
        "success": True,
        "data": {
            "genres": [
                {"id": "1", "description": "Action"},
                {"id": "37", "description": "Free to Play"},
            ]
        },
    }
}

_APPDETAILS_NO_GENRES = {
    "730": {
        "success": True,
        "data": {},  # no 'genres' key in data
    }
}

_APPDETAILS_FAILURE = {"730": {"success": False}}


# ---------------------------------------------------------------------------
# fetch_steam_genres
# ---------------------------------------------------------------------------


from scripts.enrich_steam_metadata import enrich_steam_items, fetch_steam_genres


def test_fetch_steam_genres_returns_genre_list() -> None:
    http = _http([_json(_APPDETAILS_SUCCESS)])
    result = fetch_steam_genres("730", http)
    assert result == ["Action", "Free to Play"]


def test_fetch_steam_genres_returns_none_when_success_false() -> None:
    http = _http([_json(_APPDETAILS_FAILURE)])
    result = fetch_steam_genres("730", http)
    assert result is None


def test_fetch_steam_genres_returns_none_when_no_genres_in_data() -> None:
    http = _http([_json(_APPDETAILS_NO_GENRES)])
    result = fetch_steam_genres("730", http)
    assert result is None


def test_fetch_steam_genres_returns_none_on_http_error() -> None:
    http = _http([httpx.Response(500)])
    result = fetch_steam_genres("730", http)
    assert result is None


def test_fetch_steam_genres_returns_none_on_network_error() -> None:
    transport = MagicMock(spec=httpx.BaseTransport)
    transport.handle_request.side_effect = httpx.RequestError("timeout")
    http = httpx.Client(transport=transport)
    result = fetch_steam_genres("730", http)
    assert result is None


def test_fetch_steam_genres_returns_none_on_empty_genres_list() -> None:
    body = {"730": {"success": True, "data": {"genres": []}}}
    http = _http([_json(body)])
    result = fetch_steam_genres("730", http)
    assert result is None


# ---------------------------------------------------------------------------
# enrich_steam_items
# ---------------------------------------------------------------------------


def test_enrich_steam_items_updates_item_meta() -> None:
    item = _make_item()
    session = _make_session([item])
    http = _http([_json(_APPDETAILS_SUCCESS)])

    count = enrich_steam_items(session, http, sleep_s=0.0)

    assert count == 1
    assert item.meta["genres"] == ["Action", "Free to Play"]
    session.commit.assert_called()


def test_enrich_steam_items_skips_item_on_http_failure() -> None:
    item = _make_item()
    session = _make_session([item])
    http = _http([_json(_APPDETAILS_FAILURE)])

    count = enrich_steam_items(session, http, sleep_s=0.0)

    assert count == 0
    assert "genres" not in item.meta
    session.commit.assert_not_called()


def test_enrich_steam_items_returns_count_of_enriched() -> None:
    items = [_make_item("730"), _make_item("570", "Dota 2")]
    session = _make_session(items)
    http = _http(
        [
            _json(
                {
                    "730": {
                        "success": True,
                        "data": {"genres": [{"id": "1", "description": "Action"}]},
                    }
                }
            ),
            _json(
                {
                    "570": {
                        "success": True,
                        "data": {"genres": [{"id": "23", "description": "Strategy"}]},
                    }
                }
            ),
        ]
    )

    count = enrich_steam_items(session, http, sleep_s=0.0)

    assert count == 2
    assert items[0].meta["genres"] == ["Action"]
    assert items[1].meta["genres"] == ["Strategy"]


def test_enrich_steam_items_preserves_existing_meta_keys() -> None:
    item = _make_item(meta={"description": "A great game"})
    session = _make_session([item])
    http = _http([_json(_APPDETAILS_SUCCESS)])

    enrich_steam_items(session, http, sleep_s=0.0)

    assert item.meta["description"] == "A great game"
    assert item.meta["genres"] == ["Action", "Free to Play"]


def test_enrich_steam_items_continues_after_one_failure() -> None:
    items = [_make_item("730"), _make_item("570", "Dota 2")]
    session = _make_session(items)
    http = _http(
        [
            _json(_APPDETAILS_FAILURE),  # first item fails
            _json(
                {
                    "570": {
                        "success": True,
                        "data": {"genres": [{"id": "23", "description": "Strategy"}]},
                    }
                }
            ),
        ]
    )

    count = enrich_steam_items(session, http, sleep_s=0.0)

    assert count == 1
    assert "genres" not in items[0].meta
    assert items[1].meta["genres"] == ["Strategy"]


def test_enrich_steam_items_no_items_returns_zero() -> None:
    session = _make_session([])
    http = _http([])

    count = enrich_steam_items(session, http, sleep_s=0.0)

    assert count == 0
