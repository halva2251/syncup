"""Integrity checks for the match-profile seed data."""

from __future__ import annotations

from scripts.seed_catalog import build_seed_items
from scripts.seed_users import _PROFILES, _SHARED_CORE, _TASTE_CLUSTERS


def test_seed_profiles_have_unique_identity_and_taste_clusters() -> None:
    assert len(_PROFILES) == 6
    assert len({profile["email"] for profile in _PROFILES}) == len(_PROFILES)
    assert all(profile["taste"] in _TASTE_CLUSTERS for profile in _PROFILES)


def test_profile_tastes_resolve_to_seed_catalog_items() -> None:
    catalog_names = {item["name"] for item in build_seed_items()}

    for profile in _PROFILES:
        names = _TASTE_CLUSTERS[profile["taste"]] + _SHARED_CORE
        missing = set(names) - catalog_names
        assert not missing, f"{profile['display_name']} has missing catalog items: {missing}"


def test_riley_has_requested_lastfm_artists() -> None:
    riley = next(profile for profile in _PROFILES if profile["email"] == "riley")
    assert _TASTE_CLUSTERS[riley["taste"]] == ["Juice WRLD", "d4vd", "glaive"]
