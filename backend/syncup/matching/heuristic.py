"""Heuristic matcher: item-overlap scoring weighted by item rarity.

Used as the live matching engine until Item2Vec embeddings are trained.
Niche overlap (both love Disco Elysium) scores higher than mainstream
overlap (both own CS2) because rare shared taste is a stronger signal.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class SharedHighlight:
    service: str
    item_name: str


def heuristic_score(
    a_items: frozenset[uuid.UUID],
    b_items: frozenset[uuid.UUID],
    popularity: dict[uuid.UUID, int],
) -> float:
    """Rarity-weighted overlap score, normalised to [0, 1).

    Each shared item contributes 1/popularity(item). The raw sum is then
    mapped to [0, 1) via raw/(raw+1) so scores are comparable across pairs
    with different numbers of shared items.
    """
    shared = a_items & b_items
    if not shared:
        return 0.0
    raw = sum(1.0 / max(popularity.get(item, 1), 1) for item in shared)
    return raw / (raw + 1.0)


def heuristic_breakdown(
    a_by_service: dict[str, frozenset[uuid.UUID]],
    b_by_service: dict[str, frozenset[uuid.UUID]],
    popularity: dict[uuid.UUID, int],
) -> dict[str, float]:
    """Per-service heuristic scores. Services with zero overlap are omitted."""
    result: dict[str, float] = {}
    for service in set(a_by_service) & set(b_by_service):
        score = heuristic_score(a_by_service[service], b_by_service[service], popularity)
        if score > 0:
            result[service] = score
    return result


def top_shared_highlights(
    a_by_service: dict[str, frozenset[uuid.UUID]],
    b_by_service: dict[str, frozenset[uuid.UUID]],
    item_names: dict[uuid.UUID, str],
    popularity: dict[uuid.UUID, int],
    limit: int = 20,
    eligible_item_ids: frozenset[uuid.UUID] | None = None,
) -> list[SharedHighlight]:
    """Return the most niche shared items across all services, rarest first.

    When ``eligible_item_ids`` is supplied, only those shared items are
    returned. This lets the feed restrict its highlighted tags to items that
    are prominent in both users' visible taste profiles.
    """
    candidates: list[tuple[float, str, str]] = []
    for service in set(a_by_service) & set(b_by_service):
        for item_id in a_by_service[service] & b_by_service[service]:
            if eligible_item_ids is not None and item_id not in eligible_item_ids:
                continue
            name = item_names.get(item_id)
            if not name:
                continue
            rarity = 1.0 / max(popularity.get(item_id, 1), 1)
            candidates.append((rarity, service, name))
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    return [SharedHighlight(service=svc, item_name=name) for _, svc, name in candidates[:limit]]
