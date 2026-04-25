"""Auth route tests — signup, login, logout, require_auth."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from syncup.auth.hashing import hash_password, verify_password
from syncup.db.models import Session as SessionRow
from syncup.db.models import User
from syncup.limiter import limiter as _rate_limiter

# Pre-computed once per session to keep the test suite fast — argon2 is
# intentionally slow, so re-hashing in every _make_user() call adds up.
_CACHED_HASH = hash_password("password123")


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

    app.dependency_overrides[get_db] = lambda: mock_db

    # Disable rate limiting and avoid real DB connection during tests.
    _rate_limiter.enabled = False
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    _rate_limiter.enabled = True
    app.dependency_overrides.clear()


def _make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "password_hash": _CACHED_HASH,
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
    mock_db.scalar.return_value = None

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


def test_signup_sets_location_header(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": "password123", "display_name": "Alice"},
    )

    assert resp.headers.get("location") == "/api/me"


def test_signup_normalizes_email(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "  ALICE@EXAMPLE.COM  ", "password": "password123", "display_name": "A"},
    )

    assert resp.status_code == 201
    assert resp.json()["user"]["email"] == "alice@example.com"


def test_signup_duplicate_email_returns_409(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "taken@example.com", "password": "password123", "display_name": "Bob"},
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


def test_signup_integrity_error_returns_409(auth_client: TestClient, mock_db: MagicMock) -> None:
    """Race condition guard: IntegrityError from DB maps to EMAIL_TAKEN, not 500."""
    mock_db.scalar.return_value = None
    mock_db.commit.side_effect = IntegrityError("duplicate", {}, Exception())

    resp = auth_client.post(
        "/api/auth/signup",
        json={"email": "race@example.com", "password": "password123", "display_name": "Race"},
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


def test_login_normalizes_email(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "  USER@EXAMPLE.COM  ", "password": "password123"},
    )

    assert resp.status_code == 200


def test_login_wrong_password_returns_401(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _make_user()

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_returns_401(auth_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

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


def test_login_rehashes_outdated_password(auth_client: TestClient, mock_db: MagicMock) -> None:
    """Transparent rehash: if needs_rehash returns True, password_hash is updated."""
    user = _make_user()
    original_hash = user.password_hash
    mock_db.scalar.return_value = user

    with patch("syncup.auth.router.needs_rehash", return_value=True):
        resp = auth_client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )

    assert resp.status_code == 200
    assert user.password_hash != original_hash
    assert verify_password(user.password_hash or "", "password123")
    mock_db.commit.assert_called()


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


def test_require_auth_no_cookie_returns_401(mock_db: MagicMock) -> None:
    from syncup.auth.router import require_auth
    from syncup.exceptions import SyncUpError

    mock_request = MagicMock()
    mock_request.cookies.get.return_value = None

    with pytest.raises(SyncUpError) as exc_info:
        require_auth(mock_request, mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "UNAUTHORIZED"


def test_require_auth_expired_session_returns_401(mock_db: MagicMock) -> None:
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


def test_require_auth_deleted_user_returns_401(mock_db: MagicMock) -> None:
    """Orphaned session: token valid but user row was deleted."""
    from syncup.auth.router import require_auth
    from syncup.exceptions import SyncUpError

    valid_session = MagicMock(spec=SessionRow)
    valid_session.expires_at = datetime.now(UTC) + timedelta(days=1)
    valid_session.user_id = uuid.uuid4()

    def _get(model: type, key: object) -> object:
        if model is SessionRow:
            return valid_session
        return None  # user deleted

    mock_db.get.side_effect = _get

    mock_request = MagicMock()
    mock_request.cookies.get.return_value = "valid-token"

    with pytest.raises(SyncUpError) as exc_info:
        require_auth(mock_request, mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "UNAUTHORIZED"
