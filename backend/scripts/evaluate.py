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


def split_holdout(
    item_ids: list[Any],
    fraction: float,
    seed: int = 42,
) -> tuple[list[Any], list[Any]]:
    """Split item IDs into training and holdout sets.

    Args:
        item_ids: List of item identifiers to split.
        fraction: Fraction to place in holdout (0.0 = all train, 1.0 = all holdout).
        seed: Random seed for reproducibility.

    Returns:
        (train_ids, holdout_ids) — disjoint, together exhausting item_ids.
    """
    rng = random.Random(seed)
    shuffled = list(item_ids)
    rng.shuffle(shuffled)
    n_holdout = int(len(shuffled) * fraction)
    return shuffled[n_holdout:], shuffled[:n_holdout]


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

# Per-group config: (shared_count, unique_per_user)
# shared_ids[-1] is withheld as holdout (not in user_items), so training Jaccard
# uses only (n_shared - 1) train-shared items:
#   training_J(i,j) = train_shared / (train_per_user_i + train_per_user_j - train_shared)
# Group A: 7 train-shared + 1 unique  → train items=8, J = 7/(8+8-7) = 7/9  ≈ 0.78
# Group B: 4 train-shared + 2 unique  → train items=6, J = 4/(6+6-4) = 4/8  = 0.50
# Group C: 0 train-shared + 4 unique  → train items=4, J = 0/(4+4-0) = 0/8  = 0.00
# Out:     7 train-shared + 1 unique  → train items=8, J = 7/9 ≈ 0.78 (within out-group)
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
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


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
    for (name, item_type, genres), emb in zip(pool, embeddings):
        item = Item(
            id=uuid.uuid4(),
            service="eval_synthetic",
            item_type=item_type,
            external_id=str(uuid.uuid4())[:8],
            name=name,
            metadata={"genres": genres.split(", ")},
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
        is_matchable=False,  # prevent synthetic users appearing in real match results
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
    item_ids: list[uuid.UUID],
    excluded: bool = False,
) -> None:
    from syncup.db.models import UserItem

    now = datetime.now(UTC)
    for item_id in item_ids:
        ui = UserItem(
            id=uuid.uuid4(),
            user_id=user_id,
            item_id=item_id,
            engagement_score=0.8,
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
    # Restrict to synthetic cohort users only (excludes real users from the DB)
    sql = text(
        f"SELECT user_id FROM user_embeddings"
        f" WHERE service = 'combined'"
        f"   AND user_id != :uid"
        f"   AND user_id IN (SELECT id FROM users WHERE email LIKE 'eval-synthetic-%')"
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
    sql = text(
        f"SELECT i.id FROM items i"
        f" WHERE i.embedding IS NOT NULL"
        f"   AND i.service = 'eval_synthetic'"
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
    - Group A: 7 train-shared + 1 holdout-shared + 1 unique  → train Jaccard ≈ 7/9 ≈ 78%
    - Group B: 4 train-shared + 1 holdout-shared + 2 unique  → train Jaccard ≈ 4/7 ≈ 57%
    - Group C: 0 train-shared + 1 holdout-shared + 4 unique  → train Jaccard ≈ 0/9 ≈ 0%
    - Out-group: 7 train-shared + 1 holdout-shared + 1 unique (EDM, 0% cross-group overlap)

    Holdout: shared_ids[-1] is held out for all users in the group — it is in the `items`
    table with an embedding but NOT in any user_items, so it appears as a recommendation
    candidate. All users within a group share the same holdout item.
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
    for group, (n_shared, n_unique, pool) in _GROUP_CONFIGS.items():
        start, end = pool_offsets[group]
        pool_size = end - start
        ids = _insert_items(session, pool[:pool_size], all_embeddings[start:end])
        pool_item_ids[group] = ids
    session.commit()

    # Create users and assign items
    synthetic_users: list[SyntheticUser] = []
    for group in ("A", "B", "C", "out"):
        n_shared, n_unique, _ = _GROUP_CONFIGS[group]
        all_pool_ids = pool_item_ids[group]

        # shared_ids[-1] is the group-wide holdout; shared_ids[:-1] go to training
        shared_ids = all_pool_ids[:n_shared]
        holdout_item = shared_ids[-1]  # same for every user in this group
        train_shared = shared_ids[:-1]  # n_shared - 1 items used for training

        for i in range(users_per_group):
            user_id = _insert_user(session, group, i)

            unique_start = n_shared + i * n_unique
            unique_ids = all_pool_ids[unique_start : unique_start + n_unique]
            training_ids = train_shared + unique_ids

            _assign_items_to_user(session, user_id, training_ids, excluded=False)
            # holdout_item is in `items` but NOT in user_items → appears as candidate

            su = SyntheticUser(
                user_id=user_id,
                group=group,
                training_item_ids=list(training_ids),
                holdout_item_ids=[holdout_item],
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
    """Compute Precision@5 per group.

    For each user in a group, query top-5 ANN matches and check how many
    belong to the same group. Ground truth: same-group users are "relevant".
    """
    by_group: dict[str, list[SyntheticUser]] = {}
    for su in synthetic_users:
        by_group.setdefault(su.group, []).append(su)

    results: dict[str, float] = {}
    for group, members in by_group.items():
        member_ids = {su.user_id for su in members}
        precisions: list[float] = []
        for su in members:
            relevant = member_ids - {su.user_id}
            top_k = _ann_matching_query(session, su.user_id, limit=5)
            p = precision_at_k(top_k, relevant, k=5)
            precisions.append(p)
        results[group] = sum(precisions) / len(precisions) if precisions else 0.0

    return results


def run_holdout_evaluation(
    session: Any,
    synthetic_users: list[SyntheticUser],
    k: int = 10,
) -> dict[str, float]:
    """Compute Precision@k and Recall@k using held-out items as ground truth.

    Held-out items are in the `items` table with embeddings but are NOT in
    the user's user_items, so they appear as recommendation candidates.
    """
    all_precision: list[float] = []
    all_recall: list[float] = []
    group_recall: dict[str, list[float]] = {}

    for su in synthetic_users:
        if not su.holdout_item_ids:
            continue
        relevant = set(su.holdout_item_ids)
        retrieved = _ann_item_query(session, su.user_id, limit=k)
        p = precision_at_k(retrieved, relevant, k=k)
        r = recall_at_k(retrieved, relevant, k=k)
        all_precision.append(p)
        all_recall.append(r)
        group_recall.setdefault(su.group, []).append(r)

    n = len(all_precision)
    per_group = {g: sum(vals) / len(vals) for g, vals in group_recall.items() if vals}
    return {
        "precision_at_k": sum(all_precision) / n if n else 0.0,
        "recall_at_k": sum(all_recall) / n if n else 0.0,
        "k": k,
        "n_users": n,
        "recall_per_group": per_group,
    }


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
) -> dict[str, float]:
    """Compare average semantic vs heuristic scores across Group A pairs.

    Group A users have the most overlap so scores are most meaningful there.
    Popularity is built from the full synthetic cohort so that items shared by
    all 5 Group A users receive count=5 (lower rarity) rather than count=2
    (the degenerate per-pair value that makes the heuristic score constant).
    """
    group_a = [su for su in synthetic_users if su.group == "A"]

    # Precompute cohort-wide popularity once; pass to every pair
    cohort_popularity = _build_cohort_popularity(session, synthetic_users)

    semantic_scores: list[float] = []
    heuristic_scores: list[float] = []

    for i, ua in enumerate(group_a):
        for ub in group_a[i + 1 :]:
            semantic_scores.append(_semantic_score_for_pair(session, ua.user_id, ub.user_id))
            heuristic_scores.append(
                _heuristic_score_for_pair(
                    session, ua.user_id, ub.user_id, popularity=cohort_popularity
                )
            )

    def _avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "semantic_avg": _avg(semantic_scores),
        "heuristic_avg": _avg(heuristic_scores),
        "n_pairs": len(semantic_scores),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────────────


def print_report(
    matching: dict[str, float],
    holdout: dict[str, float],
    modes: dict[str, float],
    users_per_group: int,
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
        print(f"  Group {group} precision@5: {score:.2f}  ({label})")

    k = holdout["k"]
    print()
    print(f"Holdout recommendation quality (N={holdout['n_users']} users, k={k}):")
    print(f"  Precision@{k} (pooled): {holdout['precision_at_k']:.2f}")
    print(f"  Recall@{k}    (pooled): {holdout['recall_at_k']:.2f}")
    per_group: dict[str, float] = holdout.get("recall_per_group", {})
    if per_group:
        print(f"  Recall@{k} by group:")
        for g in ("A", "B", "C", "out"):
            if g in per_group:
                note = {
                    "A": "high overlap — sanity check",
                    "B": "medium overlap",
                    "C": "0% training overlap — structural upper bound",
                    "out": "cross-domain — sanity check",
                }.get(g, "")
                print(f"    Group {g}: {per_group[g]:.2f}  ({note})")

    sem = modes["semantic_avg"]
    heu = modes["heuristic_avg"]
    delta_pct = ((sem - heu) / heu * 100) if heu > 0 else float("inf")
    print()
    print("Matching mode comparison (Group A pairs):")
    print(f"  heuristic:  avg score {heu:.2f}  (rarity-weighted overlap, cohort-wide popularity)")
    if heu > 0:
        print(f"  semantic:   avg score {sem:.2f}  ({delta_pct:+.0f}% vs heuristic)")
    else:
        print(f"  semantic:   avg score {sem:.2f}")

    print()
    print("Evaluation caveats (self-critical assessment):")
    print("  - Synthetic cohort uses constant engagement_score=0.8 → log1p weighting")
    print("    is uniform; user vectors are unweighted item centroids. Real users with")
    print("    varied engagement will exercise the log1p dampening path.")
    print("  - Recall@k pooled across groups is not directly comparable: Group C and")
    print("    Out-group use items from a tight semantic cluster so recall is high by")
    print("    construction. Group A/B recall is the more informative signal.")
    print("  - Precision@5 for Out-group is trivially 1.0 (same EDM cluster). It")
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

            print("\nRunning matching evaluation (Precision@5)...")
            matching = run_matching_evaluation(session, synthetic_users)

            print("Running holdout evaluation (Precision@10, Recall@10)...")
            holdout = run_holdout_evaluation(session, synthetic_users, k=10)

            print("Running mode comparison...")
            modes = run_mode_comparison(session, synthetic_users)

            print_report(matching, holdout, modes, users_per_group)

        finally:
            if not args.no_cleanup:
                print("\nCleaning up synthetic data...")
                # Use a fresh session — the evaluation session may be in a broken
                # state if an exception occurred during the try block.
                with factory() as cleanup_session:
                    _cleanup_synthetic(cleanup_session, [su.user_id for su in synthetic_users])
                print("Done.")
            else:
                session.commit()
                print("\n--no-cleanup: synthetic rows retained.")


if __name__ == "__main__":
    main()
