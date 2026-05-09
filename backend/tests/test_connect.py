"""Tests for POST /api/connect/steam and POST /api/connect/lastfm."""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from syncup.ingest.protocol import SyncClientError

import httpx
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
def connect_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_db: MagicMock,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app
    from syncup.auth.router import require_auth
    from syncup.db.session import get_db

    fake_user = _make_user()
    mock_db.scalar.return_value = None  # no existing connection by default

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_auth] = lambda: fake_user
    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def unauthed_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-id")
    monkeypatch.setenv("DEBUG", "true")

    from syncup.api.app import app

    with patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# POST /api/connect/steam
# ---------------------------------------------------------------------------


def test_steam_connect_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post("/api/connect/steam", json={"steam_id": "76561198000000000"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_steam_connect_with_steam_id(connect_client: TestClient, mock_db: MagicMock) -> None:
    steam_id = "76561198000000000"
    mock_db.scalar.return_value = None

    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.return_value = {"steamid": steam_id, "personaname": "halva"}
        # db.add() sets conn, then db.commit() — mock scalar returns None (new connection)
        # after db.add the ORM tracks it; we just check mock calls and response shape
        mock_db.scalar.return_value = None

        resp = connect_client.post("/api/connect/steam", json={"steam_id": steam_id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "steam"
    assert body["external_user_id"] == steam_id
    assert body["sync_status"] == "pending"


def test_steam_connect_with_vanity_url(connect_client: TestClient, mock_db: MagicMock) -> None:
    steam_id = "76561198000000000"

    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.resolve_vanity_url.return_value = steam_id
        instance.get_player_summary.return_value = {"steamid": steam_id, "personaname": "halva"}
        mock_db.scalar.return_value = None

        resp = connect_client.post("/api/connect/steam", json={"vanity_url": "halva"})

    assert resp.status_code == 200
    instance.resolve_vanity_url.assert_called_once_with("halva")
    assert resp.json()["external_user_id"] == steam_id


def test_steam_connect_vanity_not_found_returns_404(
    connect_client: TestClient,
) -> None:
    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.resolve_vanity_url.side_effect = SyncClientError("Vanity URL 'nobody' not found")

        resp = connect_client.post("/api/connect/steam", json={"vanity_url": "nobody"})

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "STEAM_USER_NOT_FOUND"


def test_steam_connect_steam_id_no_profile_returns_404(
    connect_client: TestClient,
) -> None:
    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.side_effect = SyncClientError("No Steam profile found")

        resp = connect_client.post("/api/connect/steam", json={"steam_id": "99999"})

    assert resp.status_code == 404


def test_steam_connect_missing_both_fields_returns_422(
    connect_client: TestClient,
) -> None:
    resp = connect_client.post("/api/connect/steam", json={})
    assert resp.status_code == 422


def test_steam_connect_both_fields_returns_422(connect_client: TestClient) -> None:
    resp = connect_client.post(
        "/api/connect/steam",
        json={"steam_id": "76561198000000000", "vanity_url": "halva"},
    )
    assert resp.status_code == 422


def test_steam_connect_upstream_error_returns_502(connect_client: TestClient) -> None:
    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.side_effect = httpx.RequestError("timeout")

        resp = connect_client.post("/api/connect/steam", json={"steam_id": "76561198000000000"})

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_steam_connect_updates_existing_connection(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    steam_id = "76561198000000000"
    existing = _make_connection("steam", "old-id")
    mock_db.scalar.return_value = existing

    with patch("syncup.api.routes.connect.SteamClient") as mock_steam_cls:
        instance = mock_steam_cls.return_value.__enter__.return_value
        instance.get_player_summary.return_value = {"steamid": steam_id, "personaname": "halva"}

        resp = connect_client.post("/api/connect/steam", json={"steam_id": steam_id})

    assert resp.status_code == 200
    assert existing.external_user_id == steam_id
    assert existing.sync_status == "pending"
    assert existing.sync_error is None


# ---------------------------------------------------------------------------
# POST /api/connect/lastfm
# ---------------------------------------------------------------------------


def test_lastfm_connect_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post("/api/connect/lastfm", json={"username": "halva"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_lastfm_connect_valid_username(connect_client: TestClient, mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.return_value = [{"name": "Radiohead", "playcount": "500"}]

        resp = connect_client.post("/api/connect/lastfm", json={"username": "halva"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "lastfm"
    assert body["external_user_id"] == "halva"
    assert body["sync_status"] == "pending"
    instance.get_top_artists.assert_called_once_with("halva", limit=1)


def test_lastfm_connect_user_not_found_returns_404(connect_client: TestClient) -> None:
    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = SyncClientError("Last.fm API error 6: User not found")

        resp = connect_client.post("/api/connect/lastfm", json={"username": "nobody_here_xyz"})

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LASTFM_USER_NOT_FOUND"


def test_lastfm_connect_upstream_error_returns_502(connect_client: TestClient) -> None:
    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = httpx.RequestError("timeout")

        resp = connect_client.post("/api/connect/lastfm", json={"username": "halva"})

    assert resp.status_code == 502


def test_lastfm_connect_empty_username_returns_422(connect_client: TestClient) -> None:
    resp = connect_client.post("/api/connect/lastfm", json={"username": ""})
    assert resp.status_code == 422


def test_lastfm_connect_updates_existing_connection(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    existing = _make_connection("lastfm", "old-username")
    mock_db.scalar.return_value = existing

    with patch("syncup.api.routes.connect.LastfmClient") as mock_lastfm_cls:
        instance = mock_lastfm_cls.return_value.__enter__.return_value
        instance.get_top_artists.return_value = [{"name": "Radiohead"}]

        resp = connect_client.post("/api/connect/lastfm", json={"username": "halva"})

    assert resp.status_code == 200
    assert existing.external_user_id == "halva"
    assert existing.sync_status == "pending"


# ---------------------------------------------------------------------------
# POST /api/connect/letterboxd/import
# ---------------------------------------------------------------------------

_LETTERBOXD_CSV = (
    "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
    "2024-01-15,The Substance,2024,https://letterboxd.com/film/the-substance/,4.5,No,,2024-01-15\n"
    "2024-01-10,Stalker,1979,https://letterboxd.com/film/stalker/,5.0,Yes,,2024-01-10\n"
)


def test_letterboxd_import_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", _LETTERBOXD_CSV, "text/csv")},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_letterboxd_import_success(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    mock_db.scalar.return_value = None  # no existing connection
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()

    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", _LETTERBOXD_CSV, "text/csv")},
    )

    assert resp.status_code == 201
    assert resp.json() == {"imported": 2}
    mock_db.commit.assert_called()


def test_letterboxd_import_file_too_large(
    connect_client: TestClient,
) -> None:
    oversized = "x" * (10 * 1024 * 1024 + 1)
    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", oversized, "text/csv")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_letterboxd_import_malformed_csv_returns_422(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    bad_csv = "wrong,headers,here\n1,2,3\n"
    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", bad_csv, "text/csv")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CSV"


def test_letterboxd_import_updates_existing_connection(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    existing = _make_connection("letterboxd", f"csv:{uuid.uuid4()}")
    existing.sync_status = "error"  # starts in error state; route must set it to "ok"
    mock_db.scalar.return_value = existing
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()

    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", _LETTERBOXD_CSV, "text/csv")},
    )

    assert resp.status_code == 201
    assert existing.sync_status == "ok"
    assert existing.sync_error is None


def test_letterboxd_import_non_utf8_file_returns_422(
    connect_client: TestClient,
) -> None:
    # latin-1 encoded bytes that are invalid UTF-8
    latin1_bytes = "Nausicaä of the Valley of the Wind".encode("latin-1")
    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", latin1_bytes, "text/csv")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CSV"


def test_letterboxd_import_wrong_content_type_returns_422(
    connect_client: TestClient,
) -> None:
    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_letterboxd_import_skips_unrated_rows(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    csv_with_unrated = (
        "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
        "2024-01-15,The Substance,2024,,4.5,No,,2024-01-15\n"
        "2024-01-10,Stalker,1979,,,No,,2024-01-10\n"  # no rating — skipped
    )
    mock_db.scalar.return_value = None
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()

    resp = connect_client.post(
        "/api/connect/letterboxd/import",
        files={"file": ("diary.csv", csv_with_unrated, "text/csv")},
    )

    assert resp.status_code == 201
    assert resp.json() == {"imported": 1}


# ---------------------------------------------------------------------------
# POST /api/connect/rateyourmusic/import
# ---------------------------------------------------------------------------

_RYM_CSV = (
    "Title,Release_Date,Rating\n"
    "OK Computer,1997,10\n"
    "Dummy,1994,9\n"
)


def test_rym_import_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", _RYM_CSV, "text/csv")},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_rym_import_success(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    mock_db.scalar.return_value = None
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()

    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", _RYM_CSV, "text/csv")},
    )

    assert resp.status_code == 201
    assert resp.json() == {"imported": 2}
    mock_db.commit.assert_called()


def test_rym_import_file_too_large(connect_client: TestClient) -> None:
    oversized = "x" * (10 * 1024 * 1024 + 1)
    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", oversized, "text/csv")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_rym_import_malformed_csv_returns_422(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    bad_csv = "wrong,headers,here\n1,2,3\n"
    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", bad_csv, "text/csv")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CSV"


def test_rym_import_updates_existing_connection(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    existing = _make_connection("rateyourmusic", f"csv:{uuid.uuid4()}")
    existing.sync_status = "error"
    mock_db.scalar.return_value = existing
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()

    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", _RYM_CSV, "text/csv")},
    )

    assert resp.status_code == 201
    assert existing.sync_status == "ok"
    assert existing.sync_error is None


def test_rym_import_non_utf8_file_returns_422(connect_client: TestClient) -> None:
    latin1_bytes = "Björk".encode("latin-1")
    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", latin1_bytes, "text/csv")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CSV"


def test_rym_import_wrong_content_type_returns_422(connect_client: TestClient) -> None:
    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_rym_import_skips_unrated_rows(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    csv_with_unrated = "Title,Release_Date,Rating\nOK Computer,1997,10\nDummy,1994,\n"
    mock_db.scalar.return_value = None
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()

    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", csv_with_unrated, "text/csv")},
    )

    assert resp.status_code == 201
    assert resp.json() == {"imported": 1}


def test_rym_import_db_failure_returns_500(
    connect_client: TestClient, mock_db: MagicMock
) -> None:
    import uuid

    mock_db.scalar.return_value = None
    mock_db.execute.return_value.scalar_one.return_value = uuid.uuid4()
    mock_db.commit.side_effect = Exception("db exploded")

    resp = connect_client.post(
        "/api/connect/rateyourmusic/import",
        files={"file": ("ratings.csv", _RYM_CSV, "text/csv")},
    )

    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "IMPORT_FAILED"


# ---------------------------------------------------------------------------
# S3 — HTTP errors from upstream must not leak response body to client
# ---------------------------------------------------------------------------


def test_steam_http_error_does_not_leak_upstream_body(connect_client: TestClient) -> None:
    """httpx.HTTPStatusError body from Steam API must not appear in the API response."""
    import httpx as _httpx

    sensitive = "secret_steam_internal_XYZ"
    with patch("syncup.api.routes.connect.SteamClient") as mock_cls:
        instance = mock_cls.return_value.__enter__.return_value
        instance.get_player_summary.side_effect = _httpx.HTTPStatusError(
            "503",
            request=_httpx.Request("GET", "https://api.steampowered.com/"),
            response=_httpx.Response(503, text=sensitive),
        )
        resp = connect_client.post("/api/connect/steam", json={"steam_id": "76561198000000000"})

    assert sensitive not in resp.text, "Upstream error body must not be returned to client (steam)"


def test_lastfm_http_error_does_not_leak_upstream_body(connect_client: TestClient) -> None:
    """httpx.HTTPStatusError body from Last.fm API must not appear in the API response."""
    import httpx as _httpx

    sensitive = "secret_lastfm_internal_XYZ"
    with patch("syncup.api.routes.connect.LastfmClient") as mock_cls:
        instance = mock_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = _httpx.HTTPStatusError(
            "503",
            request=_httpx.Request("GET", "https://ws.audioscrobbler.com/"),
            response=_httpx.Response(503, text=sensitive),
        )
        resp = connect_client.post("/api/connect/lastfm", json={"username": "testuser"})

    assert sensitive not in resp.text, "Upstream error body must not be returned to client (lastfm)"


# ---------------------------------------------------------------------------
# M2 — RequestError paths must not leak internal exception repr to client
# ---------------------------------------------------------------------------


def test_steam_request_error_does_not_leak_hostname(connect_client: TestClient) -> None:
    """httpx.RequestError from Steam must not expose internal hostnames in the response."""
    with patch("syncup.api.routes.connect.SteamClient") as mock_cls:
        instance = mock_cls.return_value.__enter__.return_value
        instance.get_player_summary.side_effect = httpx.RequestError(
            "internal-steam-proxy:9999 connection refused"
        )
        resp = connect_client.post("/api/connect/steam", json={"steam_id": "76561198000000000"})
    assert "internal-steam-proxy" not in resp.text


def test_lastfm_request_error_does_not_leak_hostname(connect_client: TestClient) -> None:
    """httpx.RequestError from Last.fm must not expose internal hostnames in the response."""
    with patch("syncup.api.routes.connect.LastfmClient") as mock_cls:
        instance = mock_cls.return_value.__enter__.return_value
        instance.get_top_artists.side_effect = httpx.RequestError(
            "internal-lastfm-proxy:9999 connection refused"
        )
        resp = connect_client.post("/api/connect/lastfm", json={"username": "testuser"})
    assert "internal-lastfm-proxy" not in resp.text
