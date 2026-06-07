"""Autonomous QA sweep against the LIVE running server + DB.

Seeds a realistic catalog, creates a throwaway QA user, drives the real HTTP API
end-to-end, and asserts invariants across endpoints — with emphasis on the
recommendations dedup / owned-by-title fix. Cleans up all its own data.

Prereqs: server running on $BASE (default http://localhost:8000) and DB up.
Run:  source .venv/bin/activate && python scripts/qa_sweep.py
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

BASE = os.environ.get("BASE", "http://localhost:8000")
QA_SERVICE = "qa_seed"

findings: list[tuple[str, str]] = []


def check(cond: bool, level: str, msg: str) -> None:
    status = "PASS" if cond else level
    findings.append((status, msg))
    print(f"  [{status}] {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# Catalog seeding (direct DB) — items the QA user will be recommended
# ──────────────────────────────────────────────────────────────────────────────

# (name, item_type, genres) — a broad cross-domain catalog
_CATALOG: list[tuple[str, str, str]] = [
    ("Outer Wilds", "game", "exploration, mystery, space"),
    ("Hollow Knight", "game", "metroidvania, action, atmospheric"),
    ("Stardew Valley", "game", "farming, relaxing, indie"),
    ("Hades", "game", "roguelike, action, mythology"),
    ("Subnautica", "game", "survival, exploration, underwater"),
    ("Slay the Spire", "game", "roguelike, deckbuilder, strategy"),
    ("Inscryption", "game", "deckbuilder, horror, puzzle"),
    ("Return of the Obra Dinn", "game", "puzzle, mystery, deduction"),
    ("Tame Impala", "artist", "psychedelic rock, electronic, pop"),
    ("Bonobo", "artist", "electronic, downtempo, jazz"),
    ("Khruangbin", "artist", "funk, psychedelic, instrumental"),
    ("Floating Points", "artist", "electronic, jazz, ambient"),
    ("Radiohead", "artist", "alternative rock, electronic, experimental"),
    ("Aphex Twin", "artist", "electronic, ambient, IDM"),
    ("King Gizzard and the Lizard Wizard", "artist", "psychedelic rock, garage"),
    ("Men I Trust", "artist", "dream pop, indie, chill"),
    ("Everything Everywhere All at Once", "film", "sci-fi, comedy, drama"),
    ("Parasite", "film", "thriller, drama, dark comedy"),
    ("Blade Runner 2049", "film", "sci-fi, neo-noir, drama"),
    ("The Grand Budapest Hotel", "film", "comedy, drama, quirky"),
    ("Whiplash", "film", "drama, music, intense"),
    ("Spirited Away", "film", "animation, fantasy, adventure"),
    ("In the Mood for Love", "film", "romance, drama, arthouse"),
    ("Dune", "film", "sci-fi, epic, adventure"),
    ("In Rainbows", "album", "alternative rock, electronic"),
    ("Discovery", "album", "electronic, french house, disco"),
    ("To Pimp a Butterfly", "album", "hip-hop, jazz, funk"),
    ("Blonde", "album", "r&b, art pop, experimental"),
    ("Frank Ocean", "artist", "r&b, art pop, soul"),
    ("Mac DeMarco", "artist", "indie rock, slacker, jangle pop"),
    ("Disco Elysium", "game", "narrative RPG, philosophical, noir"),  # dup-with-owned probe
    ("Celeste", "game", "platformer, precision, indie"),
]

# Items the QA user will OWN (used to build their taste vector). Mix of domains.
_OWNED: list[tuple[str, str, str]] = [
    ("Disco Elysium", "game", "narrative RPG, philosophical, noir"),
    ("Planescape Torment", "game", "narrative RPG, philosophical"),
    ("Pyre", "game", "narrative RPG, indie, sports"),
    ("Nils Frahm", "artist", "neoclassical, ambient, piano"),
    ("Jon Hopkins", "artist", "electronic, ambient, techno"),
    ("Bibio", "artist", "electronic, folktronica, ambient"),
]


def _make_item_text(name: str, item_type: str, genres: str) -> str:
    return f"{name} — {item_type}, {genres}"


def seed_catalog(session: Any) -> uuid.UUID:
    """Insert the catalog + owned items with real embeddings. Returns nothing useful
    here; the QA user is created via the API. Owned items are linked after we know
    the QA user id (see assign_owned)."""
    from syncup.db.models import Item
    from syncup.embeddings.semantic import embed_batch

    texts = [_make_item_text(*row) for row in _CATALOG]
    embs = embed_batch(texts)
    now = datetime.now(UTC)
    for (name, item_type, genres), emb in zip(_CATALOG, embs, strict=True):
        session.add(
            Item(
                id=uuid.uuid4(),
                service=QA_SERVICE,
                item_type=item_type,
                external_id=str(uuid.uuid4())[:12],
                name=name,
                meta={"genres": genres.split(", ")},
                embedding=emb,
                embedding_computed_at=now,
                created_at=now,
            )
        )
    session.commit()
    return uuid.uuid4()


def assign_owned(session: Any, user_id: uuid.UUID) -> None:
    """Insert OWNED items (distinct service so they don't collide with catalog) and
    link them to the QA user via user_items, so build_user_embedding has data."""
    from syncup.db.models import Item, UserItem
    from syncup.embeddings.semantic import embed_batch

    texts = [_make_item_text(*row) for row in _OWNED]
    embs = embed_batch(texts)
    now = datetime.now(UTC)
    for (name, item_type, genres), emb in zip(_OWNED, embs, strict=True):
        item = Item(
            id=uuid.uuid4(),
            service=QA_SERVICE + "_owned",
            item_type=item_type,
            external_id=str(uuid.uuid4())[:12],
            name=name,
            meta={"genres": genres.split(", ")},
            embedding=emb,
            embedding_computed_at=now,
            created_at=now,
        )
        session.add(item)
        session.flush()
        session.add(
            UserItem(
                id=uuid.uuid4(),
                user_id=user_id,
                item_id=item.id,
                engagement_score=0.6 + 0.05 * len(name) % 4 / 10,
                raw_value=100.0,
                raw_type="consumption",
                fetched_at=now,
                excluded=False,
            )
        )
    session.commit()


def cleanup(session: Any, user_id: uuid.UUID | None) -> None:
    from sqlalchemy import text

    if user_id is not None:
        session.execute(
            text("DELETE FROM match_cache WHERE user_a_id = :u OR user_b_id = :u"),
            {"u": str(user_id)},
        )
        session.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
    session.execute(
        text("DELETE FROM items WHERE service IN (:s1, :s2)"),
        {"s1": QA_SERVICE, "s2": QA_SERVICE + "_owned"},
    )
    session.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Main sweep
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    from syncup.config import Settings
    from syncup.db.session import sessionmaker_for

    settings = Settings()
    factory = sessionmaker_for(settings.database_url)

    email = f"qa-{uuid.uuid4().hex[:8]}@gmail.com"
    pw = "qaqaqaqa12"
    user_id: uuid.UUID | None = None
    client = httpx.Client(base_url=BASE, timeout=30.0)

    try:
        print(f"\nQA sweep against {BASE} (user {email})\n" + "=" * 60)

        # --- Auth ---
        r = client.post(
            "/api/auth/signup",
            json={"email": email, "password": pw, "display_name": "QA Bot"},
        )
        check(r.status_code == 201, "FAIL", f"signup → {r.status_code} (expect 201)")
        user_id = uuid.UUID(r.json()["user"]["id"])
        # The session cookie is set Secure when the server is not in DEBUG, which
        # httpx will not resend over plain http. Send it explicitly so the sweep
        # works regardless of the server's debug flag.
        token = client.cookies.get("syncup_session")
        check(token is not None, "FAIL", "signup set a session cookie")
        client.headers["Cookie"] = f"syncup_session={token}"
        check(client.get("/api/me").status_code == 200, "FAIL", "authenticated GET /api/me → 200")

        # --- Guards before data ---
        r = client.post("/api/embeddings/build")
        check(r.status_code == 422, "FAIL", f"build w/o data → {r.status_code} (expect 422)")
        r = client.get("/api/me/recommendations")
        check(r.status_code == 422, "FAIL", f"recs w/o embedding → {r.status_code} (expect 422)")

        # --- Seed ---
        print("\nSeeding catalog + owned items (real embeddings)...")
        with factory() as s:
            seed_catalog(s)
            assign_owned(s, user_id)

        # --- Build embedding ---
        r = client.post("/api/embeddings/build")
        check(r.status_code == 200, "FAIL", f"build with data → {r.status_code} (expect 200)")
        check(
            r.json().get("item_count", 0) == len(_OWNED),
            "WARN",
            f"item_count={r.json().get('item_count')} (expect {len(_OWNED)})",
        )

        # --- Recommendations battery ---
        print("\nRecommendations:")
        r = client.get("/api/me/recommendations?limit=20")
        recs = r.json()["items"]
        check(r.status_code == 200, "FAIL", f"recs → {r.status_code}")
        check(
            len(recs) > 5,
            "WARN",
            f"got {len(recs)} recs from a {len(_CATALOG)}-item catalog (expect >5)",
        )

        names = [(x["item_name"].lower(), x["item_type"]) for x in recs]
        check(
            len(names) == len(set(names)),
            "FAIL",
            f"no duplicate (title,type) in recs (got {len(names)}, unique {len(set(names))})",
        )

        owned_titles = {(n.lower(), t) for n, t, _ in _OWNED}
        leaked = [n for n in names if n in owned_titles]
        check(not leaked, "FAIL", f"no owned title recommended (leaked: {leaked})")

        # Disco Elysium is owned AND in the catalog under qa_seed → must NOT appear
        disco = [x for x in recs if x["item_name"] == "Disco Elysium"]
        check(not disco, "FAIL", "owned 'Disco Elysium' not recommended from another service")

        scores = [x["similarity_score"] for x in recs]
        check(all(0.0 < s <= 1.0 for s in scores), "FAIL", "all scores in (0, 1]")
        check(scores == sorted(scores, reverse=True), "FAIL", "scores are descending")

        # item_type filter
        r = client.get("/api/me/recommendations?item_type=film&limit=10")
        films = r.json()["items"]
        check(
            all(x["item_type"] == "film" for x in films),
            "FAIL",
            f"item_type=film returns only films ({[x['item_type'] for x in films]})",
        )
        check(len(films) > 0, "WARN", f"film filter returned {len(films)} items")

        # limit respected
        r = client.get("/api/me/recommendations?limit=3")
        check(len(r.json()["items"]) <= 3, "FAIL", "limit=3 respected")

        # invalid limit rejected
        r = client.get("/api/me/recommendations?limit=999")
        check(r.status_code == 422, "FAIL", f"limit=999 → {r.status_code} (expect 422)")

        # --- Cross-domain sanity: a games+music user should get film recs too ---
        r = client.get("/api/me/recommendations?item_type=film&limit=5")
        check(
            r.status_code == 200 and len(r.json()["items"]) > 0,
            "WARN",
            "cross-domain: film recs surface for a games/music user",
        )

        # --- Dimensions / taste / matches smoke ---
        print("\nOther endpoints:")
        r = client.get("/api/me/taste")
        check(r.status_code == 200, "FAIL", f"GET /api/me/taste → {r.status_code}")
        r = client.patch("/api/me/dimensions", json={"weights": {QA_SERVICE + "_owned": 1.0}})
        check(r.status_code in (200, 204), "WARN", f"PATCH dimensions → {r.status_code}")
        r = client.patch("/api/me", json={"is_matchable": True})
        check(r.status_code == 200, "FAIL", f"PATCH /api/me matchable → {r.status_code}")
        r = client.get("/api/matches")
        check(r.status_code == 200, "FAIL", f"GET /api/matches → {r.status_code}")

    finally:
        client.close()
        print("\nCleaning up QA data...")
        with factory() as s:
            cleanup(s, user_id)
        print("Done.")

    # --- Summary ---
    print("\n" + "=" * 60)
    fails = [m for lvl, m in findings if lvl == "FAIL"]
    warns = [m for lvl, m in findings if lvl == "WARN"]
    passes = [m for lvl, m in findings if lvl == "PASS"]
    print(f"QA SWEEP: {len(passes)} passed, {len(warns)} warnings, {len(fails)} failures")
    if fails:
        print("\nFAILURES:")
        for m in fails:
            print(f"  - {m}")
    if warns:
        print("\nWARNINGS:")
        for m in warns:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
