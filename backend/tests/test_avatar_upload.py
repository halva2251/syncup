"""Tests for POST /api/me/avatar — profile photo upload."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from syncup.db.models import User

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
_GARBAGE = b"MZ\x90\x00" + b"\x00" * 64


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


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=DbSession)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[TestClient, None, None]:
    """Unauthenticated client."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def upload_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
    tmp_path: Path,
) -> Generator[tuple[TestClient, User, Path], None, None]:
    """Authenticated client; yields (client, fake_user, upload_dir)."""
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c, fake_user, upload_dir
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


def test_upload_avatar_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/me/avatar", files={"file": ("a.png", _PNG, "image/png")})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_upload_avatar_happy_path(
    upload_client: tuple[TestClient, User, Path],
    mock_db: MagicMock,
) -> None:
    c, user, upload_dir = upload_client
    resp = c.post("/api/me/avatar", files={"file": ("photo.png", _PNG, "image/png")})
    assert resp.status_code == 200
    avatar_url = resp.json()["avatar_url"]
    assert avatar_url.startswith("/uploads/avatars/")
    assert avatar_url.endswith(".png")
    assert user.avatar_url == avatar_url
    stored = upload_dir / "avatars" / avatar_url.rsplit("/", 1)[1]
    assert stored.is_file()
    assert stored.read_bytes() == _PNG
    mock_db.commit.assert_called_once()


def test_upload_avatar_jpeg_extension(
    upload_client: tuple[TestClient, User, Path],
) -> None:
    c, _, _ = upload_client
    resp = c.post("/api/me/avatar", files={"file": ("photo.jpg", _JPEG, "image/jpeg")})
    assert resp.status_code == 200
    assert resp.json()["avatar_url"].endswith(".jpg")


def test_upload_avatar_bad_content_type_returns_422(
    upload_client: tuple[TestClient, User, Path],
) -> None:
    c, _, _ = upload_client
    resp = c.post(
        "/api/me/avatar",
        files={"file": ("malware.exe", _PNG, "application/x-msdownload")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_avatar_too_large_returns_413(
    upload_client: tuple[TestClient, User, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c, _, _ = upload_client
    # Shrink the cap via the app's settings rather than uploading 5 MB.
    from syncup.api.app import app

    app.state.settings.avatar_max_bytes = 16
    try:
        resp = c.post("/api/me/avatar", files={"file": ("big.png", _PNG, "image/png")})
    finally:
        app.state.settings.avatar_max_bytes = 5 * 1024 * 1024
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_avatar_content_type_lies_returns_422(
    upload_client: tuple[TestClient, User, Path],
) -> None:
    """Content type claims PNG but the bytes are not an image."""
    c, _, _ = upload_client
    resp = c.post("/api/me/avatar", files={"file": ("fake.png", _GARBAGE, "image/png")})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_avatar_replaces_old_local_file(
    upload_client: tuple[TestClient, User, Path],
) -> None:
    c, user, upload_dir = upload_client
    old_dir = upload_dir / "avatars"
    old_dir.mkdir(parents=True)
    old_file = old_dir / "old.png"
    old_file.write_bytes(_PNG)
    user.avatar_url = "/uploads/avatars/old.png"

    resp = c.post("/api/me/avatar", files={"file": ("new.png", _PNG, "image/png")})
    assert resp.status_code == 200
    assert not old_file.exists()


def test_patch_me_accepts_local_upload_path(
    upload_client: tuple[TestClient, User, Path],
) -> None:
    """The avatar_url validator must allow stored /uploads/ paths to round-trip."""
    c, _, _ = upload_client
    resp = c.patch("/api/me", json={"avatar_url": "/uploads/avatars/abc.png"})
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "/uploads/avatars/abc.png"


def test_uploaded_avatar_is_served(
    upload_client: tuple[TestClient, User, Path],
) -> None:
    c, _, _ = upload_client
    resp = c.post("/api/me/avatar", files={"file": ("photo.png", _PNG, "image/png")})
    avatar_url = resp.json()["avatar_url"]
    served = c.get(avatar_url)
    assert served.status_code == 200
    assert served.content == _PNG
