"""Tests for pgvector literal serialization."""

from __future__ import annotations

import math

import pytest

from syncup.db.pgvector import format_vec


def test_format_vec_basic() -> None:
    assert format_vec([0.1, 0.2]) == "[0.10000000,0.20000000]"


def test_format_vec_empty() -> None:
    assert format_vec([]) == "[]"


def test_format_vec_negative_values() -> None:
    assert format_vec([-1.0, 0.0]) == "[-1.00000000,0.00000000]"


def test_format_vec_rejects_non_finite() -> None:
    # "nan"/"inf" are not valid pgvector literals — fail with a clear error
    # instead of an opaque DB error inside an ANN query.
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="non-finite"):
            format_vec([0.1, bad, 0.3])
