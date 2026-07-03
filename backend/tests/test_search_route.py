"""Tests for GET /api/items/search."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from syncup.db.models import User


@pytest.fixture
def authed_search_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth

    now = datetime.now(UTC)
    fake_user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        display_name="Tester",
        is_matchable=False,
        onboarded=False,
        created_at=now,
        updated_at=now,
    )

    try:
        app.dependency_overrides[require_auth] = lambda: fake_user
        with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
            with TestClient(app, follow_redirects=False) as c:
                yield c
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.fixture(autouse=True)
def _clear_search_cache() -> None:
    from syncup.ingest.search.registry import clear_cache

    clear_cache()


def test_search_requires_auth(authed_search_client: TestClient) -> None:
    # Dependency override is active, so removing it simulates an unauthenticated request.
    from syncup.api.app import app
    from syncup.auth.router import require_auth

    app.dependency_overrides.pop(require_auth, None)
    resp = authed_search_client.get("/api/items/search?q=disco&category=game")
    assert resp.status_code == 401
    app.dependency_overrides[require_auth] = lambda: None


def test_search_returns_suggestions(authed_search_client: TestClient) -> None:
    from syncup.ingest.search.registry import SearchConfig, set_default_config

    body = {
        "items": [
            {"id": 632470, "name": "Disco Elysium", "is_free": False},
        ]
    }
    from tests.http_helpers import json_response, make_http

    config = SearchConfig(http=make_http([json_response(body)]))
    set_default_config(config)

    resp = authed_search_client.get("/api/items/search?q=disco&category=game")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Disco Elysium"
    assert data["items"][0]["service"] == "steam"
    assert data["items"][0]["item_type"] == "game"


def test_search_validates_category(authed_search_client: TestClient) -> None:
    resp = authed_search_client.get("/api/items/search?q=disco&category=invalid")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_validates_limit_range(authed_search_client: TestClient) -> None:
    resp = authed_search_client.get("/api/items/search?q=disco&category=game&limit=100")
    assert resp.status_code == 422


def test_search_validates_query_min_length(authed_search_client: TestClient) -> None:
    resp = authed_search_client.get("/api/items/search?q=&category=game")
    assert resp.status_code == 422


def test_search_empty_result_for_unsupported_category(
    authed_search_client: TestClient,
) -> None:
    resp = authed_search_client.get("/api/items/search?q=anything&category=community")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
