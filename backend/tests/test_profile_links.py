"""Tests for public profile-link helpers."""

from __future__ import annotations

import uuid

from syncup.db.models import ServiceConnection
from syncup.profile_links import normalize_social_links, public_profile_links


def _connection(service: str, external_user_id: str) -> ServiceConnection:
    return ServiceConnection(
        user_id=uuid.uuid4(),
        service=service,
        external_user_id=external_user_id,
        sync_status="ok",
    )


def test_public_profile_links_include_lastfm_connection() -> None:
    links = public_profile_links(
        {"github": "https://github.com/syncup"},
        [_connection("lastfm", "night listener")],
    )

    assert links == {
        "github": "https://github.com/syncup",
        "lastfm": "https://www.last.fm/user/night%20listener",
    }


def test_normalize_social_links_rejects_unknown_platform() -> None:
    try:
        normalize_social_links({"unknown": "https://example.com"})
    except ValueError as exc:
        assert "unsupported social platform" in str(exc)
    else:
        raise AssertionError("expected unknown profile platform to be rejected")
