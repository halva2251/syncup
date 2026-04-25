"""Auth route tests — signup, login, logout, require_auth."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.auth.hashing import hash_password
from syncup.db.models import Session as SessionRow
from syncup.db.models import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def auth_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.db.session import get_db

    # Override get_db so routes use mock_db; patch sessionmaker_for so the
    # lifespan doesn't try to open a real DB connection during test startup.
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def _make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "password_hash": hash_password("password123"),
        "display_name": "Test User",
        "is_matchable": False,
        "onboarded": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    return User(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# POST /api/auth/signup
# ---------------------------------------------------------------------------


def test_signup_returns_201_and_user(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None  # no existing user

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": "password123", "display_name": "Alice"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert "user" in body
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["display_name"] == "Alice"


def test_signup_sets_session_cookie(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": "password123", "display_name": "Alice"},
    )

    assert "syncup_session" in resp.cookies


def test_signup_duplicate_email_returns_409(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()  # existing user found

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "taken@example.com", "password": "password123", "display_name": "Bob"},
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


def test_signup_short_password_returns_422(auth_client: TestClient, mock_db: MagicMock) -> None:
    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "x@example.com", "password": "short", "display_name": "X"},
    )
    assert resp.status_code == 422


def test_signup_invalid_email_returns_422(auth_client: TestClient, mock_db: MagicMock) -> None:
    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "password123", "display_name": "X"},
    )
    assert resp.status_code == 422


def test_signup_empty_display_name_returns_422(auth_client: TestClient, mock_db: MagicMock) -> None:
    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "x@example.com", "password": "password123", "display_name": ""},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------


def test_login_valid_credentials_returns_200(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert resp.status_code == 200
    assert "user" in resp.json()


def test_login_sets_session_cookie(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert "syncup_session" in resp.cookies


def test_login_wrong_password_returns_401(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_returns_401(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None  # user not found

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_runs_dummy_verify(auth_client: TestClient, mock_db: MagicMock) -> None:
    """Timing attack mitigation: dummy hash must run when email is not found."""
    mock_db.scalar.return_value = None

    with patch("syncup.auth.router.verify_password_dummy") as mock_dummy:
        auth_client.post(
            "/api/auth/login",
            json={"email": "ghost@example.com", "password": "password123"},
        )
        mock_dummy.assert_called_once()


def test_login_returns_error_envelope_on_failure(
    auth_client: TestClient, mock_db: MagicMock
) -> None:
    mock_db.scalar.return_value = None

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )

    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------


def test_logout_returns_204(auth_client: TestClient, mock_db: MagicMock) -> None:
    resp = auth_client.post("/api/auth/logout")
    assert resp.status_code == 204


def test_logout_without_session_still_returns_204(
    auth_client: TestClient, mock_db: MagicMock
) -> None:
    resp = auth_client.post("/api/auth/logout")
    assert resp.status_code == 204


def test_logout_deletes_session_row(auth_client: TestClient, mock_db: MagicMock) -> None:
    token = "some-session-token"
    mock_session_row = MagicMock(spec=SessionRow)
    mock_db.get.return_value = mock_session_row

    auth_client.cookies.set("syncup_session", token)
    auth_client.post("/api/auth/logout")

    mock_db.delete.assert_called_once_with(mock_session_row)
    mock_db.commit.assert_called()


def test_logout_clears_cookie(auth_client: TestClient, mock_db: MagicMock) -> None:
    auth_client.cookies.set("syncup_session", "old-token")
    resp = auth_client.post("/api/auth/logout")
    assert resp.cookies.get("syncup_session") in (None, "")


# ---------------------------------------------------------------------------
# require_auth dependency
# ---------------------------------------------------------------------------


def test_require_auth_no_cookie_returns_401(auth_client: TestClient, mock_db: MagicMock) -> None:
    """Hit /api/auth/logout with the require_auth path indirectly via signup → me stub."""
    # We test require_auth directly by hitting a route that uses it.
    # For now, verify that no-cookie state on a route with require_auth
    # would raise — tested via the dependency itself.

    from syncup.auth.router import require_auth
    from syncup.exceptions import SyncUpError

    mock_request = MagicMock()
    mock_request.cookies.get.return_value = None  # no cookie

    with pytest.raises(SyncUpError) as exc_info:
        require_auth(mock_request, mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "UNAUTHORIZED"


def test_require_auth_expired_session_returns_401(mock_db: MagicMock) -> None:
    from datetime import datetime, timedelta

    from syncup.auth.router import require_auth
    from syncup.exceptions import SyncUpError

    expired_session = MagicMock(spec=SessionRow)
    expired_session.expires_at = datetime.now(UTC) - timedelta(days=1)
    mock_db.get.return_value = expired_session

    mock_request = MagicMock()
    mock_request.cookies.get.return_value = "expired-token"

    with pytest.raises(SyncUpError) as exc_info:
        require_auth(mock_request, mock_db)

    assert exc_info.value.status_code == 401
