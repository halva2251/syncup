"""Tests for AniListClient — GraphQL OAuth client, Protocol conformance, fetch_items."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest

from syncup.ingest.protocol import ServiceClient, SyncClientError

# ---------------------------------------------------------------------------
# httpx mock transport helpers
# ---------------------------------------------------------------------------


class _SequenceTransport(httpx.BaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self._index = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._index >= len(self._responses):
            raise RuntimeError(f"No more mock responses (index={self._index})")
        resp = self._responses[self._index]
        self._index += 1
        return resp


def _json_resp(body: dict, status: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(status, json=body)


def _client(responses: list[httpx.Response]):  # type: ignore[return]
    from syncup.ingest.anilist import AniListClient

    transport = _SequenceTransport(responses)
    http = httpx.Client(transport=transport)
    return AniListClient(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://127.0.0.1:3000/api/connect/anilist/oauth/callback",
        http=http,
    )


# ---------------------------------------------------------------------------
# Canned API responses
# ---------------------------------------------------------------------------

_VIEWER_BODY = {
    "data": {
        "Viewer": {
            "id": 12345,
            "mediaListOptions": {"scoreFormat": "POINT_100"},
        }
    }
}

_ANIME_BODY = {
    "data": {
        "MediaListCollection": {
            "lists": [
                {
                    "entries": [
                        {
                            "media": {
                                "id": 30,
                                "title": {
                                    "romaji": "Neon Genesis Evangelion",
                                    "english": "Neon Genesis Evangelion",
                                },
                                "startDate": {"year": 1995},
                                "format": "TV",
                            },
                            "score": 95,
                            "updatedAt": 1700000000,
                        },
                        {
                            "media": {
                                "id": 31,
                                "title": {"romaji": "Akira", "english": "Akira"},
                                "startDate": {"year": 1988},
                                "format": "MOVIE",
                            },
                            "score": 0,  # should be skipped
                            "updatedAt": 1700000001,
                        },
                    ]
                }
            ]
        }
    }
}

_MANGA_BODY = {
    "data": {
        "MediaListCollection": {
            "lists": [
                {
                    "entries": [
                        {
                            "media": {
                                "id": 100,
                                "title": {
                                    "romaji": "Berserk",
                                    "english": None,  # no English title
                                },
                                "startDate": {"year": 1989},
                                "format": "MANGA",
                            },
                            "score": 100,
                            "updatedAt": 1700000002,
                        }
                    ]
                }
            ]
        }
    }
}

_COMBINED_BODY = {
    "data": {
        "Viewer": {
            "id": 12345,
            "mediaListOptions": {"scoreFormat": "POINT_100"},
        },
        "animeList": {
            "lists": [
                {
                    "entries": [
                        {
                            "media": {
                                "id": 30,
                                "title": {
                                    "romaji": "Neon Genesis Evangelion",
                                    "english": "Neon Genesis Evangelion",
                                },
                                "startDate": {"year": 1995},
                                "format": "TV",
                            },
                            "score": 95,
                            "updatedAt": 1700000000,
                        },
                        {
                            "media": {
                                "id": 31,
                                "title": {"romaji": "Akira", "english": "Akira"},
                                "startDate": {"year": 1988},
                                "format": "MOVIE",
                            },
                            "score": 0,  # should be skipped
                            "updatedAt": 1700000001,
                        },
                    ]
                }
            ]
        },
        "mangaList": {
            "lists": [
                {
                    "entries": [
                        {
                            "media": {
                                "id": 100,
                                "title": {
                                    "romaji": "Berserk",
                                    "english": None,
                                },
                                "startDate": {"year": 1989},
                                "format": "MANGA",
                            },
                            "score": 100,
                            "updatedAt": 1700000002,
                        }
                    ]
                }
            ]
        },
    }
}

_TOKEN_BODY = {
    "token_type": "Bearer",
    "expires_in": None,
    "access_token": "anilist-access-token",
    "refresh_token": "anilist-refresh-token",
}


def _make_connection(access_token_bytes: bytes | None = b"fake-encrypted-token") -> MagicMock:
    conn = MagicMock()
    conn.access_token_encrypted = access_token_bytes
    conn.external_user_id = "12345"
    return conn


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_anilist_client_conforms_to_protocol() -> None:
    from syncup.ingest.anilist import AniListClient

    assert isinstance(
        AniListClient(
            client_id="x",
            client_secret="y",
            redirect_uri="http://localhost/callback",
        ),
        ServiceClient,
    )


def test_anilist_service_name() -> None:
    from syncup.ingest.anilist import AniListClient

    assert AniListClient.service_name == "anilist"


def test_anilist_refresh_token_returns_none() -> None:
    from syncup.ingest.anilist import AniListClient

    client = AniListClient(client_id="x", client_secret="y", redirect_uri="z")
    assert client.refresh_token(_make_connection()) is None


# ---------------------------------------------------------------------------
# get_authorize_url
# ---------------------------------------------------------------------------


def test_get_authorize_url_contains_client_id() -> None:
    from syncup.ingest.anilist import AniListClient

    url = AniListClient(
        client_id="my-client-id", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="abc123")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["client_id"] == "my-client-id"


def test_get_authorize_url_contains_redirect_uri() -> None:
    from syncup.ingest.anilist import AniListClient

    redirect = "http://127.0.0.1:3000/api/connect/anilist/oauth/callback"
    url = AniListClient(client_id="x", client_secret="s", redirect_uri=redirect).get_authorize_url(
        state="st"
    )
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["redirect_uri"] == redirect


def test_get_authorize_url_has_response_type_code() -> None:
    from syncup.ingest.anilist import AniListClient

    url = AniListClient(client_id="x", client_secret="s", redirect_uri="z").get_authorize_url(
        state="s"
    )
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["response_type"] == "code"


def test_get_authorize_url_includes_state() -> None:
    from syncup.ingest.anilist import AniListClient

    url = AniListClient(client_id="x", client_secret="s", redirect_uri="z").get_authorize_url(
        state="my-state-value"
    )
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["state"] == "my-state-value"


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


def test_exchange_code_returns_token_pair() -> None:
    c = _client([_json_resp(_TOKEN_BODY)])
    token_pair = c.exchange_code("auth-code")
    assert token_pair.access_token == "anilist-access-token"
    assert token_pair.refresh_token == "anilist-refresh-token"
    assert token_pair.expires_at is None


def test_exchange_code_http_error_raises_sync_client_error() -> None:
    c = _client([httpx.Response(400, json={"error": "invalid_grant"})])
    with pytest.raises(SyncClientError):
        c.exchange_code("bad-code")


def test_exchange_code_non_json_response_raises_sync_client_error() -> None:
    # AniList returns an HTML error page during outages — must not leak JSONDecodeError.
    c = _client([httpx.Response(200, content=b"<html>Internal Server Error</html>")])
    with pytest.raises(SyncClientError, match="invalid response"):
        c.exchange_code("any-code")


# ---------------------------------------------------------------------------
# fetch_me
# ---------------------------------------------------------------------------


def test_fetch_me_returns_viewer_dict() -> None:
    body = {"data": {"Viewer": {"id": 12345}}}
    c = _client([_json_resp(body)])
    result = c.fetch_me("access-token")
    assert result == {"id": 12345}


def test_fetch_me_graphql_error_raises_sync_client_error() -> None:
    error_body = {"errors": [{"message": "Unauthorized.", "status": 401}]}
    c = _client([_json_resp(error_body)])
    with pytest.raises(SyncClientError):
        c.fetch_me("bad-token")


# ---------------------------------------------------------------------------
# _graphql — 401 raises specific error
# ---------------------------------------------------------------------------


def test_graphql_401_raises_reconnect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([httpx.Response(401, json={"error": "Unauthorized"})])
    with pytest.raises(SyncClientError, match="reconnect"):
        c.fetch_items(_make_connection())


# ---------------------------------------------------------------------------
# context manager
# ---------------------------------------------------------------------------


def test_client_context_manager_closes_http() -> None:
    from syncup.ingest.anilist import AniListClient

    c = AniListClient(client_id="x", client_secret="y", redirect_uri="z")
    with c:
        pass
    assert c.http.is_closed


# ---------------------------------------------------------------------------
# fetch_items — happy path
# ---------------------------------------------------------------------------


def test_fetch_items_returns_anime_and_manga(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    assert len(items) == 2  # Evangelion (anime) + Berserk (manga); Akira skipped (score=0)


def test_fetch_items_skips_score_zero_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    names = {i["name"] for i in items}
    assert "Akira" not in names


def test_fetch_items_anime_has_correct_item_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert eva["item_type"] == "anime"


def test_fetch_items_manga_has_correct_item_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    berserk = next(i for i in items if i["name"] == "Berserk")
    assert berserk["item_type"] == "manga"


def test_fetch_items_raw_type_is_rating(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    assert all(i["raw_type"] == "rating" for i in items)


def test_fetch_items_normalizes_score_100_to_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    berserk = next(i for i in items if i["name"] == "Berserk")
    assert berserk["engagement_score"] == pytest.approx(1.0)


def test_fetch_items_normalizes_score_95_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert eva["engagement_score"] == pytest.approx(0.95)


def test_fetch_items_raw_value_preserves_original_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert eva["raw_value"] == pytest.approx(95.0)


def test_fetch_items_external_id_is_media_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert eva["external_id"] == "30"


def test_fetch_items_metadata_has_title_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert "title_normalized" in eva["metadata"]
    assert eva["metadata"]["title_normalized"] == "neon genesis evangelion"


def test_fetch_items_metadata_has_release_year(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert eva["metadata"]["release_year"] == 1995


def test_fetch_items_metadata_has_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert eva["metadata"]["format"] == "TV"


def test_fetch_items_last_engaged_at_from_updated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    expected = datetime.fromtimestamp(1700000000, UTC)
    assert eva["last_engaged_at"] == expected


def test_fetch_items_falls_back_to_romaji_when_english_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    berserk = next(i for i in items if "Berserk" in i["name"])
    assert berserk["name"] == "Berserk"


# ---------------------------------------------------------------------------
# fetch_items — edge cases
# ---------------------------------------------------------------------------


def test_fetch_items_missing_release_year_stored_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    body = {
        "data": {
            "Viewer": {"id": 1, "mediaListOptions": {"scoreFormat": "POINT_100"}},
            "animeList": {
                "lists": [
                    {
                        "entries": [
                            {
                                "media": {
                                    "id": 999,
                                    "title": {"romaji": "Unknown", "english": None},
                                    "startDate": {"year": None},
                                    "format": "TV",
                                },
                                "score": 80,
                                "updatedAt": 0,
                            }
                        ]
                    }
                ]
            },
            "mangaList": {"lists": []},
        }
    }
    c = _client([_json_resp(body)])
    items = c.fetch_items(_make_connection())
    assert items[0]["metadata"]["release_year"] == 0


def test_fetch_items_normalizes_point_10_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    body = {
        "data": {
            "Viewer": {"id": 1, "mediaListOptions": {"scoreFormat": "POINT_10"}},
            "animeList": {
                "lists": [
                    {
                        "entries": [
                            {
                                "media": {
                                    "id": 1,
                                    "title": {"romaji": "Test", "english": "Test"},
                                    "startDate": {"year": 2020},
                                    "format": "TV",
                                },
                                "score": 9,
                                "updatedAt": 0,
                            }
                        ]
                    }
                ]
            },
            "mangaList": {"lists": []},
        }
    }
    c = _client([_json_resp(body)])
    items = c.fetch_items(_make_connection())
    assert items[0]["engagement_score"] == pytest.approx(0.9)


def test_fetch_items_empty_lists_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    body = {
        "data": {
            "Viewer": {"id": 1, "mediaListOptions": {"scoreFormat": "POINT_100"}},
            "animeList": {"lists": []},
            "mangaList": {"lists": []},
        }
    }
    c = _client([_json_resp(body)])
    items = c.fetch_items(_make_connection())
    assert items == []


# ---------------------------------------------------------------------------
# fetch_items — error cases
# ---------------------------------------------------------------------------


def test_fetch_items_missing_access_token_raises_sync_client_error() -> None:
    from syncup.ingest.anilist import AniListClient

    client = AniListClient(client_id="x", client_secret="y", redirect_uri="z")
    conn = _make_connection(access_token_bytes=None)
    with pytest.raises(SyncClientError, match="Missing access token"):
        client.fetch_items(conn)


def test_fetch_items_graphql_error_raises_sync_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    error_body = {"errors": [{"message": "Not Found.", "status": 404}]}
    c = _client([_json_resp(error_body)])
    with pytest.raises(SyncClientError):
        c.fetch_items(_make_connection())


def test_fetch_items_http_error_raises_sync_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([httpx.Response(429, json={"error": "too many requests"})])
    with pytest.raises(SyncClientError):
        c.fetch_items(_make_connection())


# ---------------------------------------------------------------------------
# I1 — SyncClientError messages must not leak exc.response.text or exc repr
# ---------------------------------------------------------------------------


def test_graphql_http_error_message_does_not_leak_response_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_graphql HTTPStatusError must not forward upstream body in SyncClientError."""
    sensitive = "secret_anilist_body_XYZ"
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    c = _client([httpx.Response(500, text=sensitive)])
    with pytest.raises(SyncClientError) as exc_info:
        c.fetch_items(_make_connection())
    assert sensitive not in str(exc_info.value), "Upstream body must not appear in SyncClientError"


def test_exchange_code_http_error_message_does_not_leak_response_body() -> None:
    """exchange_code HTTPStatusError must not forward upstream body in SyncClientError."""
    sensitive = "secret_token_body_XYZ"
    from syncup.ingest.anilist import AniListClient

    c = AniListClient(
        client_id="x",
        client_secret="y",
        redirect_uri="z",
        http=httpx.Client(transport=_SequenceTransport([httpx.Response(400, text=sensitive)])),
    )
    with pytest.raises(SyncClientError) as exc_info:
        c.exchange_code("code")
    assert sensitive not in str(exc_info.value), "Upstream body must not appear in SyncClientError"


def test_graphql_request_error_message_does_not_leak_exception_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_graphql RequestError must not forward internal exc repr in SyncClientError."""
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")

    class _ErrorTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("internal-host-xyz:5432 connection refused")

    from syncup.ingest.anilist import AniListClient

    c = AniListClient(
        client_id="x",
        client_secret="y",
        redirect_uri="z",
        http=httpx.Client(transport=_ErrorTransport()),
    )
    with pytest.raises(SyncClientError) as exc_info:
        c.fetch_items(_make_connection())
    assert "internal-host-xyz" not in str(exc_info.value), (
        "Internal hostname must not appear in SyncClientError"
    )


# ---------------------------------------------------------------------------
# Block B — genres field in metadata (Phase 2 AniList fix)
# ---------------------------------------------------------------------------


def test_fetch_items_metadata_has_genres_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """genres must be stored in metadata after fetch_items."""
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    body = {
        "data": {
            "Viewer": {"id": 1, "mediaListOptions": {"scoreFormat": "POINT_100"}},
            "animeList": {
                "lists": [
                    {
                        "entries": [
                            {
                                "media": {
                                    "id": 30,
                                    "title": {
                                        "romaji": "Neon Genesis Evangelion",
                                        "english": "Neon Genesis Evangelion",
                                    },
                                    "startDate": {"year": 1995},
                                    "format": "TV",
                                    "genres": ["Mecha", "Psychological", "Drama"],
                                },
                                "score": 95,
                                "updatedAt": 1700000000,
                            }
                        ]
                    }
                ]
            },
            "mangaList": {"lists": []},
        }
    }
    c = _client([_json_resp(body)])
    items = c.fetch_items(_make_connection())
    eva = next(i for i in items if i["name"] == "Neon Genesis Evangelion")
    assert "genres" in eva["metadata"], "genres must be present in metadata"
    assert eva["metadata"]["genres"] == ["Mecha", "Psychological", "Drama"]


def test_fetch_items_genres_empty_list_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """When genres is missing from the API response, metadata['genres'] should be []."""
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    # Use the existing _COMBINED_BODY which has no genres field
    c = _client([_json_resp(_COMBINED_BODY)])
    items = c.fetch_items(_make_connection())
    for item in items:
        assert "genres" in item["metadata"], "genres key must always be present"
        assert isinstance(item["metadata"]["genres"], list)


def test_fetch_items_manga_genres_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    """genres must also be stored for manga entries."""
    monkeypatch.setattr("syncup.ingest.anilist.decrypt_token", lambda _: "tok")
    body = {
        "data": {
            "Viewer": {"id": 1, "mediaListOptions": {"scoreFormat": "POINT_100"}},
            "animeList": {"lists": []},
            "mangaList": {
                "lists": [
                    {
                        "entries": [
                            {
                                "media": {
                                    "id": 100,
                                    "title": {"romaji": "Berserk", "english": None},
                                    "startDate": {"year": 1989},
                                    "format": "MANGA",
                                    "genres": ["Fantasy", "Dark Fantasy"],
                                },
                                "score": 100,
                                "updatedAt": 1700000002,
                            }
                        ]
                    }
                ]
            },
        }
    }
    c = _client([_json_resp(body)])
    items = c.fetch_items(_make_connection())
    berserk = next(i for i in items if "Berserk" in i["name"])
    assert berserk["metadata"]["genres"] == ["Fantasy", "Dark Fantasy"]
