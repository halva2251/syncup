"""Tests for GET /api/onboarding/status."""
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
        "display_name": "Test User",
        "is_matchable": False,
        "onboarded": False,
        "languages": None,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})



def _counts(ok_connections: int, obsessions: int) -> list[int]:
    """Return scalar count values in route query order: connections first, obsessions second."""
    return [ok_connections, obsessions]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Unauthenticated client — verifies 401 behaviour."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


def _make_ob_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    user: User,
    ok_connections: int,
    obsessions: int,
) -> Generator[TestClient, None, None]:
    """Authenticated client with configurable DB state (counts, not objects)."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    mock_db.scalar.side_effect = _counts(ok_connections, obsessions)

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def ob_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Default authenticated client: no connections, no obsessions, not matchable."""
    yield from _make_ob_client(
        monkeypatch, mock_db, _make_user(), ok_connections=0, obsessions=0
    )


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_onboarding_status_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/onboarding/status")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_onboarding_status_returns_all_fields(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_display_name" in data
    assert "has_languages" in data
    assert "has_connection_or_obsessions" in data
    assert "has_taste_data" in data
    assert "has_set_matchable" in data
    assert "next_step" in data


# ---------------------------------------------------------------------------
# has_display_name — always true (NOT NULL at signup)
# ---------------------------------------------------------------------------


def test_has_display_name_is_always_true(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.json()["has_display_name"] is True


# ---------------------------------------------------------------------------
# has_languages
# ---------------------------------------------------------------------------


def test_has_languages_false_when_null(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.json()["has_languages"] is False


def test_has_languages_true_when_set(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    user = _make_user(languages=["en", "fi"])
    for c in _make_ob_client(monkeypatch, mock_db, user, ok_connections=0, obsessions=0):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_languages"] is True


# ---------------------------------------------------------------------------
# has_connection_or_obsessions
# ---------------------------------------------------------------------------


def test_no_connections_no_obsessions_is_false(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.json()["has_connection_or_obsessions"] is False


def test_one_ok_connection_is_true(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(
        monkeypatch, mock_db, _make_user(), ok_connections=1, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_connection_or_obsessions"] is True


def test_pending_connection_does_not_count(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    """Only ok-status connections count — the route queries status='ok'."""
    for c in _make_ob_client(
        monkeypatch, mock_db, _make_user(), ok_connections=0, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_connection_or_obsessions"] is False


def test_three_obsessions_is_true(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(monkeypatch, mock_db, _make_user(), ok_connections=0, obsessions=3):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_connection_or_obsessions"] is True


def test_two_obsessions_is_false(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(monkeypatch, mock_db, _make_user(), ok_connections=0, obsessions=2):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_connection_or_obsessions"] is False


def test_four_obsessions_is_true(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(monkeypatch, mock_db, _make_user(), ok_connections=0, obsessions=4):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_connection_or_obsessions"] is True


def test_connection_and_zero_obsessions_is_true(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(
        monkeypatch, mock_db, _make_user(), ok_connections=1, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_connection_or_obsessions"] is True


# ---------------------------------------------------------------------------
# has_taste_data — derived from has_connection_or_obsessions
# ---------------------------------------------------------------------------


def test_has_taste_data_false_when_no_data(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.json()["has_taste_data"] is False


def test_has_taste_data_true_when_has_connection(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(
        monkeypatch, mock_db, _make_user(), ok_connections=1, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_taste_data"] is True


# ---------------------------------------------------------------------------
# has_set_matchable
# ---------------------------------------------------------------------------


def test_has_set_matchable_false_by_default(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.json()["has_set_matchable"] is False


def test_has_set_matchable_true_when_matchable(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    user = _make_user(is_matchable=True)
    for c in _make_ob_client(
        monkeypatch, mock_db, user, ok_connections=1, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["has_set_matchable"] is True


# ---------------------------------------------------------------------------
# next_step
# ---------------------------------------------------------------------------


def test_next_step_connect_service_when_no_data(ob_client: TestClient) -> None:
    resp = ob_client.get("/api/onboarding/status")
    assert resp.json()["next_step"] == "connect_service"


def test_next_step_set_matchable_when_has_connection(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(
        monkeypatch, mock_db, _make_user(), ok_connections=1, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["next_step"] == "set_matchable"


def test_next_step_set_matchable_when_three_obsessions(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    for c in _make_ob_client(monkeypatch, mock_db, _make_user(), ok_connections=0, obsessions=3):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["next_step"] == "set_matchable"


def test_next_step_null_when_fully_onboarded(
    monkeypatch: pytest.MonkeyPatch, mock_db: MagicMock
) -> None:
    user = _make_user(is_matchable=True)
    for c in _make_ob_client(
        monkeypatch, mock_db, user, ok_connections=1, obsessions=0
    ):
        resp = c.get("/api/onboarding/status")
        assert resp.json()["next_step"] is None
