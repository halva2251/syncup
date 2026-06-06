"""Unit tests for scripts/evaluate.py pure functions.

Tests are intentionally isolated — no DB, no model inference.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

# Names we will stub — saved so we can restore them after loading evaluate.py
_STUB_NAMES = (
    "sqlalchemy",
    "sqlalchemy.orm",
    "syncup",
    "syncup.db",
    "syncup.db.session",
    "syncup.db.models",
    "syncup.embeddings",
    "syncup.embeddings.semantic",
    "syncup.embeddings.user_embeddings",
    "syncup.matching",
    "syncup.matching.heuristic",
    "syncup.config",
)

_originals = {name: sys.modules.get(name) for name in _STUB_NAMES}


def _make_stub(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


for _stub_name in _STUB_NAMES:
    _make_stub(_stub_name)

# Provide just enough attributes for the import to succeed
sys.modules["syncup.db.models"].EMBEDDING_DIM = 384  # type: ignore[attr-defined]

_SCRIPT = pathlib.Path(__file__).parent.parent / "scripts" / "evaluate.py"
_spec = importlib.util.spec_from_file_location("evaluate", _SCRIPT)
_eval_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["evaluate"] = _eval_mod  # needed so @dataclass can resolve cls.__module__
_spec.loader.exec_module(_eval_mod)  # type: ignore[union-attr]

# Restore real modules so the rest of the test suite isn't polluted
for _name, _orig in _originals.items():
    if _orig is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _orig

precision_at_k = _eval_mod.precision_at_k
recall_at_k = _eval_mod.recall_at_k
split_holdout = _eval_mod.split_holdout
overlap_fraction = _eval_mod.overlap_fraction


# ──────────────────────────────────────────────────────────────────────
# precision_at_k
# ──────────────────────────────────────────────────────────────────────


class TestPrecisionAtK:
    def test_perfect_precision(self):
        retrieved = ["a", "b", "c", "d", "e"]
        relevant = {"a", "b", "c", "d", "e"}
        assert precision_at_k(retrieved, relevant, k=5) == 1.0

    def test_zero_precision(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b", "c"}
        assert precision_at_k(retrieved, relevant, k=3) == 0.0

    def test_partial_precision(self):
        retrieved = ["a", "x", "b", "y", "c"]
        relevant = {"a", "b", "c"}
        # 3 out of 5 relevant in top-5 → 0.6
        assert precision_at_k(retrieved, relevant, k=5) == pytest.approx(0.6)

    def test_k_truncates_list(self):
        retrieved = ["a", "b", "x", "c", "d"]
        relevant = {"a", "b", "c", "d"}
        # Only top-2 considered → 2/2 = 1.0
        assert precision_at_k(retrieved, relevant, k=2) == 1.0

    def test_empty_retrieved_returns_zero(self):
        assert precision_at_k([], {"a"}, k=5) == 0.0

    def test_empty_relevant_returns_zero(self):
        assert precision_at_k(["a", "b"], set(), k=5) == 0.0

    def test_k_larger_than_retrieved(self):
        retrieved = ["a", "b"]
        relevant = {"a", "b", "c"}
        # k=10 but only 2 items; 2 relevant / 2 retrieved = 1.0
        assert precision_at_k(retrieved, relevant, k=10) == 1.0


# ──────────────────────────────────────────────────────────────────────
# recall_at_k
# ──────────────────────────────────────────────────────────────────────


class TestRecallAtK:
    def test_perfect_recall(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert recall_at_k(retrieved, relevant, k=3) == 1.0

    def test_partial_recall(self):
        retrieved = ["a", "x", "y", "b", "z"]
        relevant = {"a", "b", "c", "d"}
        # 2 out of 4 relevant found in top-5 → 0.5
        assert recall_at_k(retrieved, relevant, k=5) == pytest.approx(0.5)

    def test_zero_recall(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=3) == 0.0

    def test_empty_relevant_returns_zero(self):
        assert recall_at_k(["a", "b"], set(), k=5) == 0.0

    def test_empty_retrieved_returns_zero(self):
        assert recall_at_k([], {"a"}, k=5) == 0.0

    def test_k_truncates(self):
        # a is at position 0, b at position 1 — top-1 retrieves only a
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=1) == pytest.approx(0.5)


# ──────────────────────────────────────────────────────────────────────
# split_holdout
# ──────────────────────────────────────────────────────────────────────


class TestSplitHoldout:
    def test_splits_correct_sizes(self):
        ids = list(range(10))
        train, holdout = split_holdout(ids, fraction=0.2)
        assert len(train) == 8
        assert len(holdout) == 2

    def test_no_overlap(self):
        ids = list(range(20))
        train, holdout = split_holdout(ids, fraction=0.2)
        assert set(train) & set(holdout) == set()

    def test_all_ids_present(self):
        ids = list(range(20))
        train, holdout = split_holdout(ids, fraction=0.2)
        assert set(train) | set(holdout) == set(ids)

    def test_fraction_zero_all_train(self):
        ids = list(range(5))
        train, holdout = split_holdout(ids, fraction=0.0)
        assert len(holdout) == 0
        assert set(train) == set(ids)

    def test_fraction_one_all_holdout(self):
        ids = list(range(5))
        train, holdout = split_holdout(ids, fraction=1.0)
        assert len(train) == 0
        assert set(holdout) == set(ids)

    def test_deterministic_with_seed(self):
        ids = list(range(100))
        train1, holdout1 = split_holdout(ids, fraction=0.2, seed=42)
        train2, holdout2 = split_holdout(ids, fraction=0.2, seed=42)
        assert train1 == train2
        assert holdout1 == holdout2

    def test_different_seeds_differ(self):
        ids = list(range(100))
        _, holdout1 = split_holdout(ids, fraction=0.2, seed=1)
        _, holdout2 = split_holdout(ids, fraction=0.2, seed=2)
        assert holdout1 != holdout2


# ──────────────────────────────────────────────────────────────────────
# overlap_fraction
# ──────────────────────────────────────────────────────────────────────


class TestOverlapFraction:
    def test_full_overlap(self):
        a = {1, 2, 3}
        b = {1, 2, 3}
        assert overlap_fraction(a, b) == 1.0

    def test_no_overlap(self):
        a = {1, 2, 3}
        b = {4, 5, 6}
        assert overlap_fraction(a, b) == 0.0

    def test_partial_overlap(self):
        a = {1, 2, 3, 4}
        b = {3, 4, 5, 6}
        # intersection = {3, 4} = 2, union = 6 → 2/6 ≈ 0.333
        assert overlap_fraction(a, b) == pytest.approx(2 / 6)

    def test_empty_sets_return_zero(self):
        assert overlap_fraction(set(), set()) == 0.0

    def test_one_empty_returns_zero(self):
        assert overlap_fraction({1, 2}, set()) == 0.0


import pytest
