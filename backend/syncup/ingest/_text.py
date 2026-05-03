"""Shared text utilities for ingest clients."""
from __future__ import annotations

import re
import unicodedata


def normalize_title(s: str) -> str:
    """Return a normalized title string for cross-service deduplication.

    Lowercases, strips accents, removes punctuation, and collapses whitespace.
    Used for film/show/anime/manga title_normalized metadata keys — these are
    load-bearing for Letterboxd ↔ Trakt cross-service deduplication.
    """
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
