"""Shared text utilities for ingest clients."""
from __future__ import annotations

import re
import unicodedata


_LIGATURES: dict[str, str] = {
    "Œ": "OE", "œ": "oe", "Æ": "AE", "æ": "ae", "ß": "ss",
}


def normalize_title(s: str) -> str:
    """Return a normalized title string for cross-service deduplication.

    Lowercases, expands ligatures, strips accents, removes punctuation, and
    collapses whitespace. Load-bearing for Letterboxd ↔ Trakt deduplication.
    """
    s = "".join(_LIGATURES.get(c, c) for c in s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
