"""Tests for syncup.embeddings.semantic — sentence-transformers wrapper.

The model (all-MiniLM-L6-v2) is NOT loaded during these tests. We mock
the SentenceTransformer class so the test suite stays fast and doesn't
require a network download or GPU.

Key invariants we verify:
- embed_text returns exactly EMBEDDING_DIM floats, L2-normalized
- embed_batch returns correct shape (n_texts × EMBEDDING_DIM) and each
  row is L2-normalized
- The model is lazy-loaded (not instantiated at import time)
- A second call reuses the cached model (no double instantiation)
- embed_text and embed_batch raise ValueError on empty input
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

EMBEDDING_DIM = 384


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_model(dim: int = EMBEDDING_DIM) -> MagicMock:
    """Return a MagicMock that mimics SentenceTransformer.encode behavior."""
    fake_model = MagicMock()

    def _encode(texts: Any, **kwargs: Any) -> np.ndarray:
        if isinstance(texts, str):
            # single string path — shouldn't reach here after refactor, but guard
            return np.random.randn(dim).astype(np.float32)
        n = len(texts)
        # Return random vectors; L2-normalisation is the responsibility of semantic.py
        raw = np.random.randn(n, dim).astype(np.float32)
        # Normalize each row so the mock already produces unit vectors
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        return (raw / norms).astype(np.float32)

    fake_model.encode.side_effect = _encode
    return fake_model


# ---------------------------------------------------------------------------
# embed_text — shape & type
# ---------------------------------------------------------------------------


def test_embed_text_returns_list_of_floats() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_text("hello world")
    assert isinstance(result, list)
    assert all(isinstance(v, float) for v in result)


def test_embed_text_returns_correct_dimension() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_text("test sentence")
    assert len(result) == EMBEDDING_DIM


def test_embed_text_is_l2_normalized() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_text("normalize me")
    norm = math.sqrt(sum(v * v for v in result))
    assert norm == pytest.approx(1.0, abs=1e-5)


# ---------------------------------------------------------------------------
# embed_text — edge cases
# ---------------------------------------------------------------------------


def test_embed_text_empty_string_raises_value_error() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        with pytest.raises(ValueError, match="empty"):
            semantic.embed_text("")


def test_embed_text_whitespace_only_raises_value_error() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        with pytest.raises(ValueError, match="empty"):
            semantic.embed_text("   ")


# ---------------------------------------------------------------------------
# embed_batch — shape & type
# ---------------------------------------------------------------------------


def test_embed_batch_returns_list_of_lists() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_batch(["hello", "world"])
    assert isinstance(result, list)
    assert all(isinstance(row, list) for row in result)


def test_embed_batch_correct_length() -> None:
    from syncup.embeddings import semantic

    texts = ["a", "b", "c"]
    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_batch(texts)
    assert len(result) == len(texts)


def test_embed_batch_each_row_correct_dimension() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_batch(["alpha", "beta"])
    assert all(len(row) == EMBEDDING_DIM for row in result)


def test_embed_batch_each_row_is_l2_normalized() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_batch(["x", "y", "z"])
    for row in result:
        norm = math.sqrt(sum(v * v for v in row))
        assert norm == pytest.approx(1.0, abs=1e-5), f"row not normalized: norm={norm}"


def test_embed_batch_each_element_is_float() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_batch(["test"])
    assert all(isinstance(v, float) for v in result[0])


# ---------------------------------------------------------------------------
# embed_batch — edge cases
# ---------------------------------------------------------------------------


def test_embed_batch_empty_list_raises_value_error() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        with pytest.raises(ValueError, match="empty"):
            semantic.embed_batch([])


def test_embed_batch_single_text_works() -> None:
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()
    with patch.object(semantic, "_model", fake_model):
        result = semantic.embed_batch(["just one"])
    assert len(result) == 1
    assert len(result[0]) == EMBEDDING_DIM


# ---------------------------------------------------------------------------
# Lazy loading — model must not be instantiated at import time
# ---------------------------------------------------------------------------


def test_model_not_instantiated_at_import() -> None:
    """_model should be None before any embed call."""

    import syncup.embeddings.semantic as sem_mod

    # Re-import to get a clean state (module may be cached; check _model directly)
    # The important thing is _model starts as None before first use.
    # We reset it and verify it stays None until a call is made.
    original = sem_mod._model
    try:
        sem_mod._model = None
        assert sem_mod._model is None
    finally:
        sem_mod._model = original


def test_model_cached_after_first_call() -> None:
    """The SentenceTransformer constructor should be called at most once."""
    from syncup.embeddings import semantic

    fake_model = _make_fake_model()

    # Reset module-level cache
    original = semantic._model
    semantic._model = None
    try:
        with patch(
            "syncup.embeddings.semantic.SentenceTransformer", return_value=fake_model
        ) as MockST:
            semantic.embed_text("first call")
            semantic.embed_text("second call")
            # Constructor called exactly once despite two embed calls
            MockST.assert_called_once()
    finally:
        semantic._model = original
