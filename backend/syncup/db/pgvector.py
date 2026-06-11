"""Helpers for serializing vectors into pgvector literal strings."""

from __future__ import annotations


def format_vec(vec: list[float]) -> str:
    """Format a float vector as a pgvector literal string, e.g. "[0.1,0.2]"."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
