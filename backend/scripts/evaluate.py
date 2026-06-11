"""Block J: Evaluation framework for SyncUp matching quality.

Run:
    cd backend && source .venv/bin/activate
    python scripts/evaluate.py
    python scripts/evaluate.py --no-cleanup          # keep synthetic rows
    python scripts/evaluate.py --cohort-size 5       # fewer users per group (fast mode)

The script constructs a synthetic cohort with known overlap levels, measures
how well semantic ANN matching surfaces the right users, and produces a
clean report suitable for the KI Challenge scientific rigor criterion.
"""

from __future__ import annotations

import argparse
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pure metric functions (no DB, fully unit-testable)
# ──────────────────────────────────────────────────────────────────────────────


def precision_at_k(
    retrieved: list[Any],
    relevant: set[Any],
    k: int,
) -> float:
    """Fraction of top-k retrieved items that are relevant (standard IR P@k).

    Always divides by k (not by len(retrieved)), so systems returning fewer
    than k results are penalised. This matches the published IR definition.

    Args:
        retrieved: Ordered list of retrieved item IDs.
        relevant: Set of relevant item IDs (ground truth).
        k: Cutoff rank.

    Returns:
        P@k in [0.0, 1.0].
    """
    if not retrieved or not relevant or k == 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / k


def recall_at_k(
    retrieved: list[Any],
    relevant: set[Any],
    k: int,
) -> float:
    """Fraction of relevant items found in top-k retrieved.

    Args:
        retrieved: Ordered list of retrieved item IDs.
        relevant: Set of relevant item IDs (ground truth).
        k: Cutoff rank.

    Returns:
        R@k in [0.0, 1.0].
    """
    if not retrieved or not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def overlap_fraction(a: set[Any], b: set[Any]) -> float:
    """Jaccard index — |A ∩ B| / |A ∪ B|.

    Returns 0.0 for empty inputs to avoid division by zero.
    """
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic cohort data
# ──────────────────────────────────────────────────────────────────────────────

# Each tuple is (name, item_type, genres_csv).
# Text fed to sentence-transformers: "{name} — {item_type}, {genres}"

_POOL_A: list[tuple[str, str, str]] = [
    # Shared base (indices 0–7): all Group A users get these
    ("Disco Elysium", "game", "narrative RPG, philosophical, noir"),
    ("Planescape: Torment", "game", "narrative RPG, philosophical, dark fantasy"),
    ("Baldur's Gate 3", "game", "narrative RPG, fantasy, turn-based"),
    ("Pathfinder: Wrath of the Righteous", "game", "narrative RPG, fantasy"),
    ("Tyranny", "game", "narrative RPG, dark fantasy, moral choices"),
    ("Pillars of Eternity", "game", "narrative RPG, fantasy, introspective"),
    ("Fallout: New Vegas", "game", "narrative RPG, post-apocalyptic, open world"),
    ("Divinity: Original Sin 2", "game", "narrative RPG, fantasy, cooperative"),
    # Unique items (indices 8–14): one per user, assigned in order
    ("Shadowrun: Dragonfall", "game", "narrative RPG, cyberpunk, noir"),
    ("Torment: Tides of Numenera", "game", "narrative RPG, sci-fantasy, philosophical"),
    ("Wasteland 3", "game", "narrative RPG, post-apocalyptic, tactical"),
    ("Knights of the Old Republic 2", "game", "narrative RPG, sci-fi, philosophical"),
    ("Disco Elysium: The Final Cut", "game", "narrative RPG, philosophical, expanded"),
    ("Pentiment", "game", "narrative RPG, historical, artistic"),
    ("Citizen Sleeper", "game", "narrative RPG, sci-fi, dice mechanics"),
]

_POOL_B: list[tuple[str, str, str]] = [
    # Shared base (indices 0–4): all Group B users get these
    ("Hades", "game", "roguelike, action, mythology"),
    ("Dead Cells", "game", "roguelike, action, metroidvania"),
    ("Hollow Knight", "game", "metroidvania, action, dark"),
    ("Enter the Gungeon", "game", "roguelike, bullet hell, action"),
    ("Risk of Rain 2", "game", "roguelike, third-person shooter, action"),
    # Unique items (indices 5–14): two per user, assigned in order
    ("Returnal", "game", "roguelike, third-person shooter, sci-fi"),
    ("Celeste", "game", "platformer, precision, indie"),
    ("Rogue Legacy 2", "game", "roguelike, platformer, action"),
    ("Spelunky 2", "game", "roguelike, platformer, adventure"),
    ("Isaac: Afterbirth+", "game", "roguelike, bullet hell, dark"),
    ("Neon Abyss", "game", "roguelike, action, bullet hell"),
    ("Vampire Survivors", "game", "roguelike, bullet hell, casual"),
    ("Slay the Spire", "game", "roguelike, deckbuilder, strategy"),
    ("Monster Train", "game", "roguelike, deckbuilder, tower defense"),
    ("Curse of the Dead Gods", "game", "roguelike, action, dark fantasy"),
]

_POOL_C: list[tuple[str, str, str]] = [
    # Each Group C user gets 1 shared item + 4 unique items from a diverse sports pool.
    # Shared (index 0):
    ("Rocket League", "game", "sports, vehicular, competitive"),
    # Unique items (indices 1–21, 4 per user for up to 5 users):
    ("FIFA 24", "game", "sports, football, simulation"),
    ("NBA 2K24", "game", "sports, basketball, simulation"),
    ("Madden NFL 25", "game", "sports, american football, simulation"),
    ("NHL 24", "game", "sports, ice hockey, simulation"),
    ("WWE 2K24", "game", "sports, wrestling, simulation"),
    ("PGA Tour 2K25", "game", "sports, golf, simulation"),
    ("F1 24", "game", "sports, racing, simulation"),
    ("Tony Hawk Pro Skater 1+2", "game", "sports, skateboarding, action"),
    ("MLB The Show 24", "game", "sports, baseball, simulation"),
    ("UFC 5", "game", "sports, fighting, simulation"),
    ("Gran Turismo 7", "game", "sports, racing, simulation"),
    ("Forza Motorsport", "game", "sports, racing, open world"),
    ("Football Manager 2024", "game", "sports, management, simulation"),
    ("Cricket 22", "game", "sports, cricket, simulation"),
    ("Riders Republic", "game", "sports, extreme sports, open world"),
    ("Skate 3", "game", "sports, skateboarding, sandbox"),
    ("EA Sports College Football 25", "game", "sports, american football, simulation"),
    ("Tennis World Tour 2", "game", "sports, tennis, simulation"),
    ("AO Tennis 2", "game", "sports, tennis, simulation"),
    ("Olympic Games Tokyo 2020", "game", "sports, multi-sport, party"),
    ("Steep", "game", "sports, extreme sports, open world"),
]

_POOL_OUT: list[tuple[str, str, str]] = [
    # Shared base (indices 0–7): all Out-group users get these
    ("Daft Punk", "artist", "electronic, french house, synth"),
    ("Aphex Twin", "artist", "electronic, ambient, IDM"),
    ("Boards of Canada", "artist", "electronic, ambient, IDM"),
    ("Four Tet", "artist", "electronic, ambient, house"),
    ("Burial", "artist", "electronic, dubstep, ambient"),
    ("Massive Attack", "artist", "trip-hop, electronic, ambient"),
    ("Portishead", "artist", "trip-hop, electronic, dark"),
    ("Bonobo", "artist", "electronic, chillout, jazz"),
    # Unique items (indices 8–14): one per user
    ("Flying Lotus", "artist", "electronic, jazz, hip-hop"),
    ("Bicep", "artist", "electronic, house, techno"),
    ("Jon Hopkins", "artist", "electronic, ambient, post-classical"),
    ("Nicolas Jaar", "artist", "electronic, ambient, minimal techno"),
    ("Objekt", "artist", "electronic, techno, experimental"),
    ("Floating Points", "artist", "electronic, jazz, ambient"),
    ("Ross from Friends", "artist", "electronic, house, lo-fi"),
]

# Per-group config: (n_shared, n_unique_per_user, pool)
#
# Holdout strategy per group:
#   A / B / Out: shared_ids[-1] is the group-wide holdout (all users share it)
#                training uses n_shared-1 shared + n_unique unique items
#   C:           last unique item per user is the holdout (unique per user)
#                training uses all n_shared shared + (n_unique-1) unique items
#
# Training Jaccard  J = shared_train / (items_i + items_j - shared_train):
#   Group A:   7 train-shared + 1 unique  → items=8,  J = 7/(8+8-7) = 7/9  ≈ 0.78
#   Group B:   4 train-shared + 2 unique  → items=6,  J = 4/(6+6-4) = 4/8  = 0.50
#   Group C:   1 train-shared + 3 unique  → items=4,  J = 1/(4+4-1) = 1/7  ≈ 0.14
#              (4th unique item per user is the holdout; each user has different holdout)
#   Out-group: 7 train-shared + 1 unique  → items=8,  J = 7/9 ≈ 0.78 (EDM cluster)
_GROUP_CONFIGS: dict[str, tuple[int, int, list[tuple[str, str, str]]]] = {
    # group → (n_shared, n_unique_per_user, pool)
    "A": (8, 1, _POOL_A),
    "B": (5, 2, _POOL_B),
    "C": (1, 4, _POOL_C),
    "out": (8, 1, _POOL_OUT),
}


@dataclass
class SyntheticUser:
    user_id: uuid.UUID
    group: str  # "A", "B", "C", "out"
    training_item_ids: list[uuid.UUID] = field(default_factory=list)
    holdout_item_ids: list[uuid.UUID] = field(default_factory=list)
    email: str = ""

    def all_item_ids(self) -> list[uuid.UUID]:
        return self.training_item_ids + self.holdout_item_ids


# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────


def _format_vec(vec: list[float]) -> str:
    # Delegate to the production serializer so eval queries can never drift
    # from the formatting used by matches.py / recommendations.py.
    from syncup.db.pgvector import format_vec

    return format_vec(vec)


def _make_item_text(name: str, item_type: str, genres: str) -> str:
    return f"{name} — {item_type}, {genres}"


def _insert_items(
    session: Any,
    pool: list[tuple[str, str, str]],
    embeddings: list[list[float]],
) -> list[uuid.UUID]:
    from syncup.db.models import Item

    item_ids: list[uuid.UUID] = []
    now = datetime.now(UTC)
    for (name, item_type, genres), emb in zip(pool, embeddings, strict=True):
        item = Item(
            id=uuid.uuid4(),
            service="eval_synthetic",
            item_type=item_type,
            external_id=str(uuid.uuid4())[:8],
            name=name,
            # ORM attribute is `meta` (column name "metadata"); passing metadata=
            # silently sets a non-mapped attribute and leaves the column as {}.
            meta={"genres": genres.split(", ")},
            embedding=emb,
            embedding_computed_at=now,
            created_at=now,
        )
        session.add(item)
        item_ids.append(item.id)
    session.flush()
    return item_ids


def _insert_user(session: Any, group: str, index: int) -> uuid.UUID:
    from syncup.db.models import User

    uid = uuid.uuid4()
    now = datetime.now(UTC)
    user = User(
        id=uid,
        email=f"eval-synthetic-{group}{index}@syncup.internal",
        display_name=f"Eval {group}{index}",
        password_hash="$2b$12$fakehash_eval",  # noqa: S106
        is_matchable=True,  # synthetic users must be matchable to mirror production ANN path
        onboarded=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return uid


def _assign_items_to_user(
    session: Any,
    user_id: uuid.UUID,
    item_scores: list[tuple[uuid.UUID, float]],
    excluded: bool = False,
) -> None:
    """Insert user_items rows. item_scores is a list of (item_id, engagement_score) pairs.

    Varying engagement scores across items exercises the log1p dampening path in
    build_user_embedding; constant scores would collapse to unweighted averaging.
    """
    from syncup.db.models import UserItem

    now = datetime.now(UTC)
    for item_id, engagement_score in item_scores:
        ui = UserItem(
            id=uuid.uuid4(),
            user_id=user_id,
            item_id=item_id,
            engagement_score=engagement_score,
            raw_value=100.0,
            raw_type="consumption",
            fetched_at=now,
            excluded=excluded,
        )
        session.add(ui)
    session.flush()


def _build_embedding_for_user(session: Any, user_id: uuid.UUID) -> None:
    from syncup.api.routes.embeddings import build_user_embedding

    build_user_embedding(session, user_id)


def _ann_matching_query(
    session: Any,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[uuid.UUID]:
    """Return top-limit user IDs (excluding self) ordered by cosine similarity."""
    from sqlalchemy import select, text

    from syncup.db.models import EMBEDDING_DIM, UserEmbedding

    row = session.execute(
        select(UserEmbedding.embedding).where(
            UserEmbedding.user_id == user_id,
            UserEmbedding.service == "combined",
        )
    ).scalar_one_or_none()
    if row is None:
        return []

    vec_str = _format_vec(list(row))
    # Mirror production ANN filter: is_matchable=true restricts to real candidates.
    # Email filter further restricts to synthetic cohort (no real user contamination).
    sql = text(
        f"SELECT user_id FROM user_embeddings"
        f" WHERE service = 'combined'"
        f"   AND user_id != :uid"
        f"   AND user_id IN ("
        f"       SELECT id FROM users"
        f"       WHERE is_matchable = true"
        f"         AND email LIKE 'eval-synthetic-%'"
        f"   )"
        f" ORDER BY embedding <=> CAST(:vec AS vector({EMBEDDING_DIM}))"
        f" LIMIT :lim"
    )
    rows = session.execute(sql, {"uid": str(user_id), "vec": vec_str, "lim": limit}).all()
    return [uuid.UUID(str(r.user_id)) for r in rows]


def _ann_item_query(
    session: Any,
    user_id: uuid.UUID,
    limit: int = 10,
) -> list[uuid.UUID]:
    """Return top-limit item IDs not owned by the user, ordered by cosine similarity."""
    from sqlalchemy import select, text

    from syncup.db.models import EMBEDDING_DIM, UserEmbedding

    row = session.execute(
        select(UserEmbedding.embedding).where(
            UserEmbedding.user_id == user_id,
            UserEmbedding.service == "combined",
        )
    ).scalar_one_or_none()
    if row is None:
        return []

    vec_str = _format_vec(list(row))
    # Search the full item catalog (not just synthetic items) to match production
    # behaviour — the holdout item must compete against all real items.
    sql = text(
        f"SELECT i.id FROM items i"
        f" WHERE i.embedding IS NOT NULL"
        f"   AND NOT EXISTS ("
        f"       SELECT 1 FROM user_items ui"
        f"       WHERE ui.user_id = :uid AND ui.item_id = i.id"
        f"   )"
        f" ORDER BY i.embedding <=> CAST(:vec AS vector({EMBEDDING_DIM}))"
        f" LIMIT :lim"
    )
    rows = session.execute(sql, {"uid": str(user_id), "vec": vec_str, "lim": limit}).all()
    return [uuid.UUID(str(r.id)) for r in rows]


def _heuristic_score_for_pair(
    session: Any,
    user_a: uuid.UUID,
    user_b: uuid.UUID,
    popularity: dict[uuid.UUID, int] | None = None,
) -> float:
    from sqlalchemy import select, text

    from syncup.db.models import UserItem
    from syncup.matching.heuristic import heuristic_score

    # Fetch item IDs for each user (not excluded)
    def _get_items(uid: uuid.UUID) -> frozenset[uuid.UUID]:
        rows = session.execute(
            select(UserItem.item_id).where(
                UserItem.user_id == uid,
                UserItem.excluded.is_(False),
            )
        ).all()
        return frozenset(r.item_id for r in rows)

    a_items = _get_items(user_a)
    b_items = _get_items(user_b)

    if not a_items or not b_items:
        return 0.0

    if popularity is None:
        # Fallback: build popularity from the pair only (degenerate — all shared items
        # get count=2, unique items get count=1). Prefer passing a cohort-wide
        # popularity dict from the caller for meaningful rarity scores.
        all_ids = list(a_items | b_items)
        pop_rows = session.execute(
            text(
                "SELECT item_id, COUNT(*) AS cnt FROM user_items"
                " WHERE item_id = ANY(:ids)"
                " GROUP BY item_id"
            ),
            {"ids": [str(i) for i in all_ids]},
        ).all()
        popularity = {uuid.UUID(str(r.item_id)): int(r.cnt) for r in pop_rows}

    return heuristic_score(a_items, b_items, popularity)


def _semantic_score_for_pair(session: Any, user_a: uuid.UUID, user_b: uuid.UUID) -> float:

    from sqlalchemy import text

    sql = text(
        "SELECT 1 - (ea.embedding <=> eb.embedding) AS score"
        " FROM user_embeddings ea, user_embeddings eb"
        " WHERE ea.user_id = :ua AND ea.service = 'combined'"
        "   AND eb.user_id = :ub AND eb.service = 'combined'"
    )
    row = session.execute(sql, {"ua": str(user_a), "ub": str(user_b)}).one_or_none()
    if row is None:
        return 0.0
    return max(0.0, min(1.0, float(row.score)))


def _cleanup_synthetic(session: Any, user_ids: list[uuid.UUID]) -> None:
    from sqlalchemy import text

    if not user_ids:
        session.execute(text("DELETE FROM items WHERE service = 'eval_synthetic'"))
        session.commit()
        return

    # Delete in FK-safe order; match_cache is explicitly cleared before users
    uid_strs = [str(u) for u in user_ids]
    session.execute(
        text("DELETE FROM match_cache WHERE user_a_id = ANY(:ids) OR user_b_id = ANY(:ids)"),
        {"ids": uid_strs},
    )
    session.execute(
        text("DELETE FROM user_embeddings WHERE user_id = ANY(:ids)"),
        {"ids": uid_strs},
    )
    session.execute(
        text("DELETE FROM user_items WHERE user_id = ANY(:ids)"),
        {"ids": uid_strs},
    )
    session.execute(
        text("DELETE FROM users WHERE id = ANY(:ids)"),
        {"ids": uid_strs},
    )
    session.execute(
        text("DELETE FROM items WHERE service = 'eval_synthetic'"),
    )
    session.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Cohort construction
# ──────────────────────────────────────────────────────────────────────────────


def build_cohort(session: Any, users_per_group: int = 5) -> list[SyntheticUser]:
    """Construct synthetic cohort and persist to DB.

    Within-group item overlap is deliberately varied:
    - Group A: 7 train-shared + 1 unique  → train Jaccard = 7/(8+8-7) = 7/9 ≈ 0.78
              (holdout = shared_ids[-1], same for all A users)
    - Group B: 4 train-shared + 2 unique  → train Jaccard = 4/(6+6-4) = 4/8 = 0.50
              (holdout = shared_ids[-1], same for all B users)
    - Group C: 1 train-shared + 3 unique  → train Jaccard = 1/(4+4-1) = 1/7 ≈ 0.14
              (holdout = last unique item per user — each user has a distinct holdout)
    - Out-group: 7 train-shared + 1 unique  → train Jaccard = 7/9 ≈ 0.78 (EDM)
              (holdout = shared_ids[-1], same for all Out users)

    Engagement scores are varied 0.2–1.0 across items (seeded per user) so that
    the log1p dampening in build_user_embedding has discriminative effect.
    """
    from syncup.embeddings.semantic import embed_batch

    # Pool size per group: n_shared + n_unique * users_per_group
    all_texts: list[str] = []
    pool_offsets: dict[str, tuple[int, int]] = {}
    for group, (n_shared, n_unique, pool) in _GROUP_CONFIGS.items():
        pool_size = n_shared + n_unique * users_per_group
        start = len(all_texts)
        all_texts += [_make_item_text(n, t, g) for n, t, g in pool[:pool_size]]
        pool_offsets[group] = (start, len(all_texts))

    total_items = len(all_texts)
    print(f"  Embedding synthetic item pools ({total_items} items across 4 groups)...")
    all_embeddings = embed_batch(all_texts)
    print(f"  Embedded {total_items} items.")

    # Insert all pool items into DB
    pool_item_ids: dict[str, list[uuid.UUID]] = {}
    for group, (_n_shared, _n_unique, pool) in _GROUP_CONFIGS.items():
        start, end = pool_offsets[group]
        pool_size = end - start
        ids = _insert_items(session, pool[:pool_size], all_embeddings[start:end])
        pool_item_ids[group] = ids
    session.commit()

    _group_seed = {"A": 100, "B": 200, "C": 300, "out": 400}

    # Create users and assign items
    synthetic_users: list[SyntheticUser] = []
    for group in ("A", "B", "C", "out"):
        n_shared, n_unique, _ = _GROUP_CONFIGS[group]
        all_pool_ids = pool_item_ids[group]
        shared_ids = all_pool_ids[:n_shared]

        # A/B/Out: group-wide shared holdout (shared_ids[-1]); Group C: per-user holdout
        if group != "C":
            group_holdout = shared_ids[-1]
            train_shared = shared_ids[:-1]
        else:
            group_holdout = None  # set per-user below
            train_shared = list(shared_ids)  # all shared items in training for C

        for i in range(users_per_group):
            user_id = _insert_user(session, group, i)

            unique_start = n_shared + i * n_unique
            unique_ids = all_pool_ids[unique_start : unique_start + n_unique]

            if group == "C":
                this_holdout = unique_ids[-1]
                training_ids = list(train_shared) + list(unique_ids[:-1])
            else:
                this_holdout = group_holdout  # type: ignore[assignment]
                training_ids = list(train_shared) + list(unique_ids)

            # Vary engagement scores 0.2–1.0 (seeded per user for reproducibility)
            rng = random.Random(_group_seed[group] + i)
            n_items = len(training_ids)
            scores = [0.2 + 0.8 * (j / max(n_items - 1, 1)) for j in range(n_items)]
            rng.shuffle(scores)
            item_scores = list(zip(training_ids, scores, strict=True))

            _assign_items_to_user(session, user_id, item_scores)
            # this_holdout is in `items` but NOT in user_items → appears as candidate

            su = SyntheticUser(
                user_id=user_id,
                group=group,
                training_item_ids=list(training_ids),
                holdout_item_ids=[this_holdout],
                email=f"eval-synthetic-{group}{i}@syncup.internal",
            )
            synthetic_users.append(su)

    session.commit()

    # Build user embeddings from training items only
    print(f"  Building embeddings for {len(synthetic_users)} synthetic users...")
    for su in synthetic_users:
        _build_embedding_for_user(session, su.user_id)
    session.commit()
    print("  Done.")

    return synthetic_users


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation functions
# ──────────────────────────────────────────────────────────────────────────────


def run_matching_evaluation(
    session: Any,
    synthetic_users: list[SyntheticUser],
) -> dict[str, float]:
    """Compute Recall@5 per group.

    For each user in a group, query top-5 ANN matches and measure what fraction
    of the other same-group members appear. Recall@5 avoids the structural
    ceiling of P@5: with 5 users/group each user has 4 relevant members, so
    P@5 maxes at 4/5=0.80 regardless of ranking quality; Recall@5 maxes at 1.0.
    """
    by_group: dict[str, list[SyntheticUser]] = {}
    for su in synthetic_users:
        by_group.setdefault(su.group, []).append(su)

    results: dict[str, float] = {}
    for group, members in by_group.items():
        member_ids = {su.user_id for su in members}
        recalls: list[float] = []
        for su in members:
            relevant = member_ids - {su.user_id}
            top_k = _ann_matching_query(session, su.user_id, limit=5)
            recalls.append(recall_at_k(top_k, relevant, k=5))
        results[group] = sum(recalls) / len(recalls) if recalls else 0.0

    return results


def run_holdout_evaluation(
    session: Any,
    synthetic_users: list[SyntheticUser],
    k: int = 10,
) -> dict[str, Any]:
    """Compute Hit Rate@k using held-out items as ground truth.

    Each user has exactly 1 holdout item; recall_at_k with a single relevant item
    is binary (0 or 1). The mean is therefore Hit Rate@k — the fraction of users
    whose held-out item appears in their top-k recommendations. This is the
    standard metric name for this setting; calling it Recall@k would imply a
    multi-item relevance set.
    """
    hits: list[float] = []
    group_hits: dict[str, list[float]] = {}

    for su in synthetic_users:
        if not su.holdout_item_ids:
            continue
        relevant = set(su.holdout_item_ids)
        retrieved = _ann_item_query(session, su.user_id, limit=k)
        hit = recall_at_k(retrieved, relevant, k=k)  # binary when |relevant|=1
        hits.append(hit)
        group_hits.setdefault(su.group, []).append(hit)

    n = len(hits)
    per_group = {g: sum(vals) / len(vals) for g, vals in group_hits.items() if vals}
    return {
        "hit_rate_at_k": sum(hits) / n if n else 0.0,
        "k": k,
        "n_users": n,
        "hit_rate_per_group": per_group,
    }


def _spearman_r(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation coefficient (pure Python, no scipy)."""
    n = len(xs)
    if n < 2:
        return float("nan")

    def _rank(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        result = [0.0] * n
        for r, idx in enumerate(order, 1):
            result[idx] = float(r)
        return result

    rx, ry = _rank(xs), _rank(ys)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry, strict=True))
    denom = n * (n * n - 1)
    return float("nan") if denom == 0 else 1.0 - 6.0 * d2 / denom


def _build_cohort_popularity(
    session: Any,
    synthetic_users: list[SyntheticUser],
) -> dict[uuid.UUID, int]:
    """Count how many synthetic users own each item (full-cohort popularity).

    Using only the pair's items would give every shared item count=2, making
    the rarity term constant and the heuristic score uninformative.  Counting
    across all cohort users reflects real-world rarity: items shared by all
    group members score lower rarity than items owned by only one user.
    """
    from sqlalchemy import text

    uid_strs = [str(su.user_id) for su in synthetic_users]
    rows = session.execute(
        text(
            "SELECT item_id, COUNT(*) AS cnt FROM user_items"
            " WHERE user_id = ANY(:ids)"
            " GROUP BY item_id"
        ),
        {"ids": uid_strs},
    ).all()
    return {uuid.UUID(str(r.item_id)): int(r.cnt) for r in rows}


def run_mode_comparison(
    session: Any,
    synthetic_users: list[SyntheticUser],
) -> dict[str, Any]:
    """Compare semantic vs heuristic scores for within-group pairs (A, B, out).

    Group C is excluded — near-zero training Jaccard means all heuristic scores
    would be 0 and the comparison would be degenerate.

    Reports per-group averages and the Spearman rank correlation between
    heuristic and semantic rankings across all pairs.  A high positive Spearman r
    confirms the two metrics agree directionally; a large delta in means confirms
    semantic is quantitatively stronger.
    """
    cohort_popularity = _build_cohort_popularity(session, synthetic_users)

    all_semantic: list[float] = []
    all_heuristic: list[float] = []
    group_results: dict[str, dict[str, float]] = {}

    for group in ("A", "B", "out"):
        members = [su for su in synthetic_users if su.group == group]
        sem: list[float] = []
        heu: list[float] = []
        for i, ua in enumerate(members):
            for ub in members[i + 1 :]:
                s = _semantic_score_for_pair(session, ua.user_id, ub.user_id)
                h = _heuristic_score_for_pair(
                    session, ua.user_id, ub.user_id, popularity=cohort_popularity
                )
                sem.append(s)
                heu.append(h)
                all_semantic.append(s)
                all_heuristic.append(h)
        n = len(sem)
        group_results[group] = {
            "semantic_avg": sum(sem) / n if n else 0.0,
            "heuristic_avg": sum(heu) / n if n else 0.0,
            "n_pairs": float(n),
        }

    def _avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "group_results": group_results,
        "semantic_avg": _avg(all_semantic),
        "heuristic_avg": _avg(all_heuristic),
        "n_pairs": len(all_semantic),
        "spearman_r": _spearman_r(all_heuristic, all_semantic),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Centroid-collapse probe (mixed-domain users)
# ──────────────────────────────────────────────────────────────────────────────


def _group_centroid(session: Any, user_ids: list[uuid.UUID]) -> list[float] | None:
    """Mean of the group's combined embeddings, L2-renormalised. None if empty."""
    import numpy as np
    from sqlalchemy import select

    from syncup.db.models import UserEmbedding

    vecs: list[list[float]] = []
    for uid in user_ids:
        row = session.execute(
            select(UserEmbedding.embedding).where(
                UserEmbedding.user_id == uid, UserEmbedding.service == "combined"
            )
        ).scalar_one_or_none()
        if row is not None:
            vecs.append(list(row))
    if not vecs:
        return None
    arr = np.mean(np.asarray(vecs, dtype=np.float64), axis=0)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return None
    return list(arr / norm)


def _cosine(session: Any, user_id: uuid.UUID, centroid: list[float]) -> float | None:
    import numpy as np
    from sqlalchemy import select

    from syncup.db.models import UserEmbedding

    row = session.execute(
        select(UserEmbedding.embedding).where(
            UserEmbedding.user_id == user_id, UserEmbedding.service == "combined"
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    a = np.asarray(list(row), dtype=np.float64)
    b = np.asarray(centroid, dtype=np.float64)
    return float(a @ b)  # both unit-norm → dot product is cosine


def run_centroid_collapse_probe(
    session: Any,
    synthetic_users: list[SyntheticUser],
    n_mixed: int = 3,
) -> dict[str, Any]:
    """Measure (not just assert) centroid collapse for mixed-domain users.

    Builds a few users whose libraries blend Group-A RPG items with Out-group EDM
    items in equal measure. Their averaged taste vector should land between the two
    clusters, matching *neither* as strongly as a pure-domain user matches its own.
    Reports the mixed user's cosine to each parent centroid vs the pure-domain
    within-cluster baseline — turning the documented failure mode into evidence.

    Returns mixed_user_ids so the caller can clean them up.
    """
    a_users = [su for su in synthetic_users if su.group == "A"]
    out_users = [su for su in synthetic_users if su.group == "out"]
    if not a_users or not out_users:
        return {}

    # Reuse already-inserted items: 4 RPG items + 4 EDM items.
    rpg_items = a_users[0].training_item_ids[:4]
    edm_items = out_users[0].training_item_ids[:4]
    if len(rpg_items) < 4 or len(edm_items) < 4:
        return {}

    mixed_ids: list[uuid.UUID] = []
    for i in range(n_mixed):
        uid = _insert_user(session, "M", i)
        item_scores = [(iid, 0.8) for iid in (*rpg_items, *edm_items)]
        _assign_items_to_user(session, uid, item_scores)
        mixed_ids.append(uid)
    session.commit()
    for uid in mixed_ids:
        _build_embedding_for_user(session, uid)
    session.commit()

    a_centroid = _group_centroid(session, [su.user_id for su in a_users])
    out_centroid = _group_centroid(session, [su.user_id for su in out_users])
    if a_centroid is None or out_centroid is None:
        return {"mixed_user_ids": mixed_ids}

    # Pure-domain baseline: how close an A user sits to the A centroid.
    a_self = [c for su in a_users if (c := _cosine(session, su.user_id, a_centroid)) is not None]
    mixed_to_rpg = [c for uid in mixed_ids if (c := _cosine(session, uid, a_centroid)) is not None]
    mixed_to_edm = [
        c for uid in mixed_ids if (c := _cosine(session, uid, out_centroid)) is not None
    ]

    def _avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "mixed_user_ids": mixed_ids,
        "n_mixed": n_mixed,
        "pure_a_to_a_centroid": _avg(a_self),
        "mixed_to_rpg_centroid": _avg(mixed_to_rpg),
        "mixed_to_edm_centroid": _avg(mixed_to_edm),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────────────


def print_report(
    matching: dict[str, float],
    holdout: dict[str, Any],
    modes: dict[str, Any],
    users_per_group: int,
    collapse: dict[str, Any] | None = None,
) -> None:
    """Print evaluation report matching roadmap §2.8 format."""
    n_users = users_per_group * 4

    print()
    print("=" * 60)
    print(f"Synthetic cohort evaluation (N={n_users} synthetic users):")
    for group in ("A", "B", "C", "out"):
        label = {
            "A": "high-overlap users correctly ranked",
            "B": "medium-overlap users ranked",
            "C": "low-overlap users ranked",
            "out": "zero-overlap out-group ranked",
        }[group]
        score = matching.get(group, 0.0)
        print(f"  Group {group} recall@5: {score:.2f}  ({label})")

    k = holdout["k"]
    print()
    print(f"Holdout recommendation quality (N={holdout['n_users']} users, k={k}):")
    print(f"  Hit Rate@{k} (pooled): {holdout['hit_rate_at_k']:.2f}")
    per_group: dict[str, float] = holdout.get("hit_rate_per_group", {})
    if per_group:
        print(f"  Hit Rate@{k} by group:")
        for g in ("A", "B", "C", "out"):
            if g in per_group:
                note = {
                    "A": "high overlap — sanity check",
                    "B": "medium overlap",
                    "C": "unique holdout per user — hardest group",
                    "out": "cross-domain — sanity check",
                }.get(g, "")
                print(f"    Group {g}: {per_group[g]:.2f}  ({note})")

    sem = modes["semantic_avg"]
    heu = modes["heuristic_avg"]
    delta_pct = ((sem - heu) / heu * 100) if heu > 0 else float("inf")
    n_pairs = modes["n_pairs"]
    spearman = modes["spearman_r"]
    print()
    print(f"Matching mode comparison (Groups A/B/out, {n_pairs} pairs):")
    print(f"  heuristic:  avg score {heu:.3f}  (rarity-weighted overlap, cohort-wide popularity)")
    if heu > 0:
        print(f"  semantic:   avg score {sem:.3f}  ({delta_pct:+.0f}% vs heuristic)")
    else:
        print(f"  semantic:   avg score {sem:.3f}")
    if not (spearman != spearman):  # nan check
        print(f"  Spearman r (heuristic vs semantic rankings): {spearman:.3f}")
    group_results: dict[str, dict[str, float]] = modes.get("group_results", {})
    if group_results:
        print("  Per-group breakdown:")
        for g in ("A", "B", "out"):
            if g in group_results:
                gr = group_results[g]
                n_g = int(gr["n_pairs"])
                g_sem = gr["semantic_avg"]
                g_heu = gr["heuristic_avg"]
                g_delta = ((g_sem - g_heu) / g_heu * 100) if g_heu > 0 else float("inf")
                print(
                    f"    Group {g}: heuristic {g_heu:.3f}  semantic {g_sem:.3f}"
                    f"  ({g_delta:+.0f}%)  n={n_g} pairs"
                )

    if collapse and "pure_a_to_a_centroid" in collapse:
        print()
        print(f"Centroid-collapse probe (mixed-domain users, N={collapse['n_mixed']}):")
        print(
            f"  pure RPG user → RPG centroid:   {collapse['pure_a_to_a_centroid']:.3f}"
            "  (within-cluster baseline)"
        )
        print(f"  mixed user    → RPG centroid:   {collapse['mixed_to_rpg_centroid']:.3f}")
        print(f"  mixed user    → EDM centroid:   {collapse['mixed_to_edm_centroid']:.3f}")
        drop_rpg = collapse["pure_a_to_a_centroid"] - collapse["mixed_to_rpg_centroid"]
        print(
            f"  → blending two domains pulls the vector to a midpoint: it matches the RPG"
            f" cluster {drop_rpg:+.3f} weaker than a pure RPG user does (centroid collapse,"
            " measured not assumed)."
        )

    print()
    print("Evaluation caveats (self-critical assessment):")
    print("  - Synthetic cohort uses seeded engagement scores (0.2–1.0); log1p dampening")
    print("    is exercised but items are still from a narrow eval vocabulary.")
    print("  - Hit Rate@k pooled across groups is not directly comparable: Group C uses")
    print("    unique holdouts per user (hardest), Out-group items cluster tightly (easy).")
    print("    Group A/B hit rate is the most informative signal.")
    print("  - Recall@5 for Out-group is trivially 1.0 (same EDM cluster). It")
    print("    validates domain separation, not intra-domain ranking quality.")
    print("Known failure modes (production):")
    print("  - Users with < 20 items: degraded recommendation quality (thin signal)")
    print("  - Steam-only users: no genre metadata pre-enrichment → lower embedding quality")
    print("  - Centroid collapse: users whose items span unrelated clusters produce")
    print("    averaged vectors that match neither cluster well")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="SyncUp evaluation framework (Block J)")
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep synthetic rows in the DB after evaluation.",
    )
    parser.add_argument(
        "--cohort-size",
        type=int,
        default=5,
        metavar="N",
        help="Number of users per group (default: 5). Use 2 for a fast smoke test.",
    )
    args = parser.parse_args()

    from syncup.config import Settings
    from syncup.db.session import sessionmaker_for

    settings = Settings()
    factory = sessionmaker_for(settings.database_url)

    users_per_group = args.cohort_size
    synthetic_users: list[SyntheticUser] = []
    mixed_user_ids: list[uuid.UUID] = []

    import sqlalchemy as sa

    with factory() as session:
        # Pre-cleanup: remove leftover synthetic data from any previous run.
        # match_cache must be deleted before users (FK constraint).
        session.execute(
            sa.text(
                "DELETE FROM match_cache WHERE user_a_id IN"
                " (SELECT id FROM users WHERE email LIKE 'eval-synthetic-%')"
                "   OR user_b_id IN"
                " (SELECT id FROM users WHERE email LIKE 'eval-synthetic-%')"
            )
        )
        session.execute(
            sa.text(
                "DELETE FROM user_embeddings WHERE user_id IN"
                " (SELECT id FROM users WHERE email LIKE 'eval-synthetic-%')"
            )
        )
        session.execute(
            sa.text(
                "DELETE FROM user_items WHERE user_id IN"
                " (SELECT id FROM users WHERE email LIKE 'eval-synthetic-%')"
            )
        )
        session.execute(sa.text("DELETE FROM users WHERE email LIKE 'eval-synthetic-%'"))
        session.execute(sa.text("DELETE FROM items WHERE service = 'eval_synthetic'"))
        session.commit()

        try:
            print(f"\nBuilding synthetic cohort ({users_per_group} users/group)...")
            synthetic_users = build_cohort(session, users_per_group=users_per_group)

            print("\nRunning matching evaluation (Recall@5)...")
            matching = run_matching_evaluation(session, synthetic_users)

            print("Running holdout evaluation (Hit Rate@10)...")
            holdout = run_holdout_evaluation(session, synthetic_users, k=10)

            print("Running mode comparison...")
            modes = run_mode_comparison(session, synthetic_users)

            print("Running centroid-collapse probe...")
            collapse = run_centroid_collapse_probe(session, synthetic_users)
            mixed_user_ids.extend(collapse.get("mixed_user_ids", []))

            print_report(matching, holdout, modes, users_per_group, collapse)

        finally:
            if not args.no_cleanup:
                print("\nCleaning up synthetic data...")
                # Use a fresh session — the evaluation session may be in a broken
                # state if an exception occurred during the try block.
                with factory() as cleanup_session:
                    all_ids = [su.user_id for su in synthetic_users] + mixed_user_ids
                    _cleanup_synthetic(cleanup_session, all_ids)
                print("Done.")
            else:
                session.commit()
                print("\n--no-cleanup: synthetic rows retained.")


if __name__ == "__main__":
    main()
