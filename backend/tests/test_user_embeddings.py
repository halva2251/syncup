"""Tests for user vector aggregation from item embeddings.

We reuse the same dark/arena synthetic setup as test_item2vec so that
the learned geometry is predictable: a user whose library is entirely
dark games should end up cosine-close to dark games and far from arena
games. If that fails, the aggregation is wrong — don't ship it.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from syncup.embeddings.item2vec import Item2VecModel, TrainingConfig
from syncup.embeddings.user_embeddings import build_user_vector

DARK_GAMES = ["disco_elysium", "planescape", "bloodborne", "dark_souls", "hollow_knight"]
ARENA_GAMES = ["fortnite", "warzone", "valorant", "apex", "cs2"]


def _synthetic_libraries(seed: int = 42) -> list[list[str]]:
    rng = random.Random(seed)
    libraries: list[list[str]] = []
    for _ in range(150):
        size = rng.randint(3, 5)
        libraries.append(rng.sample(DARK_GAMES, size))
    for _ in range(150):
        size = rng.randint(3, 5)
        libraries.append(rng.sample(ARENA_GAMES, size))
    return libraries


@pytest.fixture(scope="module")
def model() -> Item2VecModel:
    config = TrainingConfig(vector_size=32, window=5, min_count=1, epochs=50)
    return Item2VecModel.train(_synthetic_libraries(), config=config)


def test_user_vector_has_correct_dimension(model: Item2VecModel) -> None:
    user = build_user_vector({"disco_elysium": 10.0}, model)
    assert len(user) == 32


def test_user_vector_is_l2_normalized(model: Item2VecModel) -> None:
    user = build_user_vector({"disco_elysium": 10.0, "bloodborne": 5.0}, model)
    norm = math.sqrt(sum(v * v for v in user))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_user_vector_is_floats(model: Item2VecModel) -> None:
    user = build_user_vector({"disco_elysium": 10.0}, model)
    assert all(isinstance(v, float) for v in user)


def test_single_item_user_is_parallel_to_item_vector(model: Item2VecModel) -> None:
    """A user with one item has a vector parallel to that item's vector."""
    user = np.asarray(build_user_vector({"disco_elysium": 10.0}, model))
    item = np.asarray(model.vector("disco_elysium"))
    item_unit = item / np.linalg.norm(item)
    assert float(np.dot(user, item_unit)) == pytest.approx(1.0, abs=1e-6)


def test_weight_magnitude_does_not_affect_single_item_direction(
    model: Item2VecModel,
) -> None:
    """For a single item, weight magnitude only scales — direction is fixed."""
    small = build_user_vector({"disco_elysium": 1.0}, model)
    large = build_user_vector({"disco_elysium": 1000.0}, model)
    assert small == pytest.approx(large, abs=1e-6)


def test_dark_user_clusters_with_dark_games(model: Item2VecModel) -> None:
    user = np.asarray(build_user_vector({g: 10.0 for g in DARK_GAMES}, model))

    def cosine(item_id: str) -> float:
        v = np.asarray(model.vector(item_id))
        return float(np.dot(user, v / np.linalg.norm(v)))

    dark_sims = [cosine(g) for g in DARK_GAMES]
    arena_sims = [cosine(g) for g in ARENA_GAMES]
    assert min(dark_sims) > max(arena_sims), (
        f"dark user should be closer to dark games; "
        f"dark={dark_sims}, arena={arena_sims}"
    )


def test_missing_items_are_skipped_silently(model: Item2VecModel) -> None:
    with_missing = build_user_vector(
        {"disco_elysium": 10.0, "nonexistent_item": 5.0}, model
    )
    without = build_user_vector({"disco_elysium": 10.0}, model)
    assert with_missing == pytest.approx(without, abs=1e-6)


def test_all_missing_items_raises(model: Item2VecModel) -> None:
    with pytest.raises(ValueError, match="No interactions contributed"):
        build_user_vector({"nope_1": 1.0, "nope_2": 2.0}, model)


def test_empty_interactions_raises(model: Item2VecModel) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        build_user_vector({}, model)


def test_negative_weight_raises(model: Item2VecModel) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_user_vector({"disco_elysium": -1.0}, model)


def test_zero_weight_is_skipped(model: Item2VecModel) -> None:
    with_zero = build_user_vector(
        {"disco_elysium": 10.0, "bloodborne": 0.0}, model
    )
    without = build_user_vector({"disco_elysium": 10.0}, model)
    assert with_zero == pytest.approx(without, abs=1e-6)


def test_all_zero_weights_raises(model: Item2VecModel) -> None:
    with pytest.raises(ValueError, match="No interactions contributed"):
        build_user_vector({"disco_elysium": 0.0, "bloodborne": 0.0}, model)


def test_log_dampening_prevents_whale_domination(model: Item2VecModel) -> None:
    """A 10000h game shouldn't drown out a 1h game to the point of invisibility.

    Raw weights would give a 10000:1 ratio. log1p(10000):log1p(1) ~= 13:1.
    So the second item must still shift the aggregated vector noticeably.
    """
    whale_plus_one = np.asarray(
        build_user_vector({"disco_elysium": 10000.0, "fortnite": 1.0}, model)
    )
    whale_only = np.asarray(build_user_vector({"disco_elysium": 10000.0}, model))
    diff = float(np.linalg.norm(whale_plus_one - whale_only))
    assert diff > 0.01, f"log dampening not working: diff={diff} is too small"
