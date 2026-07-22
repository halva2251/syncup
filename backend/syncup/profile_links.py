"""Validation and public URL builders for profile social links."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote, urlparse

from syncup.db.models import ServiceConnection

# Manual profiles supported in Settings → Profile. Values must be a public HTTPS
# URL on the platform's own domain; this prevents profile links becoming an open
# redirect or an arbitrary-link surface.
SOCIAL_LINK_HOSTS: dict[str, frozenset[str]] = {
    "github": frozenset({"github.com", "www.github.com"}),
    "x": frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"}),
    "instagram": frozenset({"instagram.com", "www.instagram.com"}),
    "tiktok": frozenset({"tiktok.com", "www.tiktok.com"}),
    "youtube": frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}),
    "twitch": frozenset({"twitch.tv", "www.twitch.tv"}),
    "bluesky": frozenset({"bsky.app", "www.bsky.app"}),
    "mastodon": frozenset({"mastodon.social", "www.mastodon.social"}),
    "soundcloud": frozenset({"soundcloud.com", "www.soundcloud.com"}),
}


def normalize_social_links(value: object) -> dict[str, str]:
    """Validate and normalize a map of supported profile-platform URLs."""
    if not isinstance(value, dict):
        raise ValueError("social_links must be an object")
    if len(value) > len(SOCIAL_LINK_HOSTS):
        raise ValueError("too many social links")

    normalized: dict[str, str] = {}
    for platform, raw_url in value.items():
        if platform not in SOCIAL_LINK_HOSTS:
            raise ValueError(f"unsupported social platform: {platform}")
        if not isinstance(raw_url, str):
            raise ValueError("each social link must be a URL")
        url = raw_url.strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("social links must use https URLs")
        if parsed.hostname.lower() not in SOCIAL_LINK_HOSTS[platform]:
            raise ValueError(f"social link must point to {platform}")
        normalized[platform] = url
    return normalized


def _service_profile_link(connection: ServiceConnection) -> tuple[str, str] | None:
    """Return a public profile link for connections with stable public URLs."""
    external_id = quote(connection.external_user_id, safe="")
    builders = {
        "anilist": lambda: ("anilist", f"https://anilist.co/user/{external_id}"),
        "lastfm": lambda: ("lastfm", f"https://www.last.fm/user/{external_id}"),
        "reddit": lambda: ("reddit", f"https://www.reddit.com/user/{external_id}"),
        "spotify": lambda: ("spotify", f"https://open.spotify.com/user/{external_id}"),
        "steam": lambda: ("steam", f"https://steamcommunity.com/profiles/{external_id}"),
        "trakt": lambda: ("trakt", f"https://trakt.tv/users/{external_id}"),
    }
    builder = builders.get(connection.service)
    return builder() if builder else None


def public_profile_links(
    social_links: dict[str, str] | None,
    connections: Iterable[ServiceConnection],
) -> dict[str, str]:
    """Merge manually-entered links with public links inferred from services."""
    result = dict(social_links or {})
    for connection in connections:
        public_link = _service_profile_link(connection)
        if public_link is not None:
            platform, url = public_link
            result[platform] = url
    return result
