"""item2vec: learn item embeddings from co-occurrence in user libraries.

Same math as word2vec, but we train on *items* instead of *words*.
If many users who own Game A also own Game B, A and B end up with similar
vectors. After training, cosine similarity between any two item vectors
approximates how "taste-adjacent" those items are.

Under the hood: gensim's Word2Vec with skip-gram + negative sampling.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import cast

import numpy as np
from gensim.models import Word2Vec


class TrainingMode(IntEnum):
    CBOW = 0
    SKIP_GRAM = 1


@dataclass(frozen=True)
class TrainingConfig:
    """Hyperparameters for item2vec training.

    Defaults are sensible for a first pass; tune once we have real data.
    """

    vector_size: int = 128
    window: int = 10
    min_count: int = 5
    negative: int = 10
    epochs: int = 20
    workers: int = field(default_factory=lambda: os.cpu_count() or 4)
    sg: TrainingMode = TrainingMode.SKIP_GRAM


class Item2VecModel:
    """Thin wrapper over a trained gensim Word2Vec model."""

    def __init__(self, model: Word2Vec) -> None:
        self._model = model

    @classmethod
    def train(
        cls,
        item_sequences: list[list[str]],
        config: TrainingConfig | None = None,
    ) -> Item2VecModel:
        """Train a new model from a list of user libraries.

        Each inner list is one user's items (e.g. Steam game IDs or
        Last.fm artist MBIDs). Order inside each list is treated as
        arbitrary — item2vec uses a sliding window.
        """
        config = config or TrainingConfig()
        model = Word2Vec(
            sentences=item_sequences,
            vector_size=config.vector_size,
            window=config.window,
            min_count=config.min_count,
            negative=config.negative,
            sg=int(config.sg),
            epochs=config.epochs,
            workers=config.workers,
        )
        return cls(model)

    def vector(self, item_id: str) -> list[float]:
        """Return the embedding for a single item.

        Raises:
            KeyError: if item_id is not in the model vocabulary (e.g. filtered
                by min_count during training).
        """
        if item_id not in self._model.wv:
            raise KeyError(
                f"Item {item_id!r} is not in the vocabulary. "
                "It may have been filtered out by min_count during training."
            )
        vec: np.ndarray = self._model.wv[item_id]
        return cast(list[float], vec.tolist())

    def most_similar(self, item_id: str, k: int = 10) -> list[tuple[str, float]]:
        """Return the k most similar items to the given one.

        Raises:
            ValueError: if k < 1.
            KeyError: if item_id is not in the model vocabulary.
        """
        if k < 1:
            raise ValueError(f"k must be a positive integer, got {k}")
        if item_id not in self._model.wv:
            raise KeyError(
                f"Item {item_id!r} is not in the vocabulary. "
                "It may have been filtered out by min_count during training."
            )
        return cast(
            list[tuple[str, float]],
            self._model.wv.most_similar(item_id, topn=k),
        )

    def vocabulary(self) -> list[str]:
        """All item IDs known to the model, in alphabetical order."""
        return sorted(self._model.wv.key_to_index.keys())

    def save(self, path: Path) -> None:
        """Persist the trained model to disk.

        Creates parent directories if they do not exist.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))

    @classmethod
    def load(cls, path: Path) -> Item2VecModel:
        """Load a previously saved model.

        Raises:
            FileNotFoundError: if path does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"No model found at {path}")
        return cls(Word2Vec.load(str(path)))
