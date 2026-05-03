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
