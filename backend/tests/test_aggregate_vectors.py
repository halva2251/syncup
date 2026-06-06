"""Tests for aggregate_vectors() — pure function for building user taste vectors.

aggregate_vectors() takes pre-fetched (vector, weight) pairs, applies log1p dampening,
computes a weighted sum, and returns an L2-normalised vector. No model dependency.
"""

from __future__ import annotations

import math
from typing import cast

import numpy as np
import pytest

from syncup.embeddings.user_embeddings import aggregate_vectors

DIM = 4  # small dimension for readable test assertions


def _unit(direction: list[float]) -> list[float]:
    """Return the L2-normalised version of a vector."""
    arr = np.array(direction, dtype=np.float64)
    return cast(list[float], (arr / np.linalg.norm(arr)).tolist())


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


def test_returns_list_of_floats() -> None:
    vec = [1.0, 0.0, 0.0, 0.0]
    result = aggregate_vectors([(vec, 1.0)])
    assert isinstance(result, list)
    assert all(isinstance(v, float) for v in result)


def test_output_dimension_matches_input() -> None:
    vec = [0.5, 0.5, 0.0, 0.0]
    result = aggregate_vectors([(vec, 1.0)])
    assert len(result) == DIM


def test_output_is_l2_normalised() -> None:
    vec = [1.0, 2.0, 3.0, 4.0]
    result = aggregate_vectors([(vec, 5.0)])
    norm = math.sqrt(sum(v * v for v in result))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_single_pair_direction_matches_input_vector() -> None:
    """A single (vector, weight) should return a unit vector in the same direction."""
    raw = [3.0, 4.0, 0.0, 0.0]
    result = aggregate_vectors([(raw, 1.0)])
    expected = _unit(raw)
    assert result == pytest.approx(expected, abs=1e-6)


def test_weight_magnitude_does_not_affect_single_pair_direction() -> None:
    """For a single pair, varying the weight only scales before normalising — direction is fixed."""
    raw = [1.0, 2.0, 3.0, 4.0]
    small = aggregate_vectors([(raw, 0.001)])
    large = aggregate_vectors([(raw, 1000.0)])
    assert small == pytest.approx(large, abs=1e-6)


# ---------------------------------------------------------------------------
# Log1p dampening
# ---------------------------------------------------------------------------


def test_log1p_dampening_limits_whale_domination() -> None:
    """A weight-10000 pair shouldn't erase the direction of a weight-1 pair.

    Without log1p, ratio is 10000:1 → second pair is invisible.
    With log1p, ratio is log1p(10000):log1p(1) ≈ 9.2:0.69 ≈ 13:1 → visible.
    """
    # Two orthogonal vectors
    dominant = [1.0, 0.0, 0.0, 0.0]
    minor = [0.0, 1.0, 0.0, 0.0]

    whale = aggregate_vectors([(dominant, 10000.0), (minor, 1.0)])
    whale_only = aggregate_vectors([(dominant, 10000.0)])

    diff = float(np.linalg.norm(np.array(whale) - np.array(whale_only)))
    assert diff > 0.01, f"log1p dampening not reducing whale dominance: diff={diff}"


def test_equal_weights_produce_mean_direction() -> None:
    """Two equal-weight orthogonal unit vectors → result is the diagonal direction."""
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0, 0.0]
    result = aggregate_vectors([(v1, 1.0), (v2, 1.0)])
    expected = _unit([1.0, 1.0, 0.0, 0.0])
    assert result == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Skipping / filtering
# ---------------------------------------------------------------------------


def test_zero_weight_pairs_are_skipped() -> None:
    v_kept = [1.0, 0.0, 0.0, 0.0]
    v_skip = [0.0, 1.0, 0.0, 0.0]
    with_zero = aggregate_vectors([(v_kept, 1.0), (v_skip, 0.0)])
    without = aggregate_vectors([(v_kept, 1.0)])
    assert with_zero == pytest.approx(without, abs=1e-6)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_empty_pairs_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        aggregate_vectors([])


def test_all_zero_weights_raises() -> None:
    pairs = [([1.0, 0.0, 0.0, 0.0], 0.0), ([0.0, 1.0, 0.0, 0.0], 0.0)]
    with pytest.raises(ValueError, match="No pairs contributed"):
        aggregate_vectors(pairs)


def test_negative_weight_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        aggregate_vectors([([1.0, 0.0, 0.0, 0.0], -0.5)])


def test_zero_norm_vector_raises() -> None:
    """A vector of all zeros produces a zero-norm accumulator — must not return NaN."""
    with pytest.raises(ValueError, match="zero norm"):
        aggregate_vectors([([0.0, 0.0, 0.0, 0.0], 1.0)])


def test_mixed_dimensions_raises() -> None:
    """Vectors of different lengths must raise a clear error."""
    with pytest.raises(ValueError, match="same dimension"):
        aggregate_vectors([([1.0, 0.0, 0.0, 0.0], 1.0), ([0.0, 1.0, 0.0], 1.0)])


# ---------------------------------------------------------------------------
# Correctness with 384-dim vectors (production dimension)
# ---------------------------------------------------------------------------


def test_384_dim_input() -> None:
    rng = np.random.default_rng(0)
    vecs = [rng.standard_normal(384).tolist() for _ in range(10)]
    weights = [float(rng.uniform(0.1, 1.0)) for _ in range(10)]
    result = aggregate_vectors(list(zip(vecs, weights, strict=True)))
    assert len(result) == 384
    norm = math.sqrt(sum(v * v for v in result))
    assert norm == pytest.approx(1.0, abs=1e-6)
