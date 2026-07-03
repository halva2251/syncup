"""Tests for AniList OAuth connect routes:
GET /api/connect/anilist/oauth/start
GET /api/connect/anilist/oauth/callback
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import ServiceConnection, User


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


def _make_connection(service: str, external_user_id: str) -> ServiceConnection:
    now = datetime.now(UTC)
    return ServiceConnection(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        service=service,
        external_user_id=external_user_id,
        sync_status="pending",
        last_synced_at=None,
        token_expires_at=None,
        sync_error=None,
        access_token_encrypted=None,
        refresh_token_encrypted=None,
        created_at=now,
    )


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def anilist_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("ANILIST_CLIENT_ID", "test-anilist-client-id")
    monkeypatch.setenv("ANILIST_CLIENT_SECRET", "test-anilist-secret")
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
def anilist_client_no_creds(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    """Client fixture with AniList credentials NOT configured."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("FRONTEND_URL", "")
    # Explicitly blank — prevents real .env values leaking into this fixture.
    monkeypatch.setenv("ANILIST_CLIENT_ID", "")
    monkeypatch.setenv("ANILIST_CLIENT_SECRET", "")
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
def unauthed_anilist_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("ANILIST_CLIENT_ID", "test-anilist-client-id")
    monkeypatch.setenv("ANILIST_CLIENT_SECRET", "test-anilist-secret")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app, follow_redirects=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/connect/anilist/oauth/start
# ---------------------------------------------------------------------------


def test_anilist_oauth_start_requires_auth(unauthed_anilist_client: TestClient) -> None:
    resp = unauthed_anilist_client.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 401


def test_anilist_oauth_start_redirects_to_anilist(anilist_client: TestClient) -> None:
    resp = anilist_client.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "anilist.co" in location


def test_anilist_oauth_start_sets_state_cookie(anilist_client: TestClient) -> None:
    resp = anilist_client.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 302
    assert "anilist_state" in resp.cookies


def test_anilist_oauth_start_not_configured_returns_error(
    anilist_client_no_creds: TestClient,
) -> None:
    resp = anilist_client_no_creds.get("/api/connect/anilist/oauth/start")
    assert resp.status_code == 503
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/connect/anilist/oauth/callback
# ---------------------------------------------------------------------------


def test_anilist_oauth_callback_requires_auth(unauthed_anilist_client: TestClient) -> None:
    # State matches, so state check passes — auth check fires next → 401.
    resp = unauthed_anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
        cookies={"anilist_state": "some-state"},
    )
    assert resp.status_code == 401


def test_anilist_oauth_callback_state_mismatch_returns_400_even_when_unauthenticated(
    unauthed_anilist_client: TestClient,
) -> None:
    # State mismatch must return 400, not 401, even without a session.
    # This verifies that state validation runs BEFORE the auth check.
    resp = unauthed_anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"anilist_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_anilist_oauth_callback_state_mismatch_returns_400(
    anilist_client: TestClient,
) -> None:
    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "wrong-state"},
        cookies={"anilist_state": "correct-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_anilist_oauth_callback_missing_state_cookie_returns_400(
    anilist_client: TestClient,
) -> None:
    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "some-code", "state": "some-state"},
        # no state cookie set
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OAUTH_STATE_MISMATCH"


def test_anilist_oauth_callback_success_redirects_home(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    anilist_client: TestClient,
) -> None:
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    # require_auth is called directly (not via DI) after state check — must patch the fn.
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.AniListClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_at=None,
        ),
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.AniListClient.fetch_me",
        lambda self, access_token: {"id": 12345},
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"encrypted")
    mock_db.scalar.return_value = None  # no existing connection

    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "valid-code", "state": "matching-state"},
        cookies={"anilist_state": "matching-state"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://127.0.0.1:3001"


def test_anilist_oauth_callback_stores_anilist_user_id(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    anilist_client: TestClient,
) -> None:
    """external_user_id must be the AniList viewer ID, not the SyncUp user UUID."""
    from syncup.ingest.protocol import TokenPair

    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)
    monkeypatch.setattr(
        "syncup.api.routes.connect.AniListClient.exchange_code",
        lambda self, code: TokenPair(
            access_token="access-tok", refresh_token=None, expires_at=None
        ),
    )
    monkeypatch.setattr(
        "syncup.api.routes.connect.AniListClient.fetch_me",
        lambda self, access_token: {"id": 99999},
    )
    monkeypatch.setattr("syncup.api.routes.connect.encrypt_token", lambda _: b"enc")
    mock_db.scalar.return_value = None

    anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "code", "state": "st"},
        cookies={"anilist_state": "st"},
    )

    # The ServiceConnection added to DB must have external_user_id = "99999".
    added_conn: ServiceConnection = mock_db.add.call_args[0][0]
    assert added_conn.external_user_id == "99999"


# ---------------------------------------------------------------------------
# S1 — AniList callback must use secrets.compare_digest for state validation
# ---------------------------------------------------------------------------


def test_anilist_callback_uses_compare_digest_for_state_validation(
    anilist_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State comparison in the AniList callback must use secrets.compare_digest."""
    import secrets as _secrets

    called: list[tuple[str, str]] = []
    original = _secrets.compare_digest

    def spy(a: str, b: str) -> bool:
        called.append((a, b))
        return original(a, b)

    monkeypatch.setattr("syncup.api.routes.connect.secrets.compare_digest", spy)
    anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "c", "state": "st"},
        cookies={"anilist_state": "st"},
    )
    assert called, "secrets.compare_digest was not called for AniList state validation"


# ---------------------------------------------------------------------------
# S3 — AniList token exchange must not leak upstream response body
# ---------------------------------------------------------------------------


def test_anilist_callback_token_error_does_not_leak_upstream_body(
    anilist_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """httpx.HTTPStatusError body from AniList must not appear in the API response."""
    import httpx as _httpx

    sensitive = "secret_anilist_internal_XYZ"
    fake_user = _make_user()
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)

    def _raise_http_error(self: object, code: str) -> None:
        raise _httpx.HTTPStatusError(
            "400",
            request=_httpx.Request("POST", "https://anilist.co/api/v2/oauth/token"),
            response=_httpx.Response(400, text=sensitive),
        )

    monkeypatch.setattr("syncup.api.routes.connect.AniListClient.exchange_code", _raise_http_error)

    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "c", "state": "st"},
        cookies={"anilist_state": "st"},
    )
    assert sensitive not in resp.text, "Upstream error body must not be returned to client"


# ---------------------------------------------------------------------------
# H3 — AniList GraphQL error text must not reach the API consumer
# ---------------------------------------------------------------------------


def test_anilist_callback_graphql_error_uses_fixed_message(
    anilist_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H3: SyncClientError wrapping a GraphQL message must yield a fixed response, not the upstream text."""
    from syncup.ingest.protocol import SyncClientError as _SyncClientError

    graphql_leak = "Cannot query field 'secretField' on type 'User'"
    fake_user = _make_user()
    # require_auth is called directly (not via DI) in the callback — patch at module level
    monkeypatch.setattr("syncup.api.routes.connect.require_auth", lambda **_: fake_user)

    def _raise_graphql_error(self: object, code: str) -> None:
        raise _SyncClientError(f"AniList GraphQL error: {graphql_leak}")

    monkeypatch.setattr(
        "syncup.api.routes.connect.AniListClient.exchange_code", _raise_graphql_error
    )

    resp = anilist_client.get(
        "/api/connect/anilist/oauth/callback",
        params={"code": "c", "state": "st"},
        cookies={"anilist_state": "st"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "ANILIST_TOKEN_ERROR"
    assert graphql_leak not in resp.text, "GraphQL error detail must not be returned to client"
