"""User embeddings: aggregate item embeddings into per-user taste vectors.

Given a user's interactions (item_id -> engagement weight, e.g. hours
played, listen count), produce a single vector that represents the
user's overall taste.

Aggregation is a weighted sum of item vectors with log1p dampening of
weights, then L2-normalized so cosine similarity with other user
vectors is a plain dot product.

Why log1p dampening: raw play counts are wildly skewed. A user with
10000h in one game and 5h in another would otherwise have their item
library effectively replaced by one single game; log1p keeps the big
signal dominant without erasing the rest.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import cast

import numpy as np

from syncup.embeddings.item2vec import Item2VecModel


def build_user_vector(
    interactions: Mapping[str, float],
    model: Item2VecModel,
) -> list[float]:
    """Aggregate item embeddings into an L2-normalized user vector.

    Args:
        interactions: item_id -> engagement weight (e.g. hours played,
            listen count). Items missing from the model vocabulary are
            skipped silently — they provide no signal. Zero weights are
            also skipped.
        model: trained item2vec model providing item vectors.

    Returns:
        L2-normalized float vector with the same dimension as the
        model's item vectors.

    Raises:
        ValueError: if interactions is empty, any weight is negative,
            or no interactions contributed (all zero weights and/or
            all items out-of-vocabulary).
    """
    if not interactions:
        raise ValueError("interactions must not be empty")

    for item_id, weight in interactions.items():
        if weight < 0:
            raise ValueError(
                f"Weights must be non-negative, got {weight} for {item_id!r}"
            )

    accumulator: np.ndarray | None = None
    for item_id, weight in interactions.items():
        if weight == 0:
            continue
        try:
            vec = model.vector(item_id)
        except KeyError:
            continue
        dampened = math.log1p(weight)
        contribution = np.asarray(vec, dtype=np.float64) * dampened
        accumulator = (
            contribution if accumulator is None else accumulator + contribution
        )

    if accumulator is None:
        raise ValueError(
            "No interactions contributed to the user vector. "
            "All items were either out-of-vocabulary or had zero weight."
        )

    norm = float(np.linalg.norm(accumulator))
    if norm == 0.0:
        raise ValueError(
            "Aggregated user vector has zero norm; cannot L2-normalize."
        )
    return cast(list[float], (accumulator / norm).tolist())
