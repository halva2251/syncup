"""Tests for ServiceRegistry."""

from __future__ import annotations

from typing import ClassVar

import pytest

from syncup.ingest.protocol import RawItem, ServiceClient, TokenPair
from syncup.ingest.registry import _clear, get_client, register, registered_services


def _make_client(name: str) -> ServiceClient:
    class _C:
        service_name: ClassVar[str] = name

        def fetch_items(self, connection: object) -> list[RawItem]:
            return []

        def refresh_token(self, connection: object) -> TokenPair | None:
            return None

    _C.service_name = name
    return _C()  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Isolate each test from registry state set by other tests."""
    _clear()
    yield  # type: ignore[misc]
    _clear()


# ---------------------------------------------------------------------------
# register / get_client round-trip
# ---------------------------------------------------------------------------


def test_register_and_retrieve() -> None:
    client = _make_client("myservice")
    register(client)
    assert get_client("myservice") is client


def test_get_client_raises_on_unknown_service() -> None:
    with pytest.raises(KeyError, match="unknown"):
        get_client("unknown")


def test_register_replaces_existing() -> None:
    old = _make_client("svc")
    new = _make_client("svc")
    register(old)
    register(new)
    assert get_client("svc") is new


# ---------------------------------------------------------------------------
# registered_services
# ---------------------------------------------------------------------------


def test_registered_services_empty_initially() -> None:
    assert registered_services() == set()


def test_registered_services_returns_all_names() -> None:
    register(_make_client("alpha"))
    register(_make_client("beta"))
    assert registered_services() == {"alpha", "beta"}


def test_registered_services_returns_copy() -> None:
    register(_make_client("gamma"))
    s = registered_services()
    s.add("fake")
    assert "fake" not in registered_services()


# ---------------------------------------------------------------------------
# _clear (test helper)
# ---------------------------------------------------------------------------


def test_clear_empties_registry() -> None:
    register(_make_client("delta"))
    _clear()
    assert registered_services() == set()


# ---------------------------------------------------------------------------
# I4 — close_all() must call close() on every registered client that has it
# ---------------------------------------------------------------------------


def test_close_all_calls_close_on_each_registered_client() -> None:
    """close_all() must call .close() on every registered client."""
    from unittest.mock import MagicMock

    from syncup.ingest.registry import close_all

    client_a = MagicMock()
    client_a.service_name = "svc_a"
    client_b = MagicMock()
    client_b.service_name = "svc_b"
    register(client_a)
    register(client_b)

    close_all()

    client_a.close.assert_called_once()
    client_b.close.assert_called_once()


def test_close_all_skips_clients_without_close() -> None:
    """close_all() must not raise if a client has no .close() method."""
    from syncup.ingest.registry import close_all

    register(_make_client("no_close"))
    close_all()  # must not raise


def test_close_all_continues_after_one_client_raises() -> None:
    """close_all() must attempt all clients even if one .close() raises."""
    from unittest.mock import MagicMock

    from syncup.ingest.registry import close_all

    bad = MagicMock()
    bad.service_name = "bad"
    bad.close.side_effect = RuntimeError("exploded")
    good = MagicMock()
    good.service_name = "good"
    register(bad)
    register(good)

    close_all()  # must not raise

    bad.close.assert_called_once()
    good.close.assert_called_once()


def test_lifespan_shutdown_calls_close_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """App lifespan shutdown must call close_all() to release httpx connections."""
    from unittest.mock import MagicMock, patch

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv(
        "SYNCUP_TOKEN_ENCRYPTION_KEY", "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg="
    )

    from syncup.api.app import app

    close_calls: list[str] = []

    def _fake_close_all() -> None:
        close_calls.append("called")

    with (
        patch("syncup.api.app.sessionmaker_for", return_value=MagicMock()),
        patch("syncup.api.app.close_all_clients", side_effect=_fake_close_all),
    ):
        from fastapi.testclient import TestClient

        with TestClient(app):
            pass  # enter + exit triggers lifespan shutdown

    assert close_calls == ["called"], "close_all_clients() must be called during lifespan shutdown"
