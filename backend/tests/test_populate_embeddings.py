"""Tests for scripts/populate_item_embeddings.py."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from tests.http_helpers import make_session


def _make_item(
    name: str = "Disco Elysium",
    item_type: str = "game",
    embedding: list[float] | None = None,
    meta: dict | None = None,
) -> MagicMock:
    ns = MagicMock()
    ns.id = uuid.uuid4()
    ns.name = name
    ns.item_type = item_type
    ns.meta = meta or {}
    ns.embedding = embedding
    ns.embedding_computed_at = None
    return ns


_FAKE_EMBEDDING = [0.1] * 384


from scripts.populate_item_embeddings import populate_item_embeddings


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_embeds_items_without_embedding(mock_embed: MagicMock) -> None:
    item = _make_item()
    session = make_session([item])
    mock_embed.return_value = [_FAKE_EMBEDDING]

    count = populate_item_embeddings(session, batch_size=256)

    assert count == 1
    assert item.embedding == _FAKE_EMBEDDING
    assert item.embedding_computed_at is not None
    session.commit.assert_called()


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_sets_embedding_computed_at(mock_embed: MagicMock) -> None:
    item = _make_item()
    session = make_session([item])
    mock_embed.return_value = [_FAKE_EMBEDDING]

    populate_item_embeddings(session, batch_size=256)

    assert isinstance(item.embedding_computed_at, datetime)


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_returns_count(mock_embed: MagicMock) -> None:
    items = [_make_item("Game A"), _make_item("Game B"), _make_item("Game C")]
    session = make_session(items)
    mock_embed.return_value = [_FAKE_EMBEDDING, _FAKE_EMBEDDING, _FAKE_EMBEDDING]

    count = populate_item_embeddings(session, batch_size=256)

    assert count == 3


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_empty_list_returns_zero(mock_embed: MagicMock) -> None:
    session = make_session([])

    count = populate_item_embeddings(session, batch_size=256)

    assert count == 0
    mock_embed.assert_not_called()


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_processes_in_batches(mock_embed: MagicMock) -> None:
    items = [_make_item(f"Item {i}") for i in range(5)]
    session = make_session(items)
    mock_embed.side_effect = [
        [_FAKE_EMBEDDING] * 3,  # first batch of 3
        [_FAKE_EMBEDDING] * 2,  # second batch of 2
    ]

    count = populate_item_embeddings(session, batch_size=3)

    assert count == 5
    assert mock_embed.call_count == 2


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_commits_per_batch(mock_embed: MagicMock) -> None:
    items = [_make_item(f"Item {i}") for i in range(4)]
    session = make_session(items)
    mock_embed.side_effect = [
        [_FAKE_EMBEDDING] * 2,
        [_FAKE_EMBEDDING] * 2,
    ]

    populate_item_embeddings(session, batch_size=2)

    assert session.commit.call_count == 2


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_uses_item_to_text_for_text_generation(mock_embed: MagicMock) -> None:
    item = _make_item("Hollow Knight", "game", meta={"genres": ["Metroidvania", "Action"]})
    session = make_session([item])
    mock_embed.return_value = [_FAKE_EMBEDDING]

    populate_item_embeddings(session, batch_size=256)

    texts = mock_embed.call_args[0][0]
    assert len(texts) == 1
    assert "Hollow Knight" in texts[0]
    assert "game" in texts[0]


@patch("scripts.populate_item_embeddings.embed_batch")
def test_populate_skips_degenerate_items_and_counts_only_valid(mock_embed: MagicMock) -> None:
    # An item with empty name and item_type produces " — " from item_to_text(),
    # which collapses to nothing after stripping and must not be passed to embed_batch.
    good = _make_item("Disco Elysium", "game")
    degenerate = _make_item("", "")
    session = make_session([good, degenerate])
    mock_embed.return_value = [_FAKE_EMBEDDING]  # only one valid item

    count = populate_item_embeddings(session, batch_size=256)

    assert count == 1
    assert good.embedding == _FAKE_EMBEDDING
    # embed_batch received only the good item's text
    texts = mock_embed.call_args[0][0]
    assert len(texts) == 1
    session.commit.assert_called_once()
