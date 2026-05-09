"""Tests for RedditClient — OAuth client, Protocol conformance, fetch_items."""
from __future__ import annotations

import math
import urllib.parse
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


def _json_resp(body: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


def _client(responses: list[httpx.Response]):  # type: ignore[return]
    from syncup.ingest.reddit import RedditClient

    transport = _SequenceTransport(responses)
    http = httpx.Client(transport=transport)
    return RedditClient(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://127.0.0.1:3000/api/connect/reddit/oauth/callback",
        http=http,
    )


def _make_connection(
    access_token_bytes: bytes | None = b"fake-encrypted-token",
    refresh_token_bytes: bytes | None = b"fake-encrypted-refresh",
) -> MagicMock:
    conn = MagicMock()
    conn.access_token_encrypted = access_token_bytes
    conn.refresh_token_encrypted = refresh_token_bytes
    conn.external_user_id = "testuser"
    return conn


# ---------------------------------------------------------------------------
# Canned API responses
# ---------------------------------------------------------------------------

_TOKEN_BODY = {
    "access_token": "reddit-access-token",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_token": "reddit-refresh-token",
    "scope": "identity mysubreddits",
}

_ME_BODY = {
    "name": "halva2251",
    "id": "abc123",
    "icon_img": "https://example.com/avatar.png",
    "total_karma": 1337,
}

# Niche communities: low subscriber counts
_SUBREDDITS_PAGE_1 = {
    "data": {
        "children": [
            {
                "kind": "t5",
                "data": {
                    "id": "2qh3l",
                    "display_name": "haskell",
                    "subscribers": 80_000,
                    "public_description": "The Haskell programming language community.",
                },
            },
            {
                "kind": "t5",
                "data": {
                    "id": "2qh1i",
                    "display_name": "emacs",
                    "subscribers": 50_000,
                    "public_description": "The extensible self-documenting text editor.",
                },
            },
        ],
        "after": "t5_next_cursor",
        "before": None,
    }
}

_SUBREDDITS_PAGE_2 = {
    "data": {
        "children": [
            {
                "kind": "t5",
                "data": {
                    "id": "2qh0u",
                    "display_name": "neovim",
                    "subscribers": 120_000,
                    "public_description": "Vim-fork focused on extensibility and usability.",
                },
            },
        ],
        "after": None,
        "before": None,
    }
}

# One mainstream community that should be filtered out
_SUBREDDITS_WITH_MAINSTREAM = {
    "data": {
        "children": [
            {
                "kind": "t5",
                "data": {
                    "id": "2qh3l",
                    "display_name": "haskell",
                    "subscribers": 80_000,
                    "public_description": "Haskell",
                },
            },
            {
                "kind": "t5",
                "data": {
                    "id": "2qh0u",
                    "display_name": "gaming",
                    "subscribers": 2_000_000,  # > 1M — must be filtered
                    "public_description": "Gaming community",
                },
            },
        ],
        "after": None,
        "before": None,
    }
}

_SUBREDDITS_SINGLE = {
    "data": {
        "children": [
            {
                "kind": "t5",
                "data": {
                    "id": "2qh3l",
                    "display_name": "haskell",
                    "subscribers": 80_000,
                    "public_description": "Haskell",
                },
            },
        ],
        "after": None,
        "before": None,
    }
}

_SUBREDDITS_EMPTY = {
    "data": {
        "children": [],
        "after": None,
        "before": None,
    }
}


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_reddit_client_conforms_to_protocol() -> None:
    from syncup.ingest.reddit import RedditClient

    assert isinstance(
        RedditClient(
            client_id="x",
            client_secret="y",
            redirect_uri="http://localhost/callback",
        ),
        ServiceClient,
    )


def test_reddit_service_name() -> None:
    from syncup.ingest.reddit import RedditClient

    assert RedditClient.service_name == "reddit"


# ---------------------------------------------------------------------------
# get_authorize_url
# ---------------------------------------------------------------------------


def test_get_authorize_url_contains_client_id() -> None:
    from syncup.ingest.reddit import RedditClient

    url = RedditClient(
        client_id="my-client-id", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="abc123")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["client_id"] == "my-client-id"


def test_get_authorize_url_contains_redirect_uri() -> None:
    from syncup.ingest.reddit import RedditClient

    redirect = "http://127.0.0.1:3000/api/connect/reddit/oauth/callback"
    url = RedditClient(
        client_id="x", client_secret="s", redirect_uri=redirect
    ).get_authorize_url(state="xyz")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["redirect_uri"] == redirect


def test_get_authorize_url_contains_state() -> None:
    from syncup.ingest.reddit import RedditClient

    url = RedditClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="random-state-xyz")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["state"] == "random-state-xyz"


def test_get_authorize_url_points_to_reddit() -> None:
    from syncup.ingest.reddit import RedditClient

    url = RedditClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="s")
    assert "reddit.com" in url


def test_get_authorize_url_response_type_code() -> None:
    from syncup.ingest.reddit import RedditClient

    url = RedditClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="s")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["response_type"] == "code"


def test_get_authorize_url_duration_permanent() -> None:
    """duration=permanent is required to receive a refresh token."""
    from syncup.ingest.reddit import RedditClient

    url = RedditClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="s")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["duration"] == "permanent"


def test_get_authorize_url_includes_scopes() -> None:
    from syncup.ingest.reddit import RedditClient

    url = RedditClient(
        client_id="x", client_secret="s", redirect_uri="http://localhost/cb"
    ).get_authorize_url(state="s")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert "identity" in params["scope"]
    assert "mysubreddits" in params["scope"]


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


def test_exchange_code_returns_token_pair() -> None:
    client = _client([_json_resp(_TOKEN_BODY)])

    from syncup.ingest.protocol import TokenPair

    result = client.exchange_code("some-code")
    assert isinstance(result, TokenPair)
    assert result.access_token == "reddit-access-token"
    assert result.refresh_token == "reddit-refresh-token"


def test_exchange_code_sets_expires_at() -> None:
    client = _client([_json_resp(_TOKEN_BODY)])
    result = client.exchange_code("some-code")
    assert result.expires_at is not None


def test_exchange_code_raises_on_http_error() -> None:
    client = _client([_json_resp({"error": "invalid_grant"}, status=400)])
    with pytest.raises(SyncClientError, match="Reddit token exchange failed"):
        client.exchange_code("bad-code")


def test_exchange_code_raises_on_request_error() -> None:
    from syncup.ingest.reddit import RedditClient

    class _FailTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no network")

    http = httpx.Client(transport=_FailTransport())
    client = RedditClient(client_id="x", client_secret="y", redirect_uri="z", http=http)
    with pytest.raises(SyncClientError, match="Could not reach Reddit"):
        client.exchange_code("code")


def test_exchange_code_non_json_response_raises_sync_client_error() -> None:
    client = _client([httpx.Response(200, content=b"<html>Service Unavailable</html>")])
    with pytest.raises(SyncClientError, match="invalid token response"):
        client.exchange_code("code")


# ---------------------------------------------------------------------------
# fetch_me
# ---------------------------------------------------------------------------


def test_fetch_me_returns_username() -> None:
    client = _client([_json_resp(_ME_BODY)])
    result = client.fetch_me("access-token")
    assert result["name"] == "halva2251"


def test_fetch_me_raises_on_http_error() -> None:
    client = _client([_json_resp({"message": "Unauthorized"}, status=401)])
    with pytest.raises(SyncClientError):
        client.fetch_me("bad-token")


def test_fetch_me_raises_on_request_error() -> None:
    from syncup.ingest.reddit import RedditClient

    class _FailTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no network")

    http = httpx.Client(transport=_FailTransport())
    client = RedditClient(client_id="x", client_secret="y", redirect_uri="z", http=http)
    with pytest.raises(SyncClientError, match="Could not reach Reddit"):
        client.fetch_me("token")


def test_fetch_me_non_json_response_raises_sync_client_error() -> None:
    client = _client([httpx.Response(200, content=b"<html>Service Unavailable</html>")])
    with pytest.raises(SyncClientError, match="invalid profile response"):
        client.fetch_me("token")


# ---------------------------------------------------------------------------
# fetch_items
# ---------------------------------------------------------------------------


def test_fetch_items_returns_subreddits(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two pages: page 1 has 2 subs, page 2 has 1 sub
    client = _client([_json_resp(_SUBREDDITS_PAGE_1), _json_resp(_SUBREDDITS_PAGE_2)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert len(items) == 3


def test_fetch_items_item_type_is_community(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert all(i["item_type"] == "community" for i in items)


def test_fetch_items_raw_type_is_consumption(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert all(i["raw_type"] == "consumption" for i in items)


def test_fetch_items_names_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_PAGE_1), _json_resp(_SUBREDDITS_PAGE_2)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    names = {i["name"] for i in items}
    assert "haskell" in names
    assert "emacs" in names
    assert "neovim" in names


def test_fetch_items_filters_mainstream_subreddits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subreddits with > 1M subscribers must be excluded."""
    client = _client([_json_resp(_SUBREDDITS_WITH_MAINSTREAM)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    names = {i["name"] for i in items}
    assert "haskell" in names
    assert "gaming" not in names


def test_fetch_items_exactly_1m_subscribers_included(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly 1M subscribers is the boundary — must be included."""
    boundary_page = {
        "data": {
            "children": [
                {
                    "kind": "t5",
                    "data": {
                        "id": "abc",
                        "display_name": "boundary_sub",
                        "subscribers": 1_000_000,
                        "public_description": "",
                    },
                }
            ],
            "after": None,
            "before": None,
        }
    }
    client = _client([_json_resp(boundary_page)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert len(items) == 1
    assert items[0]["name"] == "boundary_sub"


def test_fetch_items_engagement_score_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most niche subreddit (smallest subs) should have engagement_score == 1.0."""
    client = _client([_json_resp(_SUBREDDITS_PAGE_1), _json_resp(_SUBREDDITS_PAGE_2)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())

    # emacs has fewest subscribers (50K) → highest raw_value → score 1.0
    emacs = next(i for i in items if i["name"] == "emacs")
    assert emacs["engagement_score"] == pytest.approx(1.0)


def test_fetch_items_engagement_score_within_range(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_PAGE_1), _json_resp(_SUBREDDITS_PAGE_2)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    for item in items:
        assert 0.0 < item["engagement_score"] <= 1.0


def test_fetch_items_raw_value_uses_natural_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """raw_value must equal 1 / math.log(subscribers + 2)."""
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    item = items[0]
    expected_raw = 1.0 / math.log(80_000 + 2)
    assert item["raw_value"] == pytest.approx(expected_raw)


def test_fetch_items_single_subreddit_score_is_1(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert len(items) == 1
    assert items[0]["engagement_score"] == pytest.approx(1.0)


def test_fetch_items_metadata_has_subreddit_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items[0]["metadata"]["subreddit_name"] == "haskell"


def test_fetch_items_metadata_has_subscribers(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items[0]["metadata"]["subscribers"] == 80_000


def test_fetch_items_metadata_has_description(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items[0]["metadata"]["description"] == "Haskell"


def test_fetch_items_description_truncated_to_200_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    long_desc = "x" * 300
    page = {
        "data": {
            "children": [
                {
                    "kind": "t5",
                    "data": {
                        "id": "abc",
                        "display_name": "longsub",
                        "subscribers": 10_000,
                        "public_description": long_desc,
                    },
                }
            ],
            "after": None,
            "before": None,
        }
    }
    client = _client([_json_resp(page)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert len(items[0]["metadata"]["description"]) == 200


def test_fetch_items_external_id_is_subreddit_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items[0]["external_id"] == "2qh3l"


def test_fetch_items_last_engaged_at_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_SINGLE)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items[0]["last_engaged_at"] is None


def test_fetch_items_empty_subscriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_SUBREDDITS_EMPTY)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items == []


def test_fetch_items_zero_subscriber_subreddit_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subreddits with 0 subscribers (private/banned) carry no taste signal."""
    zero_sub_page = {
        "data": {
            "children": [
                {
                    "kind": "t5",
                    "data": {
                        "id": "abc",
                        "display_name": "private_sub",
                        "subscribers": 0,
                        "public_description": "Private community",
                    },
                },
                {
                    "kind": "t5",
                    "data": {
                        "id": "def",
                        "display_name": "haskell",
                        "subscribers": 80_000,
                        "public_description": "Haskell",
                    },
                },
            ],
            "after": None,
            "before": None,
        }
    }
    client = _client([_json_resp(zero_sub_page)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    names = {i["name"] for i in items}
    assert "private_sub" not in names
    assert "haskell" in names


def test_fetch_items_all_mainstream_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    all_big = {
        "data": {
            "children": [
                {
                    "kind": "t5",
                    "data": {
                        "id": "abc",
                        "display_name": "gaming",
                        "subscribers": 5_000_000,
                        "public_description": "",
                    },
                }
            ],
            "after": None,
            "before": None,
        }
    }
    client = _client([_json_resp(all_big)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    assert items == []


def test_fetch_items_raises_on_missing_token() -> None:
    from syncup.ingest.reddit import RedditClient

    client = RedditClient(client_id="x", client_secret="y", redirect_uri="z")
    with pytest.raises(SyncClientError, match="Missing access token"):
        client.fetch_items(_make_connection(access_token_bytes=None))


def test_fetch_items_raises_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp({"message": "Unauthorized"}, status=401)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    with pytest.raises(SyncClientError, match="reconnect"):
        client.fetch_items(_make_connection())


def test_fetch_items_raises_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from syncup.ingest.reddit import RedditClient

    class _FailTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no network")

    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")
    http = httpx.Client(transport=_FailTransport())
    client = RedditClient(client_id="x", client_secret="y", redirect_uri="z", http=http)

    with pytest.raises(SyncClientError, match="Could not reach Reddit"):
        client.fetch_items(_make_connection())


def test_fetch_items_paginates_until_no_after(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_items must follow the `after` cursor and stop when it's None."""
    client = _client([_json_resp(_SUBREDDITS_PAGE_1), _json_resp(_SUBREDDITS_PAGE_2)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "access-token")

    items = client.fetch_items(_make_connection())
    # Page 1 has 2 subs, page 2 has 1 sub → 3 total
    assert len(items) == 3


# ---------------------------------------------------------------------------
# refresh_token
# ---------------------------------------------------------------------------


def test_refresh_token_returns_new_token_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp(_TOKEN_BODY)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "refresh-token")

    from syncup.ingest.protocol import TokenPair

    result = client.refresh_token(_make_connection())
    assert isinstance(result, TokenPair)
    assert result.access_token == "reddit-access-token"
    assert result.refresh_token == "reddit-refresh-token"
    assert result.expires_at is not None


def test_refresh_token_raises_on_missing_refresh_token() -> None:
    from syncup.ingest.reddit import RedditClient

    client = RedditClient(client_id="x", client_secret="y", redirect_uri="z")
    with pytest.raises(SyncClientError, match="Missing refresh token"):
        client.refresh_token(_make_connection(refresh_token_bytes=None))


def test_refresh_token_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client([_json_resp({"error": "invalid_grant"}, status=400)])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "refresh-token")

    with pytest.raises(SyncClientError, match="Reddit token refresh failed"):
        client.refresh_token(_make_connection())


def test_refresh_token_non_json_response_raises_sync_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client([httpx.Response(200, content=b"<html>Service Unavailable</html>")])
    monkeypatch.setattr("syncup.ingest.reddit.decrypt_token", lambda _: "refresh-token")
    with pytest.raises(SyncClientError, match="invalid token response"):
        client.refresh_token(_make_connection())


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager_closes_http() -> None:
    from syncup.ingest.reddit import RedditClient

    http = MagicMock()
    http.close = MagicMock()
    client = RedditClient(client_id="x", client_secret="y", redirect_uri="z", http=http)
    with client:
        pass
    http.close.assert_called_once()
