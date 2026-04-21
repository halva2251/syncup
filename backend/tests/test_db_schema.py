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


def test_embedding_dim_matches_training_default() -> None:
    """The DB vector size must match what item2vec trains by default.

    If this ever drifts, user embeddings computed by build_user_vector
    will not fit into user_embeddings.embedding and every insert will
    fail at runtime. Keep them lockstep.
    """
    assert EMBEDDING_DIM == TrainingConfig().vector_size


def test_users_has_matchable_partial_index() -> None:
    users = Base.metadata.tables["users"]
    partial_indexes = [
        ix
        for ix in users.indexes
        if ix.dialect_options["postgresql"].get("where") is not None
    ]
    assert any(ix.name == "idx_users_matchable" for ix in partial_indexes)


def test_match_cache_has_ordering_check() -> None:
    match_cache = Base.metadata.tables["match_cache"]
    check_names = {c.name for c in match_cache.constraints if c.name}
    assert "ck_match_cache_order" in check_names
