"""Manual integration test for Block I: GET /api/me/recommendations.

Run: cd backend && source .venv/bin/activate && python scripts/manual_test_block_i.py
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text

from syncup.api.routes.embeddings import build_user_embedding
from syncup.db.models import Item, User, UserItem
from syncup.db.session import sessionmaker_for
from syncup.embeddings.semantic import embed_batch
from syncup.limiter import limiter as _rate_limiter


def _get_factory():
    from syncup.config import Settings

    settings = Settings()
    return sessionmaker_for(settings.database_url)


def _make_user(session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        display_name="BlockI Test",
        password_hash="$2b$12$fakehash",  # noqa: S106
        is_matchable=True,
        onboarded=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def _make_item(
    session,
    service: str,
    name: str,
    item_type: str = "game",
    genres: list[str] | None = None,
) -> Item:
    item = Item(
        id=uuid.uuid4(),
        service=service,
        item_type=item_type,
        external_id=str(uuid.uuid4())[:8],
        name=name,
        metadata={"genres": genres or []},
        created_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    return item


def _make_user_item(session, user_id, item_id, score=0.8) -> None:
    ui = UserItem(
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        engagement_score=score,
        raw_value=100.0,
        raw_type="consumption",
        fetched_at=datetime.now(UTC),
        excluded=False,
    )
    session.add(ui)
    session.commit()


def _cleanup(session, emails: list[str]) -> None:
    for email in emails:
        user = session.scalar(select(User).where(User.email == email))
        if not user:
            continue
        session.execute(text("DELETE FROM user_embeddings WHERE user_id = :uid"), {"uid": user.id})
        session.execute(text("DELETE FROM user_items WHERE user_id = :uid"), {"uid": user.id})
        session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user.id})
        session.commit()
    session.execute(text("DELETE FROM items WHERE service LIKE 'block_i_test%'"))
    session.commit()


def test_happy_path_recommendations() -> None:
    print("\n=== Test 1: Happy path — returns items not in user's library ===")
    factory = _get_factory()
    emails = ["blocki-alice@example.com"]

    with factory() as session:
        _cleanup(session, emails)

        user = _make_user(session, emails[0])

        # Items Alice owns
        owned = [
            _make_item(session, "block_i_test", "Disco Elysium", "game", ["RPG", "narrative"]),
            _make_item(session, "block_i_test", "Outer Wilds", "game", ["exploration"]),
        ]
        # Items Alice does NOT own — should appear in recommendations
        catalog = [
            _make_item(session, "block_i_test", "Planescape Torment", "game", ["RPG", "narrative"]),
            _make_item(session, "block_i_test", "Return of the Obra Dinn", "game", ["mystery"]),
            _make_item(session, "block_i_test", "Nick Cave", "lastfm", ["post-punk"]),
        ]

        all_items = owned + catalog
        texts = []
        for item in all_items:
            genres = ", ".join(item.meta.get("genres", []))
            texts.append(f"{item.name} — {item.item_type}" + (f", {genres}" if genres else ""))

        embeddings = embed_batch(texts)
        for item, emb in zip(all_items, embeddings, strict=True):
            item.embedding = emb
            item.embedding_computed_at = datetime.now(UTC)
        session.commit()

        for item in owned:
            _make_user_item(session, user.id, item.id, score=0.9)

        print(f"  User: {user.id}")
        print(f"  Owned: {[i.name for i in owned]}")
        print(f"  Catalog (unowned): {[i.name for i in catalog]}")

    # Build combined embedding
    with factory() as session:
        result = build_user_embedding(session, user.id)
        print(f"  Built embedding: {result.item_count} items")

    # Call the recommendations route directly (bypass HTTP)
    from syncup.api.routes.recommendations import get_recommendations

    class FakeUser:
        id = user.id

    _rate_limiter.enabled = False
    with factory() as session:
        from unittest.mock import MagicMock

        request = MagicMock()
        result = get_recommendations(
            request=request,
            db=session,
            user=FakeUser(),  # type: ignore[arg-type]
            item_type=None,
            limit=10,
        )
    _rate_limiter.enabled = True

    # Check by (service, name) — other test services can have items with the same
    # name (e.g. block_h_test/Disco Elysium). The NOT EXISTS only excludes the
    # specific items Alice owns, which are all from block_i_test.
    owned_service_names = {(i.service, i.name) for i in owned}

    print(f"  Recommendations: {[(r.service, r.item_name) for r in result.items]}")
    for rec in result.items:
        assert (rec.service, rec.item_name) not in owned_service_names, (
            f"Owned item ({rec.service}, {rec.item_name}) appeared in recs"
        )
        assert 0.0 < rec.similarity_score <= 1.0, f"Score out of range: {rec.similarity_score}"
    assert len(result.items) > 0, "Should return at least one recommendation"

    print(f"  ✓ {len(result.items)} recommendations, none are Alice's owned items")
    print("  PASSED")


def test_item_type_filter() -> None:
    print("\n=== Test 2: item_type filter returns only requested type ===")
    factory = _get_factory()
    emails = ["blocki-bob@example.com"]

    with factory() as session:
        _cleanup(session, emails)
        user = _make_user(session, emails[0])

        owned = [_make_item(session, "block_i_test", "Hades", "game", ["roguelike"])]
        catalog = [
            _make_item(session, "block_i_test", "Dead Cells", "game", ["roguelike"]),
            _make_item(session, "block_i_test", "Portishead", "lastfm", ["trip-hop"]),
        ]

        all_items = owned + catalog
        texts = [f"{i.name} — {i.item_type}" for i in all_items]
        embeddings = embed_batch(texts)
        for item, emb in zip(all_items, embeddings, strict=True):
            item.embedding = emb
            item.embedding_computed_at = datetime.now(UTC)
        session.commit()

        _make_user_item(session, user.id, owned[0].id, score=0.9)

    with factory() as session:
        build_user_embedding(session, user.id)

    from unittest.mock import MagicMock

    from syncup.api.routes.recommendations import ItemTypeFilter, get_recommendations

    class FakeUser:
        id = user.id

    _rate_limiter.enabled = False
    with factory() as session:
        result = get_recommendations(
            request=MagicMock(),
            db=session,
            user=FakeUser(),  # type: ignore[arg-type]
            item_type=ItemTypeFilter.game,
            limit=10,
        )
    _rate_limiter.enabled = True

    print(f"  Game-only recommendations: {[r.item_name for r in result.items]}")
    assert all(r.item_type == "game" for r in result.items), "All results must be games"
    print(f"  ✓ All {len(result.items)} results are item_type='game'")
    print("  PASSED")


def test_no_embedding_returns_422() -> None:
    print("\n=== Test 3: 422 when no combined embedding ===")
    factory = _get_factory()
    emails = ["blocki-charlie@example.com"]

    with factory() as session:
        _cleanup(session, emails)
        user = _make_user(session, emails[0])

    from unittest.mock import MagicMock

    from syncup.api.routes.recommendations import get_recommendations
    from syncup.exceptions import SyncUpError

    class FakeUser:
        id = user.id

    _rate_limiter.enabled = False
    with factory() as session:
        try:
            get_recommendations(
                request=MagicMock(),
                db=session,
                user=FakeUser(),  # type: ignore[arg-type]
                item_type=None,
                limit=10,
            )
            raise AssertionError("Should have raised SyncUpError")
        except SyncUpError as exc:
            assert exc.status_code == 422, f"Expected 422, got {exc.status_code}"
            assert exc.code == "NO_EMBEDDING_AVAILABLE"
            print(f"  ✓ Raised SyncUpError(code={exc.code}, status={exc.status_code})")
    _rate_limiter.enabled = True

    # Cleanup
    with factory() as session:
        _cleanup(session, emails)

    print("  PASSED")


def test_oversample_delivers_full_limit() -> None:
    print("\n=== Test 4: Oversample — returns up to limit even with some low-score items ===")
    factory = _get_factory()
    emails = ["blocki-diana@example.com"]

    with factory() as session:
        _cleanup(session, emails)
        user = _make_user(session, emails[0])

        anchor = _make_item(session, "block_i_test", "Anchor Game", "game", ["RPG"])
        # 15 catalog items in same genre — high cosine similarity expected
        catalog = [
            _make_item(session, "block_i_test", f"RPG Game {i}", "game", ["RPG"]) for i in range(15)
        ]

        all_items = [anchor] + catalog
        texts = [f"{i.name} — game, RPG" for i in all_items]
        embeddings = embed_batch(texts)
        for item, emb in zip(all_items, embeddings, strict=True):
            item.embedding = emb
            item.embedding_computed_at = datetime.now(UTC)
        session.commit()

        _make_user_item(session, user.id, anchor.id, score=0.9)

    with factory() as session:
        build_user_embedding(session, user.id)

    from unittest.mock import MagicMock

    from syncup.api.routes.recommendations import get_recommendations

    class FakeUser:
        id = user.id

    _rate_limiter.enabled = False
    with factory() as session:
        result = get_recommendations(
            request=MagicMock(),
            db=session,
            user=FakeUser(),  # type: ignore[arg-type]
            item_type=None,
            limit=10,
        )
    _rate_limiter.enabled = True

    print(f"  Requested limit=10, got {len(result.items)} recommendations")
    # All catalog items are RPG — should saturate limit=10 from 15 candidates
    assert len(result.items) == 10, f"Expected 10 items (limited), got {len(result.items)}"
    print("  ✓ Oversample delivered full limit=10")

    # Cleanup
    with factory() as session:
        _cleanup(session, emails)
        session.execute(text("DELETE FROM items WHERE service LIKE 'block_i_test%'"))
        session.commit()

    print("  PASSED")


if __name__ == "__main__":
    test_happy_path_recommendations()
    test_item_type_filter()
    test_no_embedding_returns_422()
    test_oversample_delivers_full_limit()
    print("\n=== ALL BLOCK I MANUAL TESTS PASSED ===")
