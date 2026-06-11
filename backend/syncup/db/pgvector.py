"""Helpers for serializing vectors into pgvector literal strings."""

from __future__ import annotations

import math


def format_vec(vec: list[float]) -> str:
    """Format a float vector as a pgvector literal string, e.g. "[0.1,0.2]".

    Raises ValueError on non-finite elements (NaN/inf) — they are not valid
    pgvector literals and would otherwise surface as an opaque DB error.
    """
    if not all(math.isfinite(v) for v in vec):
        raise ValueError("vector contains non-finite values (NaN/inf)")
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
