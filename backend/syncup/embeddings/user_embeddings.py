"""User embeddings: aggregate item embeddings into per-user taste vectors.

Given a user's interactions (item_id -> engagement weight), produce a single
vector that represents the user's overall taste.

Two-level aggregation (see syncup.api.routes.embeddings.build_user_embedding):
  1. Within a service, items are combined with `aggregate_vectors` — a log1p-
     dampened weighted sum, L2-normalised to a unit "service taste direction".
  2. Across services, those unit directions are combined with
     `combine_service_vectors` — a LINEAR weighted sum by dimension weight,
     L2-normalised. Mean-pooling each service to unit mass first is what makes
     the user's per-service dimension weights authoritative: a service with many
     items no longer dominates the centroid by sheer count.

A note on log1p dampening (honest framing): `engagement_score` reaching this
module is already normalised to [0, 1] by every ingest client (e.g. Steam's
playtime / max_playtime). On [0, 1], log1p is nearly linear (log1p(0.2)=0.182
vs log1p(1.0)=0.693 — a 3.8x spread vs the raw 5x), so it applies only a MILD
concave reweighting here. The dramatic dampening that tames order-of-magnitude
raw play-count skew (e.g. 10000h vs 5h) already happened upstream during the
client's [0, 1] normalisation — this module never sees raw counts. log1p is kept
as a gentle within-service preference for higher-engagement items, not as the
whale-domination fix it would be on raw data.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import cast

import numpy as np

from syncup.embeddings.item2vec import Item2VecModel


def _weighted_normalize(
    pairs: list[tuple[list[float], float]],
    *,
    dampen: bool,
    _ctx: str,
) -> list[float]:
    """Weighted sum of (vector, weight) pairs, L2-normalised.

    Args:
        pairs: (vector, weight) pairs. Weights must be >= 0; zero-weight skipped.
        dampen: if True, apply log1p to each weight before accumulation (mild
            concave reweighting); if False, use the weight linearly.
        _ctx: caller name for error messages.

    Raises:
        ValueError: empty input, any negative weight, mismatched dimensions,
            all-zero weights, or a zero-norm accumulator.
    """
    if not pairs:
        raise ValueError(f"{_ctx} requires a non-empty list of pairs")

    expected_dim = len(pairs[0][0])
    for _vec, weight in pairs:
        if weight < 0:
            raise ValueError(f"Weights must be non-negative, got {weight}")

    for vec, _weight in pairs:
        if len(vec) != expected_dim:
            raise ValueError(
                f"All vectors must have the same dimension ({expected_dim}), got {len(vec)}"
            )

    accumulator: np.ndarray | None = None
    for vec, weight in pairs:
        if weight == 0:
            continue
        effective = math.log1p(weight) if dampen else weight
        contribution = np.asarray(vec, dtype=np.float64) * effective
        accumulator = contribution if accumulator is None else accumulator + contribution

    if accumulator is None:
        raise ValueError("No pairs contributed to the user vector — all weights were zero.")

    norm = float(np.linalg.norm(accumulator))
    if norm == 0.0:
        raise ValueError(
            "Aggregated vector has zero norm; cannot L2-normalize. "
            "Check that input vectors are non-zero."
        )
    return cast(list[float], (accumulator / norm).tolist())


def aggregate_vectors(
    pairs: list[tuple[list[float], float]],
) -> list[float]:
    """Within-service aggregation: log1p-dampened weighted sum, L2-normalised.

    Weights (engagement_score, already in [0, 1]) are log1p-dampened before
    accumulation — a mild concave reweighting toward higher-engagement items.
    See the module docstring for why this is mild, not a raw-count whale fix.

    Args:
        pairs: pre-fetched (embedding_vector, weight) pairs from the DB.
            Weights must be >= 0. Zero-weight pairs are skipped.

    Returns:
        L2-normalised float vector of the same dimension as the inputs.

    Raises:
        ValueError: if pairs is empty, any weight is negative, the accumulated
            vector has zero norm, or no pairs contributed (all zero weights).
    """
    return _weighted_normalize(pairs, dampen=True, _ctx="aggregate_vectors")


def combine_service_vectors(
    pairs: list[tuple[list[float], float]],
) -> list[float]:
    """Across-service aggregation: LINEAR weighted sum of unit vectors, L2-normalised.

    Each input vector is a service's unit taste direction (from aggregate_vectors);
    each weight is that service's dimension weight. No log1p is applied — dimension
    weights are direct linear preferences, so a 0.7 vs 0.3 weight produces a
    0.7:0.3 contribution ratio. This is what makes the per-service slider
    authoritative regardless of how many items each service contributed.

    Args:
        pairs: (service_unit_vector, dimension_weight) pairs. Weights must be >= 0;
            zero-weight services are skipped.

    Returns:
        L2-normalised combined taste vector.

    Raises:
        ValueError: same conditions as aggregate_vectors.
    """
    return _weighted_normalize(pairs, dampen=False, _ctx="combine_service_vectors")


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
            raise ValueError(f"Weights must be non-negative, got {weight} for {item_id!r}")

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
        accumulator = contribution if accumulator is None else accumulator + contribution

    if accumulator is None:
        raise ValueError(
            "No interactions contributed to the user vector. "
            "All items were either out-of-vocabulary or had zero weight."
        )

    norm = float(np.linalg.norm(accumulator))
    if norm == 0.0:
        raise ValueError("Aggregated user vector has zero norm; cannot L2-normalize.")
    return cast(list[float], (accumulator / norm).tolist())
