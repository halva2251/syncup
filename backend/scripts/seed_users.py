"""Seed realistic matchable profiles so the /feed page is populated.

Creates demo users (is_matchable=True, onboarded=True) with distinct taste
profiles drawn from the seed catalog (scripts/seed_catalog.py). Each user gets a
ServiceConnection (sync_status="ok") and UserItem rows pointing at catalog
items, then a combined embedding is built so both the heuristic and semantic
match paths produce results.

Because the heuristic matcher keys on shared `Item.id` UUIDs (not names), and
seed-catalog items use `external_id LIKE 'seed-%'`, real synced items (Steam
appids, etc.) will NOT overlap with these. To guarantee a real user sees
matches, pass `--link-user <email>` to copy a taste profile onto an existing
account so it shares catalog item IDs with the seed users.

Prerequisite: run `python scripts/seed_catalog.py` first so the catalog items
exist with embeddings.

Design:
- Seed users are email-namespaced (`seed-*@syncup.demo`) and trivially wipeable.
- `--link-user` attaches a taste profile (subset of catalog items) to an EXISTING
  user by email, so that user shares Item.id overlap with the seed users. This
  is idempotent (skips UserItem rows that already exist).
- `--wipe` removes all seed users + their cascaded rows (user_items,
  user_embeddings, service_connections) and match_cache entries.

Run:
    source .venv/bin/activate
    python scripts/seed_catalog.py              # prerequisite: catalog items
    python scripts/seed_users.py                # create 5 demo profiles
    python scripts/seed_users.py --link-user me@example.com   # link a real user
    python scripts/seed_users.py --wipe         # remove all seed users
    python scripts/seed_users.py --dry-run      # preview without writing
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text

SEED_DOMAIN = "syncup.demo"

# ──────────────────────────────────────────────────────────────────────────────
# Profile definitions — each is a (email-local, display_name, bio, discord,
# taste_descriptor). Taste descriptors map to catalog item names (see below).
# ──────────────────────────────────────────────────────────────────────────────

_PROFILES: list[dict[str, Any]] = [
    {
        "email": "maya",
        "display_name": "Maya",
        "bio": (
            "Indie game dev. Lives for narrative RPGs, post-rock, and slow "
            "cinema. Will talk your ear off about Disco Elysium."
        ),
        "discord": "maya#0420",
        "languages": ["en"],
        "taste": "narrative",
    },
    {
        "email": "kenji",
        "display_name": "Kenji",
        "bio": (
            "Soulslike gremlin. Spends weekends in Lordran and listening to "
            "electronic ambient. Anime completionist."
        ),
        "discord": "kenji_v#7788",
        "languages": ["en", "ja"],
        "taste": "soulslike",
    },
    {
        "email": "lena",
        "display_name": "Lena",
        "bio": (
            "Music producer and film buff. Trip-hop forever. "
            "I rate every movie I watch."
        ),
        "discord": "lena.beats#2245",
        "languages": ["en", "de"],
        "taste": "electronic",
    },
    {
        "email": "arjun",
        "display_name": "Arjun",
        "bio": (
            "Hip-hop head and JRPG enjoyer. Currently replaying "
            "Persona 5 and spinning Madvillainy."
        ),
        "discord": "arjun#9912",
        "languages": ["en", "hi"],
        "taste": "hiphop",
    },
    {
        "email": "sofia",
        "display_name": "Sofia",
        "bio": (
            "Cozy games and shoegaze. Stardew Valley farm is my zen garden. "
            "Beach House on repeat."
        ),
        "discord": "sofia.dev#0044",
        "languages": ["en", "es"],
        "taste": "cozy",
    },
    {
        "email": "riley",
        "display_name": "Riley",
        "bio": (
            "Late-night Last.fm scrobbler. Juice WRLD, d4vd, and glaive are "
            "always in rotation. Send me your favourite sad banger."
        ),
        "discord": "riley.fm#0707",
        "languages": ["en"],
        "taste": "altpop",
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Taste profiles — curated subsets of the seed catalog item names.
# Each list is a set of catalog `name` values. Seed users within a cluster share
# items so they match each other AND the linked real user.
#
# There is deliberate cross-cluster overlap (e.g. Disco Elysium appears in
# multiple profiles) so every seed user matches at least 2-3 others.
# ──────────────────────────────────────────────────────────────────────────────

_TASTE_CLUSTERS: dict[str, list[str]] = {
    "narrative": [
        "Disco Elysium",
        "Outer Wilds",
        "Return of the Obra Dinn",
        "Night in the Woods",
        "Pentiment",
        "Kentucky Route Zero",
        "Godspeed You! Black Emperor",
        "The National",
        "Blade Runner 2049",
        "Stalker",
    ],
    "soulslike": [
        "Elden Ring",
        "Dark Souls III",
        "Bloodborne",
        "Sekiro: Shadows Die Twice",
        "Hollow Knight",
        "Hades",
        "NieR: Automata",
        "Neon Genesis Evangelion",
        "Aphex Twin",
    ],
    "electronic": [
        "Burial",
        "Boards of Canada",
        "Massive Attack",
        "Portishead",
        "Four Tet",
        "Jon Hopkins",
        "Untrue",
        "Mezzanine",
        "Drive",
        "Annihilation",
    ],
    "hiphop": [
        "Kendrick Lamar",
        "MF DOOM",
        "Tyler, the Creator",
        "Frank Ocean",
        "Mac Miller",
        "To Pimp a Butterfly",
        "Madvillainy",
        "Blonde",
        "Persona 5 Royal",
        "Cowboy Bebop",
    ],
    "cozy": [
        "Stardew Valley",
        "Spiritfarer",
        "Celeste",
        "Beach House",
        "Slowdive",
        "Men I Trust",
        "Spirited Away",
    ],
    "altpop": [
        "Juice WRLD",
        "d4vd",
        "glaive",
    ],
}

# Items every seed user shares with the real user (guarantees overlap).
# These are popular, broadly-appealing items likely in any real user's library.
_SHARED_CORE: list[str] = [
    "Disco Elysium",
    "Hades",
    "Hollow Knight",
    "Radiohead",
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _seed_email(local: str) -> str:
    return f"seed-{local}@{SEED_DOMAIN}"


def _load_catalog_items(session: Any) -> dict[str, uuid.UUID]:
    """Map catalog item name → Item.id for all seed-catalog items."""
    from syncup.db.models import Item

    rows = session.execute(
        select(Item.id, Item.name).where(Item.external_id.like("seed-%"))
    ).all()
    return {row.name: row.id for row in rows}


def _resolve_item_ids(
    name_map: dict[str, uuid.UUID], names: list[str]
) -> list[uuid.UUID]:
    """Resolve catalog names to IDs, silently dropping any that don't exist."""
    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for name in names:
        clean = name.strip()
        item_id = name_map.get(clean)
        if item_id and item_id not in seen:
            ids.append(item_id)
            seen.add(item_id)
    return ids


def _make_user(session: Any, profile: dict[str, Any]) -> Any:
    from syncup.db.models import User

    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=_seed_email(profile["email"]),
        display_name=profile["display_name"],
        password_hash="$argon2id$seed",  # noqa: S106 — unusable placeholder
        bio=profile["bio"],
        discord_handle=profile["discord"],
        languages=profile["languages"],
        is_matchable=True,
        onboarded=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.commit()
    return user


def _make_connection(session: Any, user_id: uuid.UUID, service: str) -> None:
    from syncup.db.models import ServiceConnection

    # Skip if a connection for this service already exists.
    existing = session.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user_id,
            ServiceConnection.service == service,
        )
    )
    if existing:
        return
    session.add(
        ServiceConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            service=service,
            external_user_id=f"seed-{user_id.hex[:8]}",
            sync_status="ok",
            last_synced_at=datetime.now(UTC),
        )
    )
    session.commit()


def _link_items(
    session: Any,
    user_id: uuid.UUID,
    item_ids: list[uuid.UUID],
) -> int:
    """Create UserItem rows for the given items. Returns count inserted."""
    from syncup.db.models import UserItem

    inserted = 0
    now = datetime.now(UTC)
    for item_id in item_ids:
        existing = session.scalar(
            select(UserItem).where(
                UserItem.user_id == user_id,
                UserItem.item_id == item_id,
            )
        )
        if existing:
            continue
        session.add(
            UserItem(
                id=uuid.uuid4(),
                user_id=user_id,
                item_id=item_id,
                engagement_score=0.8,
                raw_value=100.0,
                raw_type="consumption",
                fetched_at=now,
                excluded=False,
            )
        )
        inserted += 1
    session.commit()
    return inserted


def _build_embedding(session: Any, user_id: uuid.UUID) -> int | None:
    """Build a combined embedding so semantic matching works. Returns item count or None."""
    from syncup.api.routes.embeddings import build_user_embedding

    try:
        result = build_user_embedding(session, user_id)
        return result.item_count
    except Exception:
        # NO_EMBEDDINGS_AVAILABLE or model not loaded — heuristic still works.
        return None


# ──────────────────────────────────────────────────────────────────────────────
# DB operations
# ──────────────────────────────────────────────────────────────────────────────


def _wipe(session: Any) -> int:
    """Delete all seed users (cascades to user_items, embeddings, connections)."""
    from syncup.db.models import User

    seed_ids = [
        row.id
        for row in session.execute(
            select(User.id).where(User.email.like(f"seed-%@{SEED_DOMAIN}"))
        ).all()
    ]
    if not seed_ids:
        return 0

    # Clean match_cache for these users (not covered by FK CASCADE reliably).
    for uid in seed_ids:
        session.execute(
            text("DELETE FROM match_cache WHERE user_a_id = :uid OR user_b_id = :uid"),
            {"uid": uid},
        )
    # Deleting users cascades to user_items, user_embeddings, service_connections.
    session.execute(
        text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": seed_ids}
    )
    session.commit()
    return len(seed_ids)


def _existing_seed_emails(session: Any) -> set[str]:
    from syncup.db.models import User

    rows = session.execute(
        select(User.email).where(User.email.like(f"seed-%@{SEED_DOMAIN}"))
    ).all()
    return {r.email for r in rows}


def seed(session: Any, *, dry_run: bool = False) -> tuple[int, int]:
    """Create the seed profiles. Returns (created, skipped)."""
    name_map = _load_catalog_items(session)
    if not name_map:
        print("ERROR: No seed-catalog items found. Run `scripts/seed_catalog.py` first.")
        return 0, 0

    existing = _existing_seed_emails(session)
    todo = [p for p in _PROFILES if _seed_email(p["email"]) not in existing]
    skipped = len(_PROFILES) - len(todo)

    if not todo:
        return 0, skipped
    if dry_run:
        return len(todo), skipped

    created = 0
    for profile in todo:
        user = _make_user(session, profile)
        _make_connection(session, user.id, "steam")
        _make_connection(session, user.id, "spotify")
        _make_connection(session, user.id, "lastfm")

        item_names = _TASTE_CLUSTERS.get(profile["taste"], []) + _SHARED_CORE
        item_ids = _resolve_item_ids(name_map, item_names)
        count = _link_items(session, user.id, item_ids)

        emb_count = _build_embedding(session, user.id)
        emb_label = f", embedding: {emb_count} items" if emb_count else ", heuristic only"
        print(
            f"  Created {user.display_name} ({user.email}): "
            f"{count} items linked{emb_label}"
        )
        created += 1

    return created, skipped


def link_user(session: Any, email: str, *, dry_run: bool = False) -> bool:
    """Attach a broad taste profile to an existing user so they match seed users."""
    from syncup.db.models import User

    user = session.scalar(select(User).where(User.email == email))
    if not user:
        print(f"ERROR: No user found with email '{email}'.")
        return False

    name_map = _load_catalog_items(session)
    if not name_map:
        print("ERROR: No seed-catalog items found. Run `scripts/seed_catalog.py` first.")
        return False

    # Give the real user a generous taste spread so they overlap with every cluster.
    all_names: list[str] = list(_SHARED_CORE)
    for names in _TASTE_CLUSTERS.values():
        all_names.extend(names)
    item_ids = _resolve_item_ids(name_map, all_names)

    if dry_run:
        print(f"[dry-run] would link {len(item_ids)} catalog items to {email}")
        return True

    count = _link_items(session, user.id, item_ids)
    _build_embedding(session, user.id)
    if not user.is_matchable:
        user.is_matchable = True
        session.commit()

    print(f"Linked {count} catalog items to {email} (is_matchable=True).")
    print("Visit /feed and hit 'Refresh matches' to see your seed matches.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo matchable profiles")
    parser.add_argument("--wipe", action="store_true", help="Delete all seed users and exit")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be done without writing"
    )
    parser.add_argument(
        "--link-user",
        metavar="EMAIL",
        help="Link an existing user to catalog items so they match the seed profiles",
    )
    args = parser.parse_args()

    from syncup.config import Settings
    from syncup.db.session import sessionmaker_for

    settings = Settings()
    factory = sessionmaker_for(settings.database_url)

    with factory() as session:
        if args.wipe:
            n = _wipe(session)
            print(f"Wiped {n} seed users (@{SEED_DOMAIN}).")
            return

        if args.link_user:
            link_user(session, args.link_user, dry_run=args.dry_run)
            return

        print(f"Seeding {len(_PROFILES)} demo profiles...")
        created, skipped = seed(session, dry_run=args.dry_run)
        if args.dry_run:
            print(f"[dry-run] would create {created}, skip {skipped} already present.")
        else:
            print(f"Created {created} profiles, skipped {skipped} already present.")
            print()
            print("To make a real user see these matches, run:")
            print("  python scripts/seed_users.py --link-user <their-email>")


if __name__ == "__main__":
    main()
