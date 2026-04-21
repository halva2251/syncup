"""Tests for the matching engine.

The matching engine scores user similarity using per-service cosine
similarity combined with user-controlled dimension weights (e.g.
"music 70%, games 30%"). Weights are renormalized over services that
both users actually have, so a user with only Spotify connected still
gets meaningful scores against someone with Spotify + Steam.

A good end-to-end test: train item2vec on synthetic dark/arena game
data, build user profiles for a dark user and an arena user, and
confirm a second dark user ranks above the arena user when querying
from a dark user's profile.
"""
from __future__ import annotations

import math
import random

import pytest

from syncup.embeddings.item2vec import Item2VecModel, TrainingConfig
from syncup.embeddings.user_embeddings import build_user_vector
from syncup.matching.engine import (
    UserProfile,
    cosine_similarity,
    match_score,
    rank_matches,
)

DARK_GAMES = ["disco_elysium", "planescape", "bloodborne", "dark_souls", "hollow_knight"]
ARENA_GAMES = ["fortnite", "warzone", "valorant", "apex", "cs2"]


def _synthetic_libraries(seed: int = 42) -> list[list[str]]:
    rng = random.Random(seed)
    libs: list[list[str]] = []
    for _ in range(150):
        libs.append(rng.sample(DARK_GAMES, rng.randint(3, 5)))
    for _ in range(150):
        libs.append(rng.sample(ARENA_GAMES, rng.randint(3, 5)))
    return libs


@pytest.fixture(scope="module")
def item_model() -> Item2VecModel:
    config = TrainingConfig(vector_size=32, window=5, min_count=1, epochs=50)
    return Item2VecModel.train(_synthetic_libraries(), config=config)


# ---------- cosine_similarity ----------


def test_cosine_identical_unit_vectors_is_one() -> None:
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_opposite_vectors_is_negative_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_is_magnitude_invariant() -> None:
    """Cosine depends on direction only."""
    a = [1.0, 0.0]
    b = [1000.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(1.0)


def test_cosine_rejects_zero_vector() -> None:
    with pytest.raises(ValueError, match="zero-norm"):
        cosine_similarity([0.0, 0.0], [1.0, 0.0])


def test_cosine_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimension"):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


# ---------- match_score ----------


def test_match_score_identical_profiles_is_one(item_model: Item2VecModel) -> None:
    vec = build_user_vector({"disco_elysium": 10.0}, item_model)
    profile = UserProfile(user_id="u1", vectors={"steam": vec})
    assert match_score(profile, profile, weights={"steam": 1.0}) == pytest.approx(1.0)


def test_match_score_weighted_average_across_services() -> None:
    """If games sim = 1 and music sim = 0 with weights 0.3/0.7, score = 0.3."""
    a = UserProfile(
        user_id="a",
        vectors={"games": [1.0, 0.0], "music": [1.0, 0.0]},
    )
    b = UserProfile(
        user_id="b",
        vectors={"games": [1.0, 0.0], "music": [0.0, 1.0]},
    )
    score = match_score(a, b, weights={"games": 0.3, "music": 0.7})
    assert score == pytest.approx(0.3)


def test_match_score_renormalizes_weights_that_dont_sum_to_one() -> None:
    """Weights {games: 3, music: 7} should produce the same score as {0.3, 0.7}."""
    a = UserProfile(
        user_id="a",
        vectors={"games": [1.0, 0.0], "music": [1.0, 0.0]},
    )
    b = UserProfile(
        user_id="b",
        vectors={"games": [1.0, 0.0], "music": [0.0, 1.0]},
    )
    raw = match_score(a, b, weights={"games": 3.0, "music": 7.0})
    normalized = match_score(a, b, weights={"games": 0.3, "music": 0.7})
    assert raw == pytest.approx(normalized)


def test_match_score_ignores_services_not_shared_by_both_users() -> None:
    """If weight names a service one user lacks, it's dropped; remaining weights renormalize."""
    a = UserProfile(
        user_id="a",
        vectors={"games": [1.0, 0.0], "music": [1.0, 0.0]},
    )
    b = UserProfile(user_id="b", vectors={"games": [1.0, 0.0]})  # no music
    score = match_score(a, b, weights={"games": 0.3, "music": 0.7})
    # music drops out; only games counts; renormalized weight = 1.0; sim = 1.0.
    assert score == pytest.approx(1.0)


def test_match_score_ignores_services_not_in_weights() -> None:
    """Services present in profiles but not in weights are not considered."""
    a = UserProfile(
        user_id="a",
        vectors={"games": [1.0, 0.0], "films": [1.0, 0.0]},
    )
    b = UserProfile(
        user_id="b",
        vectors={"games": [1.0, 0.0], "films": [0.0, 1.0]},
    )
    # Only games weighted; films disagreement should not reduce the score.
    score = match_score(a, b, weights={"games": 1.0})
    assert score == pytest.approx(1.0)


def test_match_score_no_shared_services_is_zero() -> None:
    a = UserProfile(user_id="a", vectors={"games": [1.0, 0.0]})
    b = UserProfile(user_id="b", vectors={"music": [1.0, 0.0]})
    assert match_score(a, b, weights={"games": 0.5, "music": 0.5}) == 0.0


def test_match_score_rejects_empty_weights() -> None:
    a = UserProfile(user_id="a", vectors={"games": [1.0, 0.0]})
    b = UserProfile(user_id="b", vectors={"games": [1.0, 0.0]})
    with pytest.raises(ValueError, match="weights must not be empty"):
        match_score(a, b, weights={})


def test_match_score_rejects_negative_weights() -> None:
    a = UserProfile(user_id="a", vectors={"games": [1.0, 0.0]})
    b = UserProfile(user_id="b", vectors={"games": [1.0, 0.0]})
    with pytest.raises(ValueError, match="non-negative"):
        match_score(a, b, weights={"games": -1.0})


def test_match_score_rejects_all_zero_weights() -> None:
    a = UserProfile(user_id="a", vectors={"games": [1.0, 0.0]})
    b = UserProfile(user_id="b", vectors={"games": [1.0, 0.0]})
    with pytest.raises(ValueError, match="at least one positive weight"):
        match_score(a, b, weights={"games": 0.0})


# ---------- rank_matches ----------


def test_rank_matches_sorts_descending() -> None:
    query = UserProfile(user_id="q", vectors={"games": [1.0, 0.0]})
    close = UserProfile(user_id="close", vectors={"games": [1.0, 0.0]})
    far = UserProfile(user_id="far", vectors={"games": [0.0, 1.0]})
    middle = UserProfile(
        user_id="middle",
        vectors={"games": [math.sqrt(0.5), math.sqrt(0.5)]},
    )
    ranked = rank_matches(query, [far, close, middle], weights={"games": 1.0})
    ordered_ids = [p.user_id for p, _ in ranked]
    assert ordered_ids == ["close", "middle", "far"]


def test_rank_matches_respects_k() -> None:
    query = UserProfile(user_id="q", vectors={"games": [1.0, 0.0]})
    candidates = [
        UserProfile(user_id=f"c{i}", vectors={"games": [1.0, 0.0]}) for i in range(5)
    ]
    ranked = rank_matches(query, candidates, weights={"games": 1.0}, k=2)
    assert len(ranked) == 2


def test_rank_matches_k_larger_than_candidates_returns_all() -> None:
    query = UserProfile(user_id="q", vectors={"games": [1.0, 0.0]})
    candidates = [UserProfile(user_id="c", vectors={"games": [1.0, 0.0]})]
    ranked = rank_matches(query, candidates, weights={"games": 1.0}, k=10)
    assert len(ranked) == 1


def test_rank_matches_empty_candidates_returns_empty() -> None:
    query = UserProfile(user_id="q", vectors={"games": [1.0, 0.0]})
    assert rank_matches(query, [], weights={"games": 1.0}) == []


def test_rank_matches_rejects_invalid_k() -> None:
    query = UserProfile(user_id="q", vectors={"games": [1.0, 0.0]})
    with pytest.raises(ValueError, match="positive integer"):
        rank_matches(query, [query], weights={"games": 1.0}, k=0)


def test_rank_matches_excludes_query_from_candidates() -> None:
    """A user should never be ranked as their own match."""
    query = UserProfile(user_id="q", vectors={"games": [1.0, 0.0]})
    other = UserProfile(user_id="other", vectors={"games": [1.0, 0.0]})
    ranked = rank_matches(query, [query, other], weights={"games": 1.0})
    ids = [p.user_id for p, _ in ranked]
    assert "q" not in ids


# ---------- end-to-end with real item2vec ----------


def test_end_to_end_dark_user_matches_other_dark_user(item_model: Item2VecModel) -> None:
    """A dark user should rank another dark user above an arena user."""
    dark_a = build_user_vector({g: 10.0 for g in DARK_GAMES[:3]}, item_model)
    dark_b = build_user_vector({g: 10.0 for g in DARK_GAMES[2:]}, item_model)
    arena = build_user_vector({g: 10.0 for g in ARENA_GAMES}, item_model)

    query = UserProfile(user_id="query", vectors={"games": dark_a})
    candidates = [
        UserProfile(user_id="dark_match", vectors={"games": dark_b}),
        UserProfile(user_id="arena_user", vectors={"games": arena}),
    ]
    ranked = rank_matches(query, candidates, weights={"games": 1.0})
    assert ranked[0][0].user_id == "dark_match"
    assert ranked[0][1] > ranked[1][1]
