"""Matching engine: score user-to-user similarity with dimension weighting.

A user's profile is a collection of per-service vectors (one per
connected service: Steam, Last.fm, Spotify, ...). Each vector is
already L2-normalized by `build_user_vector`, so cosine similarity is
a plain dot product.

Match score is a weighted average of per-service cosine similarities,
where the weights come from the querying user's preferences (e.g.
"music 70%, games 30%"). Weights are renormalized over the services
that both users actually have, so incomplete profiles on either side
don't arbitrarily deflate otherwise-strong matches.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class UserProfile:
    """A user's per-service taste vectors.

    Each entry in ``vectors`` should be L2-normalized; the matching
    engine assumes unit vectors and does not re-normalize them.
    """

    user_id: str
    vectors: Mapping[str, Sequence[float]]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return cosine similarity of two vectors, in the range [-1, 1].

    Raises:
        ValueError: if the vectors differ in dimension or either is
            zero-norm (cosine is undefined in that case).
    """
    if len(a) != len(b):
        raise ValueError(
            f"Vector dimension mismatch: {len(a)} vs {len(b)}"
        )
    arr_a = np.asarray(a, dtype=np.float64)
    arr_b = np.asarray(b, dtype=np.float64)
    norm_a = float(np.linalg.norm(arr_a))
    norm_b = float(np.linalg.norm(arr_b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise ValueError("Cannot compute cosine of a zero-norm vector")
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))


def match_score(
    a: UserProfile,
    b: UserProfile,
    weights: Mapping[str, float],
) -> float:
    """Weighted average of per-service cosine similarity between two profiles.

    Only services present in *both* profiles and in ``weights`` contribute.
    Weights are renormalized over those shared services so incomplete
    profiles still produce a meaningful score on their overlap.

    Returns 0.0 when the profiles share no weighted service.

    Raises:
        ValueError: if weights is empty, any weight is negative, or all
            weights are zero.
    """
    if not weights:
        raise ValueError("weights must not be empty")

    for service, w in weights.items():
        if w < 0:
            raise ValueError(
                f"Weights must be non-negative, got {w} for {service!r}"
            )

    if not any(w > 0 for w in weights.values()):
        raise ValueError("weights must contain at least one positive weight")

    shared = [
        service
        for service, w in weights.items()
        if w > 0 and service in a.vectors and service in b.vectors
    ]
    if not shared:
        return 0.0

    total_weight = sum(weights[service] for service in shared)
    weighted_sum = 0.0
    for service in shared:
        sim = cosine_similarity(a.vectors[service], b.vectors[service])
        weighted_sum += (weights[service] / total_weight) * sim
    return weighted_sum


def rank_matches(
    query: UserProfile,
    candidates: Iterable[UserProfile],
    weights: Mapping[str, float],
    k: int = 10,
) -> list[tuple[UserProfile, float]]:
    """Return the top-k candidates sorted by match score (highest first).

    The query profile is excluded from the result if it appears in
    ``candidates``.

    Raises:
        ValueError: if k < 1, or if weights are invalid (see
            ``match_score``).
    """
    if k < 1:
        raise ValueError(f"k must be a positive integer, got {k}")

    scored = [
        (candidate, match_score(query, candidate, weights))
        for candidate in candidates
        if candidate.user_id != query.user_id
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]
