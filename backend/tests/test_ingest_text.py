"""Tests for syncup/ingest/_text.py — normalize_title.

normalize_title is load-bearing for Letterboxd ↔ Trakt cross-service film
deduplication. Two services produce an identical title_normalized for the same
film; a drift here silently breaks dedup.
"""
from __future__ import annotations

import pytest

from syncup.ingest._text import normalize_title


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Basic lowercasing
        ("Disco Elysium", "disco elysium"),
        ("STALKER", "stalker"),
        # Accent stripping
        ("Café Society", "cafe society"),
        ("Nausicaä of the Valley of the Wind", "nausicaa of the valley of the wind"),
        ("Amélie", "amelie"),
        # Punctuation removal
        ("Hello!!", "hello"),
        ("It's a Wonderful Life", "its a wonderful life"),
        ("Spider-Man: No Way Home", "spiderman no way home"),
        # Whitespace collapsing
        ("  Blade   Runner  ", "blade runner"),
        ("Blade\tRunner", "blade runner"),
        # Combined: accents + punctuation + casing
        ("L'Avventura", "lavventura"),
        ("2001: A Space Odyssey", "2001 a space odyssey"),
        # Numbers preserved
        ("Se7en", "se7en"),
        ("The 400 Blows", "the 400 blows"),
        # Already normalised — idempotent
        ("blade runner", "blade runner"),
        # Empty string
        ("", ""),
        # Whitespace-only
        ("   ", ""),
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


def test_normalize_title_cross_service_dedup() -> None:
    """Letterboxd and Trakt representations of the same film normalise identically."""
    letterboxd_title = "Stalker"
    trakt_title = "Stalker"
    assert normalize_title(letterboxd_title) == normalize_title(trakt_title)


def test_normalize_title_cross_service_dedup_with_accent() -> None:
    letterboxd_title = "Nausicaä of the Valley of the Wind"
    trakt_title = "Nausicaa of the Valley of the Wind"
    assert normalize_title(letterboxd_title) == normalize_title(trakt_title)


def test_normalize_title_returns_str() -> None:
    assert isinstance(normalize_title("test"), str)
