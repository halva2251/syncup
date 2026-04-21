"""Sanity test for item2vec: similar items should cluster after training.

We construct synthetic user libraries where users fall into two camps
("dark" games vs "arena" games). A correctly trained item2vec model
should learn this, so querying `most_similar("disco_elysium")` returns
mostly other dark games, not arena games.

If this test fails, the training pipeline is broken — don't move on.
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from syncup.embeddings.item2vec import Item2VecModel, TrainingConfig

DARK_GAMES = ["disco_elysium", "planescape", "bloodborne", "dark_souls", "hollow_knight"]
ARENA_GAMES = ["fortnite", "warzone", "valorant", "apex", "cs2"]


def _synthetic_libraries(seed: int = 42) -> list[list[str]]:
    """Fake libraries: each user is firmly in one camp (no cross-cluster noise).

    We vary the *size* of each library (3-5 items) so the model sees a variety
    of co-occurrence contexts rather than identical sets every time.
    """
    rng = random.Random(seed)
    libraries: list[list[str]] = []
    for _ in range(150):
        size = rng.randint(3, 5)
        lib = rng.sample(DARK_GAMES, size)
        libraries.append(lib)
    for _ in range(150):
        size = rng.randint(3, 5)
        lib = rng.sample(ARENA_GAMES, size)
        libraries.append(lib)
    return libraries


@pytest.fixture(scope="module")
def trained_model() -> Item2VecModel:
    config = TrainingConfig(vector_size=32, window=5, min_count=1, epochs=50)
    return Item2VecModel.train(_synthetic_libraries(), config=config)


def test_vocabulary_contains_all_items(trained_model: Item2VecModel) -> None:
    vocab = set(trained_model.vocabulary())
    assert set(DARK_GAMES + ARENA_GAMES).issubset(vocab)


def test_vocabulary_is_sorted(trained_model: Item2VecModel) -> None:
    vocab = trained_model.vocabulary()
    assert vocab == sorted(vocab)


def test_dark_game_neighbours_are_mostly_dark(trained_model: Item2VecModel) -> None:
    top = trained_model.most_similar("disco_elysium", k=3)
    top_ids = [item for item, _ in top]
    dark_count = sum(1 for item in top_ids if item in DARK_GAMES)
    assert dark_count >= 2, (
        f"Expected at least 2 dark games in top 3, got {top_ids}. "
        "The model did not learn the dark/arena split."
    )


def test_arena_game_neighbours_are_mostly_arena(trained_model: Item2VecModel) -> None:
    top = trained_model.most_similar("fortnite", k=3)
    top_ids = [item for item, _ in top]
    arena_count = sum(1 for item in top_ids if item in ARENA_GAMES)
    assert arena_count >= 2, (
        f"Expected at least 2 arena games in top 3, got {top_ids}."
    )


def test_vector_has_correct_dimension(trained_model: Item2VecModel) -> None:
    vec = trained_model.vector("disco_elysium")
    assert len(vec) == 32


def test_vector_returns_floats(trained_model: Item2VecModel) -> None:
    vec = trained_model.vector("disco_elysium")
    assert all(isinstance(v, float) for v in vec)


def test_unknown_item_raises_key_error(trained_model: Item2VecModel) -> None:
    with pytest.raises(KeyError, match="not in the vocabulary"):
        trained_model.vector("nonexistent_item_xyz")


def test_most_similar_unknown_item_raises_key_error(trained_model: Item2VecModel) -> None:
    with pytest.raises(KeyError, match="not in the vocabulary"):
        trained_model.most_similar("nonexistent_item_xyz")


def test_most_similar_invalid_k_raises_value_error(trained_model: Item2VecModel) -> None:
    with pytest.raises(ValueError, match="k must be a positive integer"):
        trained_model.most_similar("disco_elysium", k=0)


def test_save_and_load_round_trip(trained_model: Item2VecModel, tmp_path: Path) -> None:
    save_path = tmp_path / "models" / "item2vec.bin"
    trained_model.save(save_path)
    assert save_path.exists()

    loaded = Item2VecModel.load(save_path)
    assert trained_model.vector("disco_elysium") == loaded.vector("disco_elysium")


def test_load_missing_path_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Item2VecModel.load(tmp_path / "nonexistent.bin")
