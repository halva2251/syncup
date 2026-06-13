"""Tests for Steam OpenID connect routes:
GET /api/connect/steam/openid/start
GET /api/connect/steam/openid/callback
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import User


def _make_user(**kwargs: object) -> User:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "display_name": "Test User",
        "is_matchable": False,
        "onboarded": False,
        "created_at": now,
        "updated_at": now,
    }
    return User(**{**defaults, **kwargs})


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def steam_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("STEAM_API_KEY", "test-steam-key")
    monkeypatch.setenv("FRONTEND_URL", "")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setattr(
        "syncup.api.routes.connect._do_sync_generic", lambda *args, **kwargs: None
    )

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    mock_db.scalar.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def steam_client_no_creds(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Client fixture with Steam API key NOT configured."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("STEAM_API_KEY", "")
    monkeypatch.setenv("FRONTEND_URL", "")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setattr(
        "syncup.api.routes.connect._do_sync_generic", lambda *args, **kwargs: None
    )

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def unauthed_steam_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("STEAM_API_KEY", "test-steam-key")
    monkeypatch.setenv("FRONTEND_URL", "")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/connect/steam/openid/start
# ---------------------------------------------------------------------------


def test_steam_openid_start_requires_auth(unauthed_steam_client: TestClient) -> None:
    resp = unauthed_steam_client.get("/api/connect/steam/openid/start")
    assert resp.status_code == 401


def test_steam_openid_start_redirects_to_steam(steam_client: TestClient) -> None:
    resp = steam_client.get("/api/connect/steam/openid/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "steamcommunity.com/openid/login" in location
    assert "openid.mode=checkid_setup" in location


def test_steam_openid_start_sets_state_cookie(steam_client: TestClient) -> None:
    resp = steam_client.get("/api/connect/steam/openid/start")
    assert resp.status_code == 302
    assert "steam_state" in resp.cookies


def test_steam_openid_start_not_configured_returns_error(
    steam_client_no_creds: TestClient,
) -> None:
    resp = steam_client_no_creds.get("/api/connect/steam/openid/start")
    assert resp.status_code == 503
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/connect/steam/openid/callback
# ---------------------------------------------------------------------------


def test_steam_openid_callback_requires_auth(unauthed_steam_client: TestClient) -> None:
    resp = unauthed_steam_client.get(
        "/api/connect/steam/openid/callback",
        params={"state": "some-state"},
        cookies={"steam_state": "some-state"},
    )
    assert resp.status_code == 401


def test_steam_openid_callback_state_mismatch_returns_400(
    unauthed_steam_client: TestClient,
) -> None:
    resp = unauthed_steam_client.get(
        "/api/connect/steam/openid/callback",
        params={"state": "wrong-state"},
        cookies={"steam_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_steam_openid_callback_missing_state_cookie_returns_400(
    steam_client: TestClient,
) -> None:
    resp = steam_client.get(
        "/api/connect/steam/openid/callback",
        params={"state": "some-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_steam_openid_callback_success_redirects_home(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    steam_client: TestClient,
) -> None:
    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.SteamClient.validate_openid_assertion",
        lambda self, params: "76561197960434622",
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.SteamClient.get_player_summary",
        lambda self, steam_id: {"personaname": "Test"},
    )
    mock_db.scalar.return_value = None

    resp = steam_client.get(
        "/api/connect/steam/openid/callback",
        params={
            "state": "matching-state",
            "openid.identity": "https://steamcommunity.com/openid/id/76561197960434622",
            "openid.mode": "id_res",
        },
        cookies={"steam_state": "matching-state"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_steam_openid_callback_stores_steam_id(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    steam_client: TestClient,
) -> None:
    from syncup.db.models import ServiceConnection

    fake_user = _make_user()
    steam_id = "76561197960434622"
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.SteamClient.validate_openid_assertion",
        lambda self, params: steam_id,
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.SteamClient.get_player_summary",
        lambda self, sid: {"personaname": "Test"},
    )
    mock_db.scalar.return_value = None

    steam_client.get(
        "/api/connect/steam/openid/callback",
        params={
            "state": "st",
            "openid.identity": f"https://steamcommunity.com/openid/id/{steam_id}",
            "openid.mode": "id_res",
        },
        cookies={"steam_state": "st"},
    )

    added_conn: ServiceConnection = mock_db.add.call_args[0][0]
    assert added_conn.external_user_id == steam_id


def test_steam_openid_callback_uses_compare_digest(
    steam_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import secrets as _secrets

    called: list[tuple[str, str]] = []
    original = _secrets.compare_digest

    def spy(a: str, b: str) -> bool:
        called.append((a, b))
        return original(a, b)

    monkeypatch.setattr("syncup.api.routes.connect.secrets.compare_digest", spy)
    steam_client.get(
        "/api/connect/steam/openid/callback",
        params={"state": "st"},
        cookies={"steam_state": "st"},
    )
    assert called, "secrets.compare_digest was not called for Steam state validation"
