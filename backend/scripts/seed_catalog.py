"""Seed a public item catalog so recommendations are meaningful from day one.

Inserts a curated set of well-known, taste-distinctive items (games, music
artists, films, albums, anime) into `items` with real embeddings computed via the
SAME `item_to_text` serializer used in production — so seeded items live in the
exact embedding space as real synced+enriched items.

Why: recommendations are drawn from the shared catalog. With only one real user
the catalog is just that user's own library, so there is nothing to recommend
(cold start). This seed gives every user a meaningful cross-domain pool.

Design:
- Items use realistic service names (steam/lastfm/letterboxd/rateyourmusic/anilist)
  so recommendation output looks native.
- external_id is `seed-<slug>` — namespaced so it never collides with real
  OAuth-synced items (numeric appids, mbids, etc.) and is trivially identifiable.
- Idempotent: re-running skips items already present.
- Reversible: `--wipe` deletes every seeded row (external_id LIKE 'seed-%').

Run:
    source .venv/bin/activate
    python scripts/seed_catalog.py            # insert (skips existing)
    python scripts/seed_catalog.py --wipe     # remove all seeded items
    python scripts/seed_catalog.py --dry-run  # show what would be inserted
"""

from __future__ import annotations

import argparse
import re
import uuid
from datetime import UTC, datetime
from typing import Any

# Service name per domain — chosen so recommendation output reads naturally.
SERVICE_BY_TYPE: dict[str, str] = {
    "game": "steam",
    "artist": "lastfm",
    "film": "letterboxd",
    "album": "rateyourmusic",
    "anime": "anilist",
}

# (name, genres-csv) for games / artists / anime
_GAMES: list[tuple[str, str]] = [
    ("Disco Elysium", "narrative RPG, philosophical, noir"),
    ("Outer Wilds", "exploration, mystery, space"),
    ("Hollow Knight", "metroidvania, action, atmospheric"),
    ("Hades", "roguelike, action, mythology"),
    ("The Witcher 3: Wild Hunt", "open world RPG, fantasy, narrative"),
    ("Elden Ring", "open world, soulslike, fantasy"),
    ("Dark Souls III", "soulslike, action RPG, dark fantasy"),
    ("Sekiro: Shadows Die Twice", "action, soulslike, samurai"),
    ("Bloodborne", "soulslike, gothic horror, action"),
    ("Stardew Valley", "farming, relaxing, indie"),
    ("Celeste", "platformer, precision, indie"),
    ("Subnautica", "survival, exploration, underwater"),
    ("Slay the Spire", "roguelike, deckbuilder, strategy"),
    ("Inscryption", "deckbuilder, horror, puzzle"),
    ("Return of the Obra Dinn", "puzzle, mystery, deduction"),
    ("Baldur's Gate 3", "narrative RPG, fantasy, turn-based"),
    ("Divinity: Original Sin 2", "RPG, fantasy, cooperative"),
    ("Planescape: Torment", "narrative RPG, philosophical, dark fantasy"),
    ("Pillars of Eternity", "narrative RPG, fantasy, introspective"),
    ("Fallout: New Vegas", "RPG, post-apocalyptic, open world"),
    ("Portal 2", "puzzle, first-person, comedy"),
    ("Half-Life: Alyx", "VR, first-person shooter, sci-fi"),
    ("Red Dead Redemption 2", "open world, western, narrative"),
    ("Hotline Miami", "top-down shooter, neon, brutal"),
    ("Katana ZERO", "action platformer, neo-noir, fast"),
    ("Dead Cells", "roguelike, metroidvania, action"),
    ("Hyper Light Drifter", "action, pixel art, atmospheric"),
    ("Tunic", "action adventure, puzzle, isometric"),
    ("Pentiment", "narrative, historical, artistic"),
    ("Citizen Sleeper", "narrative RPG, sci-fi, dice"),
    ("Night in the Woods", "narrative, indie, slice of life"),
    ("Kentucky Route Zero", "narrative, magical realism, surreal"),
    ("NieR: Automata", "action RPG, philosophical, sci-fi"),
    ("Persona 5 Royal", "JRPG, stylish, social sim"),
    ("Final Fantasy XIV", "MMORPG, fantasy, narrative"),
    ("Factorio", "automation, strategy, building"),
    ("RimWorld", "colony sim, emergent, sci-fi"),
    ("Terraria", "sandbox, adventure, crafting"),
    ("Vampire Survivors", "roguelike, bullet heaven, casual"),
    ("Cuphead", "run and gun, hand-drawn, hard"),
    ("Undertale", "RPG, indie, subversive"),
    ("Spiritfarer", "management, cozy, emotional"),
    ("Death Stranding", "open world, walking sim, sci-fi"),
    ("Control", "action adventure, supernatural, brutalist"),
    ("Disco Elysium: The Final Cut", "narrative RPG, philosophical, expanded"),
]

_ARTISTS: list[tuple[str, str]] = [
    ("Radiohead", "alternative rock, electronic, experimental"),
    ("Aphex Twin", "electronic, ambient, IDM"),
    ("Boards of Canada", "electronic, ambient, downtempo"),
    ("Burial", "electronic, dubstep, ambient"),
    ("Four Tet", "electronic, ambient, house"),
    ("Bonobo", "electronic, downtempo, jazz"),
    ("Floating Points", "electronic, jazz, ambient"),
    ("Jon Hopkins", "electronic, ambient, techno"),
    ("Nils Frahm", "neoclassical, ambient, piano"),
    ("Tame Impala", "psychedelic rock, electronic, pop"),
    ("King Gizzard and the Lizard Wizard", "psychedelic rock, garage, experimental"),
    ("Khruangbin", "funk, psychedelic, instrumental"),
    ("Men I Trust", "dream pop, indie, chill"),
    ("Mac DeMarco", "indie rock, slacker, jangle pop"),
    ("Frank Ocean", "r&b, art pop, soul"),
    ("Kendrick Lamar", "hip-hop, jazz rap, conscious"),
    ("MF DOOM", "hip-hop, abstract, underground"),
    ("Tyler, the Creator", "hip-hop, neo-soul, alternative"),
    ("FKA twigs", "art pop, electronic, r&b"),
    ("James Blake", "electronic, soul, downtempo"),
    ("Massive Attack", "trip-hop, electronic, ambient"),
    ("Portishead", "trip-hop, electronic, dark"),
    ("Godspeed You! Black Emperor", "post-rock, instrumental, drone"),
    ("Explosions in the Sky", "post-rock, instrumental, cinematic"),
    ("Sigur Rós", "post-rock, ambient, ethereal"),
    ("The National", "indie rock, melancholic, baritone"),
    ("Sufjan Stevens", "indie folk, chamber pop, intimate"),
    ("Bon Iver", "indie folk, electronic, falsetto"),
    ("Nick Cave and the Bad Seeds", "post-punk, gothic, literary"),
    ("Talk Talk", "art rock, post-rock, experimental"),
    ("Daft Punk", "electronic, french house, disco"),
    ("Justice", "electronic, french house, dance"),
    ("Caribou", "electronic, psychedelic, dance"),
    ("Bicep", "electronic, house, techno"),
    ("Flying Lotus", "electronic, jazz, hip-hop"),
    ("Thundercat", "funk, jazz fusion, r&b"),
    ("BadBadNotGood", "jazz, hip-hop, instrumental"),
    ("Mac Miller", "hip-hop, jazz rap, introspective"),
    ("Beach House", "dream pop, shoegaze, ethereal"),
    ("Slowdive", "shoegaze, dream pop, atmospheric"),
    ("My Bloody Valentine", "shoegaze, noise pop, dreamy"),
    ("Aesop Rock", "hip-hop, abstract, dense"),
    ("Charles Mingus", "jazz, hard bop, experimental"),
    ("Miles Davis", "jazz, modal, fusion"),
    ("Alice Coltrane", "spiritual jazz, harp, devotional"),
]

_ANIME: list[tuple[str, str]] = [
    ("Cowboy Bebop", "space western, action, jazz"),
    ("Neon Genesis Evangelion", "mecha, psychological, drama"),
    ("Mushishi", "supernatural, slice of life, atmospheric"),
    ("Monster", "thriller, psychological, drama"),
    ("Steins;Gate", "sci-fi, time travel, thriller"),
    ("Hunter x Hunter", "adventure, shonen, strategy"),
    ("Vinland Saga", "historical, action, drama"),
    ("Frieren: Beyond Journey's End", "fantasy, adventure, melancholic"),
    ("Made in Abyss", "adventure, dark fantasy, exploration"),
    ("Mob Psycho 100", "action, comedy, supernatural"),
    ("Ping Pong the Animation", "sports, drama, stylized"),
    ("Serial Experiments Lain", "psychological, cyberpunk, surreal"),
    ("Texhnolyze", "cyberpunk, dystopian, bleak"),
    ("Haibane Renmei", "drama, supernatural, contemplative"),
    ("Land of the Lustrous", "fantasy, action, existential"),
    ("A Silent Voice", "drama, romance, emotional"),
    ("Your Name", "romance, drama, supernatural"),
    ("Spirited Away", "fantasy, adventure, coming of age"),
    ("Princess Mononoke", "fantasy, epic, environmental"),
    ("Devilman Crybaby", "horror, supernatural, tragedy"),
]

# (name, year, genres) for films
_FILMS: list[tuple[str, int, str]] = [
    ("Blade Runner 2049", 2017, "sci-fi, neo-noir, drama"),
    ("Parasite", 2019, "thriller, drama, dark comedy"),
    ("Everything Everywhere All at Once", 2022, "sci-fi, comedy, drama"),
    ("Whiplash", 2014, "drama, music, intense"),
    ("In the Mood for Love", 2000, "romance, drama, arthouse"),
    ("There Will Be Blood", 2007, "drama, period, epic"),
    ("No Country for Old Men", 2007, "thriller, neo-western, crime"),
    ("The Grand Budapest Hotel", 2014, "comedy, drama, quirky"),
    ("Mad Max: Fury Road", 2015, "action, post-apocalyptic, kinetic"),
    ("Dune", 2021, "sci-fi, epic, adventure"),
    ("Arrival", 2016, "sci-fi, drama, cerebral"),
    ("Her", 2013, "sci-fi, romance, melancholic"),
    ("Drive", 2011, "neo-noir, crime, stylish"),
    ("The Lighthouse", 2019, "psychological, horror, arthouse"),
    ("Hereditary", 2018, "horror, drama, dread"),
    ("Portrait of a Lady on Fire", 2019, "romance, period, arthouse"),
    ("Past Lives", 2023, "romance, drama, quiet"),
    ("Spirited Away", 2001, "animation, fantasy, adventure"),
    ("Princess Mononoke", 1997, "animation, fantasy, epic"),
    ("Stalker", 1979, "sci-fi, philosophical, slow cinema"),
    ("2001: A Space Odyssey", 1968, "sci-fi, epic, cerebral"),
    ("Apocalypse Now", 1979, "war, drama, epic"),
    ("The Master", 2012, "drama, period, character study"),
    ("Synecdoche, New York", 2008, "drama, surreal, existential"),
    ("Eternal Sunshine of the Spotless Mind", 2004, "romance, sci-fi, melancholic"),
    ("Lost in Translation", 2003, "drama, romance, atmospheric"),
    ("Oldboy", 2003, "thriller, mystery, brutal"),
    ("Burning", 2018, "mystery, drama, slow burn"),
    ("Uncut Gems", 2019, "thriller, drama, anxiety"),
    ("The Social Network", 2010, "drama, biographical, sharp"),
    ("Interstellar", 2014, "sci-fi, drama, epic"),
    ("Memories of Murder", 2003, "crime, thriller, drama"),
    ("Aftersun", 2022, "drama, memory, intimate"),
    ("First Reformed", 2017, "drama, religious, austere"),
    ("Annihilation", 2018, "sci-fi, horror, surreal"),
]

# (name, artist, genres) for albums
_ALBUMS: list[tuple[str, str, str]] = [
    ("In Rainbows", "Radiohead", "alternative rock, electronic"),
    ("Kid A", "Radiohead", "experimental rock, electronic"),
    ("Discovery", "Daft Punk", "electronic, french house, disco"),
    ("To Pimp a Butterfly", "Kendrick Lamar", "hip-hop, jazz, funk"),
    ("Blonde", "Frank Ocean", "r&b, art pop, experimental"),
    ("Madvillainy", "Madvillain", "hip-hop, abstract, underground"),
    ("Untrue", "Burial", "electronic, dubstep, ambient"),
    ("Selected Ambient Works 85-92", "Aphex Twin", "electronic, ambient, techno"),
    ("Music Has the Right to Children", "Boards of Canada", "electronic, ambient"),
    ("Currents", "Tame Impala", "psychedelic pop, electronic"),
    ("Dummy", "Portishead", "trip-hop, electronic"),
    ("Mezzanine", "Massive Attack", "trip-hop, electronic, dark"),
    (
        "Lift Your Skinny Fists Like Antennas to Heaven",
        "Godspeed You! Black Emperor",
        "post-rock, instrumental",
    ),
    ("Spirit of Eden", "Talk Talk", "art rock, post-rock"),
    ("For Emma, Forever Ago", "Bon Iver", "indie folk, intimate"),
    ("Illinois", "Sufjan Stevens", "indie folk, chamber pop"),
    ("Black Messiah", "D'Angelo", "neo-soul, funk, r&b"),
    ("Cosmogramma", "Flying Lotus", "electronic, jazz, experimental"),
    ("Drukqs", "Aphex Twin", "electronic, IDM, breakcore"),
    ("Lonerism", "Tame Impala", "psychedelic rock, pop"),
    ("Yeezus", "Kanye West", "hip-hop, industrial, experimental"),
    ("good kid, m.A.A.d city", "Kendrick Lamar", "hip-hop, conscious"),
    ("Since I Left You", "The Avalanches", "plunderphonics, electronic"),
    ("The Money Store", "Death Grips", "experimental hip-hop, noise"),
    ("Lateralus", "Tool", "progressive metal, art rock"),
]


def _slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def build_seed_items() -> list[dict[str, Any]]:
    """Return plain dicts describing every seed item (no DB). Pure + testable."""
    out: list[dict[str, Any]] = []

    for name, genres in _GAMES:
        out.append(_item("game", name, {"genres": genres.split(", ")}))
    for name, genres in _ARTISTS:
        out.append(_item("artist", name, {"genres": genres.split(", ")}))
    for name, genres in _ANIME:
        out.append(_item("anime", name, {"genres": genres.split(", ")}))
    for name, year, genres in _FILMS:
        out.append(_item("film", name, {"release_year": year, "genres": genres.split(", ")}))
    for name, artist, genres in _ALBUMS:
        out.append(
            _item(
                "album",
                name,
                {"artist_normalized": artist, "genres": genres.split(", ")},
                slug_extra=artist,
            )
        )

    return out


def _item(item_type: str, name: str, meta: dict[str, Any], slug_extra: str = "") -> dict[str, Any]:
    base = f"{name}-{slug_extra}" if slug_extra else name
    return {
        "service": SERVICE_BY_TYPE[item_type],
        "item_type": item_type,
        "external_id": f"seed-{_slug(base)}",
        "name": name,
        "meta": meta,
    }


# ──────────────────────────────────────────────────────────────────────────────
# DB operations
# ──────────────────────────────────────────────────────────────────────────────


def _wipe(session: Any) -> int:
    from sqlalchemy import text

    result = session.execute(text("DELETE FROM items WHERE external_id LIKE 'seed-%'"))
    session.commit()
    return result.rowcount or 0


def _existing_external_ids(session: Any) -> set[str]:
    from sqlalchemy import select

    from syncup.db.models import Item

    rows = session.execute(select(Item.external_id).where(Item.external_id.like("seed-%"))).all()
    return {r.external_id for r in rows}


def seed(session: Any, *, dry_run: bool = False) -> tuple[int, int]:
    """Insert missing seed items with embeddings. Returns (inserted, skipped)."""
    from syncup.db.models import Item
    from syncup.embeddings.item_text import item_to_text
    from syncup.embeddings.semantic import embed_batch

    specs = build_seed_items()
    existing = _existing_external_ids(session)
    todo = [s for s in specs if s["external_id"] not in existing]
    skipped = len(specs) - len(todo)

    if not todo:
        return 0, skipped
    if dry_run:
        return len(todo), skipped

    # Build transient Item objects so item_to_text produces the exact production text.
    now = datetime.now(UTC)
    items = [
        Item(
            id=uuid.uuid4(),
            service=s["service"],
            item_type=s["item_type"],
            external_id=s["external_id"],
            name=s["name"],
            meta=s["meta"],
            created_at=now,
        )
        for s in todo
    ]
    texts = [item_to_text(it) for it in items]
    embeddings = embed_batch(texts)
    for it, emb in zip(items, embeddings, strict=True):
        it.embedding = emb
        it.embedding_computed_at = now
        session.add(it)
    session.commit()
    return len(items), skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the public item catalog")
    parser.add_argument("--wipe", action="store_true", help="Delete all seeded items and exit")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be inserted without writing"
    )
    args = parser.parse_args()

    from syncup.config import Settings
    from syncup.db.session import sessionmaker_for

    settings = Settings()
    factory = sessionmaker_for(settings.database_url)

    with factory() as session:
        if args.wipe:
            n = _wipe(session)
            print(f"Wiped {n} seeded catalog items (external_id LIKE 'seed-%').")
            return

        total = len(build_seed_items())
        print(f"Seeding catalog ({total} curated items across 5 domains)...")
        inserted, skipped = seed(session, dry_run=args.dry_run)
        if args.dry_run:
            print(f"[dry-run] would insert {inserted}, skip {skipped} already present.")
        else:
            print(f"Inserted {inserted} new items, skipped {skipped} already present.")
            print("Recommendations now have a real cross-domain pool to draw from.")


if __name__ == "__main__":
    main()
