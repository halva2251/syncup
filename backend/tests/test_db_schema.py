"""Schema smoke tests — verify models register cleanly, no live DB needed.

Integration tests that exercise real SQL against pgvector belong in a
separate suite once a test DB is provisioned. These tests are cheap
guardrails against accidental model-registration breakage or silent
dimension drift between training config and the DB schema.
"""

from __future__ import annotations

from syncup.db.base import Base
from syncup.db.models import EMBEDDING_DIM
from syncup.embeddings.item2vec import TrainingConfig

EXPECTED_TABLES = {
    "auth_providers",
    "items",
    "manual_obsessions",
    "match_cache",
    "preference_overrides",
    "service_connections",
    "sessions",
    "user_dimension_weights",
    "user_embeddings",
    "user_items",
    "users",
}


def test_all_expected_tables_registered() -> None:
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_embedding_dim_is_384() -> None:
    """EMBEDDING_DIM must be 384 for all-MiniLM-L6-v2 (sentence-transformers).

    Phase 2 switched from Item2Vec (128-dim) to sentence-transformers
    (384-dim) for cross-domain semantic matching. If this drifts, every
    item and user embedding insert will fail at runtime.
    """
    assert EMBEDDING_DIM == 384


def test_item2vec_training_dim_is_independent() -> None:
    """Item2Vec TrainingConfig.vector_size is decoupled from EMBEDDING_DIM.

    Item2Vec is an optional future enhancement for intra-service
    co-occurrence ranking; it does NOT set the main embedding dimension.
    sentence-transformers (EMBEDDING_DIM=384) is the canonical embedding.
    """
    assert TrainingConfig().vector_size == 128
    assert EMBEDDING_DIM != TrainingConfig().vector_size


def test_users_has_matchable_partial_index() -> None:
    users = Base.metadata.tables["users"]
    partial_indexes = [
        ix for ix in users.indexes if ix.dialect_options["postgresql"].get("where") is not None
    ]
    assert any(ix.name == "idx_users_matchable" for ix in partial_indexes)


def test_match_cache_has_ordering_check() -> None:
    match_cache = Base.metadata.tables["match_cache"]
    check_names = {c.name for c in match_cache.constraints if c.name}
    assert "ck_match_cache_order" in check_names


# ---------------------------------------------------------------------------
# Phase 2 Block A — schema additions
# ---------------------------------------------------------------------------


def test_user_item_has_excluded_column() -> None:
    """UserItem must have an `excluded` boolean column for Phase 2 item exclusion."""
    user_items = Base.metadata.tables["user_items"]
    assert "excluded" in user_items.c, "user_items.excluded column missing"


def test_user_has_vibe_columns() -> None:
    """User must have all four vibe synthesis columns added in Phase 2 Block A."""
    users = Base.metadata.tables["users"]
    for col in ("vibe_summary", "archetype", "key_themes", "vibe_computed_at"):
        assert col in users.c, f"users.{col} column missing"
