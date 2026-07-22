"""Tests for PATCH /api/me — profile edit."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import User

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _make_user(**kwargs: object) -> User:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "email": "me@example.com",
        "display_name": "Old Name",
        "bio": None,
        "discord_handle": None,
        "avatar_url": None,
        "is_matchable": False,
        "onboarded": False,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Unauthenticated client."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def patch_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[tuple[TestClient, User], None, None]:
    """Authenticated client; yields (client, fake_user) so tests can inspect pre-patch state."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c, fake_user
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_patch_me_requires_auth(client: TestClient) -> None:
    resp = client.patch("/api/me", json={"display_name": "Alex"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Happy path — single field updates
# ---------------------------------------------------------------------------


def test_patch_me_updates_display_name(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"display_name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "New Name"


def test_patch_me_updates_is_matchable(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"is_matchable": True})
    assert resp.status_code == 200
    assert resp.json()["is_matchable"] is True


def test_patch_me_updates_bio(patch_client: tuple[TestClient, User]) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"bio": "I love Disco Elysium"})
    assert resp.status_code == 200
    assert resp.json()["bio"] == "I love Disco Elysium"


def test_patch_me_updates_discord_handle(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"discord_handle": "halva#1234"})
    assert resp.status_code == 200
    assert resp.json()["discord_handle"] == "halva#1234"


def test_patch_me_updates_social_links(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch(
        "/api/me",
        json={"social_links": {"github": "https://github.com/syncup"}},
    )
    assert resp.status_code == 200
    assert resp.json()["social_links"] == {"github": "https://github.com/syncup"}


def test_patch_me_updates_avatar_url(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"avatar_url": "https://example.com/avatar.png"})
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "https://example.com/avatar.png"


# ---------------------------------------------------------------------------
# Happy path — multiple fields + omission behaviour
# ---------------------------------------------------------------------------


def test_patch_me_updates_multiple_fields(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch(
        "/api/me",
        json={"display_name": "Alex", "bio": "gamer", "is_matchable": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Alex"
    assert body["bio"] == "gamer"
    assert body["is_matchable"] is True


def test_patch_me_omitted_fields_are_unchanged(
    patch_client: tuple[TestClient, User],
) -> None:
    c, user = patch_client
    user.bio = "original bio"
    user.discord_handle = "old#0000"

    resp = c.patch("/api/me", json={"is_matchable": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["bio"] == "original bio"
    assert body["discord_handle"] == "old#0000"
    assert body["is_matchable"] is True


def test_patch_me_empty_body_is_noop(
    patch_client: tuple[TestClient, User],
    mock_db: MagicMock,
) -> None:
    c, user = patch_client
    resp = c.patch("/api/me", json={})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == user.display_name
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Clearing nullable fields to null
# ---------------------------------------------------------------------------


def test_patch_me_clears_bio_to_null(
    patch_client: tuple[TestClient, User],
) -> None:
    c, user = patch_client
    user.bio = "something"
    resp = c.patch("/api/me", json={"bio": None})
    assert resp.status_code == 200
    assert resp.json()["bio"] is None


def test_patch_me_clears_discord_handle_to_null(
    patch_client: tuple[TestClient, User],
) -> None:
    c, user = patch_client
    user.discord_handle = "old#0000"
    resp = c.patch("/api/me", json={"discord_handle": None})
    assert resp.status_code == 200
    assert resp.json()["discord_handle"] is None


def test_patch_me_clears_avatar_url_to_null(
    patch_client: tuple[TestClient, User],
) -> None:
    c, user = patch_client
    user.avatar_url = "https://old.example.com/avatar.png"
    resp = c.patch("/api/me", json={"avatar_url": None})
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] is None


# ---------------------------------------------------------------------------
# Response shape — new fields exposed
# ---------------------------------------------------------------------------


def test_patch_me_response_includes_all_profile_fields(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"bio": "hi"})
    assert resp.status_code == 200
    body = resp.json()
    assert "avatar_url" in body
    assert "bio" in body
    assert "discord_handle" in body
    assert "display_name" in body
    assert "is_matchable" in body
    assert "languages" in body
    assert "id" in body
    assert "email" in body
    assert "created_at" in body


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


def test_patch_me_updates_languages(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"languages": ["en", "de"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["languages"] == ["de", "en"]


def test_patch_me_clears_languages_to_null(
    patch_client: tuple[TestClient, User],
) -> None:
    c, user = patch_client
    user.languages = ["en", "fr"]
    resp = c.patch("/api/me", json={"languages": None})
    assert resp.status_code == 200
    assert resp.json()["languages"] is None


def test_patch_me_normalizes_language_case(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"languages": ["EN", " De "]})
    assert resp.status_code == 200
    assert resp.json()["languages"] == ["de", "en"]


def test_patch_me_deduplicates_languages(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"languages": ["en", "en", "de"]})
    assert resp.status_code == 200
    assert resp.json()["languages"] == ["de", "en"]


def test_patch_me_invalid_language_code_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"languages": ["en", "klingon"]})
    assert resp.status_code == 422


def test_patch_me_too_many_languages_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"languages": ["en", "de", "fr", "es", "it", "pt", "ru", "zh", "ja", "ko", "hi"]})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_patch_me_empty_display_name_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"display_name": ""})
    assert resp.status_code == 422


def test_patch_me_display_name_too_long_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"display_name": "x" * 201})
    assert resp.status_code == 422


def test_patch_me_bio_too_long_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"bio": "x" * 501})
    assert resp.status_code == 422


def test_patch_me_discord_handle_too_long_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"discord_handle": "x" * 101})
    assert resp.status_code == 422


def test_patch_me_rejects_social_link_on_wrong_host(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch(
        "/api/me",
        json={"social_links": {"github": "https://example.com/syncup"}},
    )
    assert resp.status_code == 422


def test_patch_me_avatar_url_too_long_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"avatar_url": "x" * 501})
    assert resp.status_code == 422


def test_patch_me_is_matchable_non_bool_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    c, _ = patch_client
    resp = c.patch("/api/me", json={"is_matchable": "yes"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# A4 — whitespace validation on string fields
# ---------------------------------------------------------------------------


def test_patch_me_whitespace_display_name_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    """A4: display_name of only whitespace must be rejected."""
    c, _ = patch_client
    resp = c.patch("/api/me", json={"display_name": "   "})
    assert resp.status_code == 422


def test_patch_me_whitespace_bio_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    """A4: bio of only whitespace must be rejected (use null to clear it)."""
    c, _ = patch_client
    resp = c.patch("/api/me", json={"bio": "   "})
    assert resp.status_code == 422


def test_patch_me_whitespace_discord_handle_returns_422(
    patch_client: tuple[TestClient, User],
) -> None:
    """A4: discord_handle of only whitespace must be rejected."""
    c, _ = patch_client
    resp = c.patch("/api/me", json={"discord_handle": "   "})
    assert resp.status_code == 422


def test_patch_me_display_name_is_stripped(
    patch_client: tuple[TestClient, User],
) -> None:
    """A4: leading/trailing whitespace is stripped from display_name."""
    c, _ = patch_client
    resp = c.patch("/api/me", json={"display_name": "  Alice  "})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Alice"
