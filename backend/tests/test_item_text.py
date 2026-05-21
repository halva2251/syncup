"""Tests for syncup.embeddings.item_text — item_to_text() serializer.

Covers every item_type from roadmap §2.1:
  game, artist, track, film, show, anime, manga, album, community, manual obsession (fallback)

The critical invariant: item_to_text MUST NEVER RAISE, even when metadata
keys are absent, None, or contain unexpected types. All tests use
SimpleNamespace so no DB connection is required.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(
    name: str,
    item_type: str,
    meta: dict[str, Any] | None = None,
    service: str = "test",
) -> SimpleNamespace:
    """Build a duck-typed Item substitute for item_to_text."""
    return SimpleNamespace(
        name=name,
        item_type=item_type,
        meta=meta if meta is not None else {},
        service=service,
    )


# ---------------------------------------------------------------------------
# Steam games
# ---------------------------------------------------------------------------


def test_game_with_genres_includes_genres() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Disco Elysium", "game", {"genres": ["RPG", "Adventure"]}, service="steam")
    text = item_to_text(item)
    assert "Disco Elysium" in text
    assert "game" in text
    assert "RPG" in text
    assert "Adventure" in text


def test_game_with_genres_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Hollow Knight", "game", {"genres": ["Metroidvania", "Action"]}, service="steam")
    text = item_to_text(item)
    assert text == "Hollow Knight — game, Metroidvania, Action"


def test_game_without_genres_falls_back_gracefully() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("CS2", "game", {}, service="steam")
    text = item_to_text(item)
    assert "CS2" in text
    assert "game" in text
    assert text == "CS2 — game"


def test_game_with_empty_genres_list_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Portal", "game", {"genres": []}, service="steam")
    text = item_to_text(item)
    assert text == "Portal — game"


def test_game_with_none_genres_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Portal 2", "game", {"genres": None}, service="steam")
    text = item_to_text(item)
    assert text == "Portal 2 — game"


# ---------------------------------------------------------------------------
# Music artists
# ---------------------------------------------------------------------------


def test_artist_with_genres_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Nick Cave", "artist", {"genres": ["Post-punk", "Alternative"]}, service="lastfm")
    text = item_to_text(item)
    assert text == "Nick Cave — music, Post-punk, Alternative"


def test_artist_without_genres_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Unknown Artist", "artist", {}, service="lastfm")
    text = item_to_text(item)
    assert text == "Unknown Artist — music"


def test_artist_with_empty_genres_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Artist", "artist", {"genres": []}, service="spotify")
    text = item_to_text(item)
    assert text == "Artist — music"


# ---------------------------------------------------------------------------
# Music tracks
# ---------------------------------------------------------------------------


def test_track_with_artist_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "Into My Arms",
        "track",
        {"artists": ["Nick Cave & The Bad Seeds"]},
        service="spotify",
    )
    text = item_to_text(item)
    assert text == "Into My Arms by Nick Cave & The Bad Seeds — music"


def test_track_without_artists_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Mystery Track", "track", {}, service="spotify")
    text = item_to_text(item)
    assert text == "Mystery Track — music"


def test_track_with_empty_artists_list_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Track", "track", {"artists": []}, service="spotify")
    text = item_to_text(item)
    assert text == "Track — music"


def test_track_uses_first_artist_only() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "Collab",
        "track",
        {"artists": ["Artist A", "Artist B", "Artist C"]},
        service="spotify",
    )
    text = item_to_text(item)
    assert "Artist A" in text
    assert "Artist B" not in text


# ---------------------------------------------------------------------------
# Films
# ---------------------------------------------------------------------------


def test_film_with_year_and_genres_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "Stalker",
        "film",
        {"release_year": 1979, "genres": ["Drama", "Sci-Fi"]},
        service="letterboxd",
    )
    text = item_to_text(item)
    assert text == "Stalker (1979) — film, Drama, Sci-Fi"


def test_film_with_year_no_genres() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Stalker", "film", {"release_year": 1979}, service="letterboxd")
    text = item_to_text(item)
    assert text == "Stalker (1979) — film"


def test_film_without_year_falls_back_to_name_only() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Unknown Film", "film", {"genres": ["Drama"]}, service="trakt")
    text = item_to_text(item)
    # year 0 / missing → no year in output
    assert "Unknown Film — film" in text
    assert "(0)" not in text
    assert "(None)" not in text


def test_film_with_zero_year_omits_year() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Film", "film", {"release_year": 0, "genres": ["Action"]}, service="trakt")
    text = item_to_text(item)
    assert "(0)" not in text
    assert "Action" in text


def test_film_with_none_year_omits_year() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Film", "film", {"release_year": None, "genres": ["Action"]}, service="trakt")
    text = item_to_text(item)
    assert "(None)" not in text


# ---------------------------------------------------------------------------
# Shows
# ---------------------------------------------------------------------------


def test_show_with_year_and_genres_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "The Wire",
        "show",
        {"release_year": 2002, "genres": ["Crime", "Drama"]},
        service="trakt",
    )
    text = item_to_text(item)
    assert text == "The Wire (2002) — show, Crime, Drama"


def test_show_without_genres_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Severance", "show", {"release_year": 2022}, service="trakt")
    text = item_to_text(item)
    assert text == "Severance (2022) — show"


# ---------------------------------------------------------------------------
# Anime
# ---------------------------------------------------------------------------


def test_anime_with_genres_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "Neon Genesis Evangelion",
        "anime",
        {"genres": ["Mecha", "Psychological"]},
        service="anilist",
    )
    text = item_to_text(item)
    assert text == "Neon Genesis Evangelion — anime, Mecha, Psychological"


def test_anime_without_genres_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Some Anime", "anime", {}, service="anilist")
    text = item_to_text(item)
    assert text == "Some Anime — anime"


# ---------------------------------------------------------------------------
# Manga
# ---------------------------------------------------------------------------


def test_manga_with_genres_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Berserk", "manga", {"genres": ["Fantasy", "Dark Fantasy"]}, service="anilist")
    text = item_to_text(item)
    assert text == "Berserk — manga, Fantasy, Dark Fantasy"


def test_manga_without_genres_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Berserk", "manga", {}, service="anilist")
    text = item_to_text(item)
    assert text == "Berserk — manga"


# ---------------------------------------------------------------------------
# Albums
# ---------------------------------------------------------------------------


def test_album_with_artist_normalized_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "Murder Ballads",
        "album",
        {"artist_normalized": "nick cave and the bad seeds"},
        service="rateyourmusic",
    )
    text = item_to_text(item)
    assert text == "Murder Ballads by nick cave and the bad seeds — album, music"


def test_album_without_artist_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Unknown Album", "album", {}, service="rateyourmusic")
    text = item_to_text(item)
    assert text == "Unknown Album — album, music"


def test_album_with_none_artist_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Album", "album", {"artist_normalized": None}, service="rateyourmusic")
    text = item_to_text(item)
    assert text == "Album — album, music"


# ---------------------------------------------------------------------------
# Reddit communities
# ---------------------------------------------------------------------------


def test_community_with_description_format() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item(
        "slatestarcodex",
        "community",
        {"description": "A community for rationalists"},
        service="reddit",
    )
    text = item_to_text(item)
    assert text == "r/slatestarcodex — online community, A community for rationalists"


def test_community_description_truncated_to_100_chars() -> None:
    from syncup.embeddings.item_text import item_to_text

    long_desc = "x" * 200
    item = _item("subreddit", "community", {"description": long_desc}, service="reddit")
    text = item_to_text(item)
    # The description portion must be at most 100 chars
    prefix = "r/subreddit — online community, "
    desc_part = text[len(prefix) :]
    assert len(desc_part) <= 100


def test_community_without_description_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("niche_sub", "community", {}, service="reddit")
    text = item_to_text(item)
    assert text == "r/niche_sub — online community"


def test_community_with_empty_description_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("sub", "community", {"description": ""}, service="reddit")
    text = item_to_text(item)
    assert text == "r/sub — online community"


# ---------------------------------------------------------------------------
# Manual obsessions and unknown types (generic fallback)
# ---------------------------------------------------------------------------


def test_unknown_item_type_falls_back_to_name_dash_type() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("Some Book", "book", {}, service="manual")
    text = item_to_text(item)
    assert text == "Some Book — book"


def test_manual_obsession_other_category_falls_back() -> None:
    from syncup.embeddings.item_text import item_to_text

    item = _item("My Weird Interest", "other", {}, service="manual")
    text = item_to_text(item)
    assert text == "My Weird Interest — other"


# ---------------------------------------------------------------------------
# Never-raise contract — missing, None, or malformed metadata
# ---------------------------------------------------------------------------


def test_never_raises_with_empty_meta() -> None:
    from syncup.embeddings.item_text import item_to_text

    for item_type in (
        "game",
        "artist",
        "track",
        "film",
        "show",
        "anime",
        "manga",
        "album",
        "community",
    ):
        item = _item("Test", item_type, {})
        result = item_to_text(item)  # must not raise
        assert isinstance(result, str)
        assert len(result) > 0


def test_never_raises_with_none_values_in_meta() -> None:
    from syncup.embeddings.item_text import item_to_text

    bad_meta = {
        "genres": None,
        "release_year": None,
        "artists": None,
        "artist_normalized": None,
        "description": None,
    }
    for item_type in (
        "game",
        "artist",
        "track",
        "film",
        "show",
        "anime",
        "manga",
        "album",
        "community",
    ):
        item = _item("Test", item_type, bad_meta)
        result = item_to_text(item)  # must not raise
        assert isinstance(result, str)


def test_result_always_contains_item_name() -> None:
    from syncup.embeddings.item_text import item_to_text

    for item_type in (
        "game",
        "artist",
        "track",
        "film",
        "show",
        "anime",
        "manga",
        "album",
        "community",
        "other",
    ):
        item = _item("UniqueNameXYZ", item_type, {})
        result = item_to_text(item)
        assert "UniqueNameXYZ" in result, f"name missing for item_type={item_type!r}: {result!r}"


def test_result_is_always_non_empty_string() -> None:
    from syncup.embeddings.item_text import item_to_text

    for item_type in (
        "game",
        "artist",
        "track",
        "film",
        "show",
        "anime",
        "manga",
        "album",
        "community",
        "other",
    ):
        item = _item("Test", item_type, {})
        result = item_to_text(item)
        assert isinstance(result, str)
        assert len(result.strip()) > 0
