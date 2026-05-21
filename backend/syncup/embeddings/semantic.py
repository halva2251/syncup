"""Semantic embedding wrapper around sentence-transformers.

Uses all-MiniLM-L6-v2 by default (384-dim, matches EMBEDDING_DIM).
The model is lazy-loaded on first use and cached module-level so it is
instantiated at most once per process.

All outputs are L2-normalized so cosine similarity reduces to a dot product.
"""

from __future__ import annotations

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "sentence-transformers is required. Install with: pip install -e '.[ml]'"
    ) from exc

from syncup.config import Settings

# Module-level cache — None until first embed_text / embed_batch call.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        model_name = Settings().embedding_model_name
        _model = SentenceTransformer(model_name)
    return _model


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize each row. Rows with zero norm are left as-is (shouldn't happen)."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


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
    return normalized[0].tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return L2-normalized rows.

    Raises:
        ValueError: if texts is empty.
    """
    if not texts:
        raise ValueError("embed_batch requires a non-empty list")

    model = _get_model()
    raw: np.ndarray = model.encode(texts, convert_to_numpy=True, batch_size=256)
    normalized = _normalize(raw.astype(np.float64))
    return normalized.tolist()
