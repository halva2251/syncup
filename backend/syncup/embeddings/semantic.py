"""Semantic embedding wrapper around sentence-transformers.

Uses all-MiniLM-L6-v2 by default (384-dim, matches EMBEDDING_DIM).
The model is lazy-loaded on first use and cached module-level so it is
instantiated at most once per process.

All outputs are L2-normalized so cosine similarity reduces to a dot product.
"""

from __future__ import annotations

import logging
import threading
from typing import cast

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "sentence-transformers is required. Install with: pip install -e '.[ml]'"
    ) from exc

from syncup.config import Settings

# Model name read once at module load — avoids re-reading .env on every call
# and eliminates the Settings() re-instantiation race when encode() is moved
# to a thread pool executor.
# pydantic-settings reads required fields from env vars, not the constructor;
# mypy cannot see that.
_MODEL_NAME: str = Settings().embedding_model_name  # type: ignore[call-arg]

# Module-level model cache and its lock (double-checked locking pattern).
# The lock prevents a double-init race when encode() is offloaded to a thread pool.
_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize each row. Logs a warning for any zero-norm row (degenerate embedding)."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    zero_mask = norms == 0
    if zero_mask.any():
        n_zero = int(zero_mask.sum())
        logger.warning(
            "embed: %d row(s) have zero L2 norm — embedding will be the zero vector. "
            "This indicates degenerate model output for the supplied text.",
            n_zero,
        )
    safe_norms = np.where(zero_mask, 1.0, norms)
    return vectors / safe_norms


def embed_text(text: str) -> list[float]:
    """Embed a single string and return an L2-normalized list of floats.

    Raises:
        ValueError: if text is empty or whitespace-only.
    """
    if not text or not text.strip():
        raise ValueError("embed_text requires a non-empty string")

    model = _get_model()
    raw: np.ndarray = model.encode([text], convert_to_numpy=True)
    normalized = _normalize(raw.astype(np.float64))
    return cast(list[float], normalized[0].tolist())


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return L2-normalized rows.

    Raises:
        ValueError: if texts is empty, or if any individual string is blank.
            Blank strings produce degenerate near-zero embeddings that corrupt
            cosine similarity scores silently — raise early instead.
    """
    if not texts:
        raise ValueError("embed_batch requires a non-empty list")
    blank_indices = [i for i, t in enumerate(texts) if not t.strip()]
    if blank_indices:
        raise ValueError(
            f"embed_batch: blank string(s) at index/indices {blank_indices} — "
            "all texts must be non-empty"
        )

    model = _get_model()
    raw: np.ndarray = model.encode(texts, convert_to_numpy=True, batch_size=256)
    normalized = _normalize(raw.astype(np.float64))
    return cast(list[list[float]], normalized.tolist())
