"""Tests for the heuristic matching scorer."""
from __future__ import annotations

import uuid

import pytest

from syncup.matching.heuristic import (
    SharedHighlight,
    heuristic_breakdown,
    heuristic_score,
    top_shared_highlights,
)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# heuristic_score
# ---------------------------------------------------------------------------


def test_no_overlap_returns_zero() -> None:
    a = frozenset({_uid()})
    b = frozenset({_uid()})
    assert heuristic_score(a, b, {}) == 0.0


def test_empty_sets_return_zero() -> None:
    assert heuristic_score(frozenset(), frozenset(), {}) == 0.0


def test_shared_item_returns_positive() -> None:
    item = _uid()
    a = frozenset({item})
    assert heuristic_score(a, a, {item: 1}) > 0.0


def test_score_is_in_zero_one_range() -> None:
    items = [_uid() for _ in range(10)]
    s = frozenset(items)
    pop = {i: 1 for i in items}
    score = heuristic_score(s, s, pop)
    assert 0.0 <= score < 1.0


def test_niche_item_scores_higher_than_popular() -> None:
    niche = _uid()
    popular = _uid()
    pop = {niche: 2, popular: 1000}
    assert heuristic_score(frozenset({niche}), frozenset({niche}), pop) > heuristic_score(
        frozenset({popular}), frozenset({popular}), pop
    )


def test_more_shared_items_scores_higher() -> None:
    items = [_uid() for _ in range(5)]
    pop = {i: 10 for i in items}
    score_one = heuristic_score(frozenset(items[:1]), frozenset(items[:1]), pop)
    score_five = heuristic_score(frozenset(items), frozenset(items), pop)
    assert score_five > score_one


def test_unknown_item_treated_as_popularity_one() -> None:
    item = _uid()
    a = frozenset({item})
    # Missing from popularity dict — should default to 1, not crash.
    score_missing = heuristic_score(a, a, {})
    score_explicit = heuristic_score(a, a, {item: 1})
    assert score_missing == pytest.approx(score_explicit)


def test_single_unique_item_scores_half() -> None:
    """raw = 1/1 = 1 → normalized = 1/(1+1) = 0.5."""
    item = _uid()
    score = heuristic_score(frozenset({item}), frozenset({item}), {item: 1})
    assert score == pytest.approx(0.5)


def test_partial_overlap_counts_only_shared() -> None:
    shared = _uid()
    only_a = _uid()
    only_b = _uid()
    pop = {shared: 1, only_a: 1, only_b: 1}
    a = frozenset({shared, only_a})
    b = frozenset({shared, only_b})
    # Score should equal score for just the shared item.
    expected = heuristic_score(frozenset({shared}), frozenset({shared}), pop)
    assert heuristic_score(a, b, pop) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# heuristic_breakdown
# ---------------------------------------------------------------------------


def test_breakdown_empty_when_no_shared_services() -> None:
    a = {"steam": frozenset({_uid()})}
    b = {"lastfm": frozenset({_uid()})}
    assert heuristic_breakdown(a, b, {}) == {}


def test_breakdown_only_includes_services_both_have() -> None:
    item = _uid()
    a = {"steam": frozenset({item}), "lastfm": frozenset({_uid()})}
    b = {"steam": frozenset({item})}
    pop = {item: 1}
    result = heuristic_breakdown(a, b, pop)
    assert "steam" in result
    assert "lastfm" not in result


def test_breakdown_excludes_zero_score_services() -> None:
    a = {"steam": frozenset({_uid()})}
    b = {"steam": frozenset({_uid()})}
    # No overlap → score = 0 → should be excluded.
    assert heuristic_breakdown(a, b, {}) == {}


def test_breakdown_per_service_score_positive() -> None:
    item = _uid()
    a = {"steam": frozenset({item})}
    b = {"steam": frozenset({item})}
    pop = {item: 5}
    result = heuristic_breakdown(a, b, pop)
    assert result["steam"] > 0.0


def test_breakdown_multiple_services() -> None:
    steam_item = _uid()
    music_item = _uid()
    a = {"steam": frozenset({steam_item}), "lastfm": frozenset({music_item})}
    b = {"steam": frozenset({steam_item}), "lastfm": frozenset({music_item})}
    pop = {steam_item: 1, music_item: 1}
    result = heuristic_breakdown(a, b, pop)
    assert set(result) == {"steam", "lastfm"}


# ---------------------------------------------------------------------------
# top_shared_highlights
# ---------------------------------------------------------------------------


def test_highlights_empty_when_no_overlap() -> None:
    a = {"steam": frozenset({_uid()})}
    b = {"steam": frozenset({_uid()})}
    assert top_shared_highlights(a, b, {}, {}) == []


def test_highlights_returns_shared_items() -> None:
    item = _uid()
    a = {"steam": frozenset({item})}
    b = {"steam": frozenset({item})}
    names = {item: "Disco Elysium"}
    pop = {item: 1}
    result = top_shared_highlights(a, b, names, pop)
    assert result == [SharedHighlight(service="steam", item_name="Disco Elysium")]


def test_highlights_respects_limit() -> None:
    items = [_uid() for _ in range(10)]
    s = frozenset(items)
    a = {"steam": s}
    b = {"steam": s}
    names = {i: f"Game {n}" for n, i in enumerate(items)}
    pop = {i: 1 for i in items}
    result = top_shared_highlights(a, b, names, pop, limit=3)
    assert len(result) == 3


def test_highlights_niche_items_first() -> None:
    niche = _uid()
    popular = _uid()
    a = {"steam": frozenset({niche, popular})}
    b = {"steam": frozenset({niche, popular})}
    names = {niche: "Niche Game", popular: "Popular Game"}
    pop = {niche: 2, popular: 1000}
    result = top_shared_highlights(a, b, names, pop, limit=2)
    # Most niche item should come first.
    assert result[0].item_name == "Niche Game"


def test_highlights_skips_items_without_names() -> None:
    named = _uid()
    unnamed = _uid()
    a = {"steam": frozenset({named, unnamed})}
    b = {"steam": frozenset({named, unnamed})}
    names = {named: "Known Game"}  # unnamed has no entry
    pop = {named: 1, unnamed: 1}
    result = top_shared_highlights(a, b, names, pop)
    assert all(h.item_name != "" for h in result)
    assert len(result) == 1
