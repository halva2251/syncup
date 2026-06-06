"""Manual integration test for Block F: auto-embed + vibe synthesis.

Run: cd backend && source .venv/bin/activate && python scripts/manual_test_block_f.py
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import patch

from sqlalchemy import select, text

from syncup.api.routes.sync import _do_sync_generic, _embed_new_items
from syncup.db.models import Item, ServiceConnection, User, UserItem
from syncup.db.session import sessionmaker_for
from syncup.embeddings.vibe_synthesizer import synthesize_vibe


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_factory():
    from syncup.config import Settings

    settings = Settings()
    return sessionmaker_for(settings.database_url)


def _make_user(session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        display_name="Test User",
        password_hash="$2b$12$fakehash",  # noqa: S106
        is_matchable=True,
        onboarded=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def _make_connection(session, user_id: uuid.UUID, service: str) -> ServiceConnection:
    conn = ServiceConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        service=service,
        external_user_id="test-id",
        sync_status="ok",
        last_synced_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    session.add(conn)
    session.commit()
    return conn


def _make_item(session, service: str, name: str, item_type: str = "game") -> Item:
    item = Item(
        id=uuid.uuid4(),
        service=service,
        item_type=item_type,
        external_id=str(uuid.uuid4())[:8],
        name=name,
        metadata={"genres": ["RPG"]},
        created_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    return item


def _make_user_item(
    session,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    engagement_score: float = 0.8,
    excluded: bool = False,
) -> None:
    ui = UserItem(
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        engagement_score=engagement_score,
        raw_value=100.0,
        raw_type="consumption",
        fetched_at=datetime.now(UTC),
        excluded=excluded,
    )
    session.add(ui)
    session.commit()


# ---------------------------------------------------------------------------
# Mock LLM server (OpenAI-compatible tool-use response)
# ---------------------------------------------------------------------------


class MockLLMHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def do_POST(self):
        import json

        content_len = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_len)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": json.dumps(
                                        {
                                            "vibe_summary": "Loves melancholic RPGs and narrative depth.",
                                            "archetype": "The Story Seeker",
                                            "key_themes": ["melancholy", "agency", "worldbuilding"],
                                        }
                                    )
                                }
                            }
                        ]
                    }
                }
            ]
        }
        self.wfile.write(json.dumps(resp).encode())


def _start_mock_llm(port: int = 18080):
    server = HTTPServer(("127.0.0.1", port), MockLLMHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_auto_embed() -> None:
    print("\n=== Test 1: _embed_new_items (auto-embed post-sync) ===")
    factory = _get_factory()
    with factory() as session:
        # Clean up old test data
        email = "test-autombed@example.com"
        existing = session.scalar(select(User).where(User.email == email))
        if existing:
            session.execute(text("DELETE FROM user_items WHERE user_id = :uid"), {"uid": existing.id})
            session.execute(text("DELETE FROM items WHERE service = 'manual_test'"))
            session.execute(text("DELETE FROM service_connections WHERE user_id = :uid"), {"uid": existing.id})
            session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": existing.id})
            session.commit()

        user = _make_user(session, email)
        conn = _make_connection(session, user.id, "manual_test")

        # Create 3 items without embeddings
        items = [
            _make_item(session, "manual_test", "Disco Elysium", "game"),
            _make_item(session, "manual_test", "Hades", "game"),
            _make_item(session, "manual_test", "Outer Wilds", "game"),
        ]
        for item in items:
            _make_user_item(session, user.id, item.id, engagement_score=0.9)

        # Verify embeddings are NULL
        for item in items:
            session.refresh(item)
            assert item.embedding is None, f"Item {item.name} should start with no embedding"

        print(f"  Created user {user.id} with {len(items)} unembedded items")

    # Call _embed_new_items in a fresh session
    with factory() as session:
        _embed_new_items(session, user.id, "manual_test")

    # Verify embeddings were populated
    with factory() as session:
        for item in items:
            item_db = session.get(Item, item.id)
            assert item_db is not None
            assert item_db.embedding is not None, f"Item {item.name} should now have embedding"
            assert len(item_db.embedding) == 384, f"Embedding should be 384-dim, got {len(item_db.embedding)}"
            assert item_db.embedding_computed_at is not None
            print(f"  ✓ {item.name}: embedding dim={len(item_db.embedding)}, computed_at={item_db.embedding_computed_at}")

    print("  PASSED")


def test_vibe_synthesis() -> None:
    print("\n=== Test 2: synthesize_vibe with mock LLM ===")
    server = _start_mock_llm(18080)
    try:
        factory = _get_factory()
        with factory() as session:
            email = "test-vibe@example.com"
            existing = session.scalar(select(User).where(User.email == email))
            if existing:
                session.execute(text("DELETE FROM user_items WHERE user_id = :uid"), {"uid": existing.id})
                session.execute(text("DELETE FROM items WHERE service = 'vibe_test'"))
                session.execute(text("DELETE FROM service_connections WHERE user_id = :uid"), {"uid": existing.id})
                session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": existing.id})
                session.commit()

            user = _make_user(session, email)
            items = [
                _make_item(session, "vibe_test", "Disco Elysium", "game"),
                _make_item(session, "vibe_test", "Hades", "game"),
                _make_item(session, "vibe_test", "Godspeed You! Black Emperor", "artist"),
            ]
            for item in items:
                _make_user_item(session, user.id, item.id, engagement_score=0.95)

            print(f"  Created user {user.id} with {len(items)} items")

        result = synthesize_vibe(
            factory,
            user.id,
            llm_api_key="fake-key",
            llm_base_url="http://127.0.0.1:18080",
            llm_model="mock-model",
        )

        assert result is not None, "synthesize_vibe should return a result"
        print(f"  vibe_summary: {result.vibe_summary}")
        print(f"  archetype: {result.archetype}")
        print(f"  key_themes: {result.key_themes}")

        # Verify DB was updated
        with factory() as session:
            user_db = session.get(User, user.id)
            assert user_db is not None
            assert user_db.vibe_summary == result.vibe_summary
            assert user_db.archetype == result.archetype
            assert user_db.key_themes == result.key_themes
            assert user_db.vibe_computed_at is not None
            print(f"  ✓ DB persisted: vibe_summary, archetype, key_themes, vibe_computed_at")

        print("  PASSED")
    finally:
        server.shutdown()


def test_vibe_skipped_without_key() -> None:
    print("\n=== Test 3: synthesize_vibe skipped when no API key ===")
    factory = _get_factory()
    result = synthesize_vibe(factory, uuid.uuid4(), llm_api_key=None)
    assert result is None
    print("  ✓ Returned None when llm_api_key is None")
    print("  PASSED")


def test_vibe_skips_excluded_items() -> None:
    print("\n=== Test 4: _select_top_items skips excluded items ===")
    factory = _get_factory()
    with factory() as session:
        email = "test-exclude@example.com"
        existing = session.scalar(select(User).where(User.email == email))
        if existing:
            session.execute(text("DELETE FROM user_items WHERE user_id = :uid"), {"uid": existing.id})
            session.execute(text("DELETE FROM items WHERE service = 'exclude_test'"))
            session.execute(text("DELETE FROM service_connections WHERE user_id = :uid"), {"uid": existing.id})
            session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": existing.id})
            session.commit()

        user = _make_user(session, email)
        included = _make_item(session, "exclude_test", "Included Game", "game")
        excluded = _make_item(session, "exclude_test", "Excluded Game", "game")
        _make_user_item(session, user.id, included.id, engagement_score=0.5)
        _make_user_item(session, user.id, excluded.id, engagement_score=0.99, excluded=True)

        from syncup.embeddings.vibe_synthesizer import _select_top_items

        top = _select_top_items(session, user.id)
        names = {t.name for t in top}
        assert "Included Game" in names
        assert "Excluded Game" not in names
        print(f"  ✓ Top items: {names}")
        print("  PASSED")


if __name__ == "__main__":
    test_auto_embed()
    test_vibe_synthesis()
    test_vibe_skipped_without_key()
    test_vibe_skips_excluded_items()
    print("\n=== ALL MANUAL TESTS PASSED ===")
