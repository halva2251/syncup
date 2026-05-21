"""Convert an Item (or any duck-typed object with name/item_type/meta) to
an embeddable text string.

Format table (roadmap §2.1):
  game      "{name} — game, {genres}"         meta["genres"] list; fallback omits genres
  artist    "{name} — music, {genres}"        meta["genres"] list; fallback omits genres
  track     "{name} by {artist} — music"      meta["artists"][0]; fallback omits artist
  film      "{name} ({year}) — film, {genres}" meta["release_year"], meta["genres"]; year/genres optional
  show      "{name} ({year}) — show, {genres}" same pattern as film
  anime     "{name} — anime, {genres}"        meta["genres"]; fallback omits genres
  manga     "{name} — manga, {genres}"        same pattern as anime
  album     "{name} by {artist} — album, music" meta["artist_normalized"]; fallback omits artist
  community "r/{name} — online community, {desc[:100]}" meta["description"]; fallback omits desc
  <other>   "{name} — {item_type}"            covers manual obsessions, book, other, unknown

This function MUST NEVER RAISE. Missing or None metadata falls back gracefully.
"""

from __future__ import annotations

from typing import Any


def item_to_text(item: Any) -> str:
    """Serialize an item to a text string for semantic embedding.

    Args:
        item: any object with .name (str), .item_type (str), and .meta (dict).
              The Item ORM model satisfies this; SimpleNamespace stubs work too.

    Returns:
        A non-empty string suitable for sentence-transformers input.
    """
    name: str = item.name or ""
    item_type: str = item.item_type or ""
    meta: dict[str, Any] = getattr(item, "meta", {}) or {}

    if item_type == "game":
        return _with_genres(f"{name} — game", meta)

    if item_type == "artist":
        return _with_genres(f"{name} — music", meta)

    if item_type == "track":
        artists = _list_or_empty(meta.get("artists"))
        if artists:
            return f"{name} by {artists[0]} — music"
        return f"{name} — music"

    if item_type in ("film", "show"):
        year = meta.get("release_year") or 0
        year_str = f" ({year})" if year else ""
        base = f"{name}{year_str} — {item_type}"
        return _with_genres(base, meta)

    if item_type in ("anime", "manga"):
        return _with_genres(f"{name} — {item_type}", meta)

    if item_type == "album":
        artist = meta.get("artist_normalized") or meta.get("artist") or None
        if artist:
            return f"{name} by {artist} — album, music"
        return f"{name} — album, music"

    if item_type == "community":
        desc = (meta.get("description") or "")[:100].strip()
        if desc:
            return f"r/{name} — online community, {desc}"
        return f"r/{name} — online community"

    # Generic fallback — manual obsessions (book, other, etc.) and unknown types
    return f"{name} — {item_type}"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _list_or_empty(value: Any) -> list[str]:
    """Return value as a list if it's a non-empty list, else []."""
    if isinstance(value, list) and value:
        return value
    return []


def _with_genres(base: str, meta: dict[str, Any]) -> str:
    """Append ', genre1, genre2' to base if genres are present in meta."""
    genres = _list_or_empty(meta.get("genres"))
    if genres:
        return f"{base}, {', '.join(genres)}"
    return base
