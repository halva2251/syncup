"""Tests for the catalog seeder's pure helpers + dataset integrity."""

from __future__ import annotations

from scripts.seed_catalog import SERVICE_BY_TYPE, _slug, build_seed_items
from syncup.embeddings.item_text import item_to_text


def test_slug_basic() -> None:
    assert _slug("Disco Elysium") == "disco-elysium"
    assert _slug("King Gizzard and the Lizard Wizard!") == "king-gizzard-and-the-lizard-wizard"
    assert _slug("2001: A Space Odyssey") == "2001-a-space-odyssey"


def test_dataset_is_nonempty_and_sizeable() -> None:
    items = build_seed_items()
    assert len(items) >= 150  # "a few hundred" cross-domain pool


def test_external_ids_unique_per_service() -> None:
    items = build_seed_items()
    keys = [(i["service"], i["item_type"], i["external_id"]) for i in items]
    assert len(keys) == len(set(keys)), "duplicate (service,item_type,external_id) in seed data"


def test_all_external_ids_namespaced() -> None:
    """Every seed id must be 'seed-…' so it can't collide with real synced items."""
    assert all(i["external_id"].startswith("seed-") for i in build_seed_items())


def test_every_domain_present() -> None:
    types = {i["item_type"] for i in build_seed_items()}
    assert types == set(SERVICE_BY_TYPE.keys())


def test_item_to_text_nonempty_for_every_seed_item() -> None:
    """The seeder embeds item_to_text(item); it must produce non-degenerate text."""
    from types import SimpleNamespace

    for spec in build_seed_items():
        stub = SimpleNamespace(name=spec["name"], item_type=spec["item_type"], meta=spec["meta"])
        text = item_to_text(stub)
        assert text and text.strip(), f"empty text for {spec['name']}"
        assert spec["name"] in text


def test_albums_have_artist_in_text() -> None:
    """Album text format is '{name} by {artist} — album, music'."""
    from types import SimpleNamespace

    albums = [s for s in build_seed_items() if s["item_type"] == "album"]
    assert albums
    for spec in albums:
        stub = SimpleNamespace(name=spec["name"], item_type=spec["item_type"], meta=spec["meta"])
        assert " by " in item_to_text(stub)
