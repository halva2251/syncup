"""Batch-embed all items that have no embedding yet.

Usage (from backend/):
    python scripts/populate_item_embeddings.py

Requires the [ml] extras: pip install -e '.[ml]'

Queries items WHERE embedding IS NULL, generates 384-dim embeddings using
all-MiniLM-L6-v2 via item_to_text(), and writes results back in batches.

Incremental and safe to re-run — already-embedded items are skipped.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from syncup.db.models import Item
from syncup.db.session import get_session, sessionmaker_for
from syncup.embeddings.item_text import item_to_text
from syncup.embeddings.semantic import embed_batch

logger = logging.getLogger(__name__)


def populate_item_embeddings(session: Session, *, batch_size: int = 256) -> int:
    """Embed all items with embedding IS NULL and write results back.

    Args:
        session: SQLAlchemy session.
        batch_size: number of items to embed per batch call.

    Returns:
        Total number of items embedded.
    """
    items = session.query(Item).filter(Item.embedding.is_(None)).all()

    if not items:
        return 0

    total = 0
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]

        # Filter items whose text collapses to only dashes/whitespace — these
        # arise when both name and item_type are empty and produce near-zero
        # embeddings that corrupt cosine similarity scores.
        valid_pairs = [
            (item, item_to_text(item)) for item in batch if item_to_text(item).strip(" ——")
        ]
        if len(valid_pairs) < len(batch):
            logger.warning(
                "Skipped %d item(s) with degenerate text — check name/item_type fields.",
                len(batch) - len(valid_pairs),
            )
        if not valid_pairs:
            continue

        valid_items, texts = zip(*valid_pairs)
        vectors = embed_batch(list(texts))

        now = datetime.now(UTC)
        for item, vec in zip(valid_items, vectors):
            item.embedding = vec
            item.embedding_computed_at = now

        session.commit()
        total += len(valid_items)
        logger.info("Embedded %d / %d items.", total, len(items))

    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        from syncup.config import Settings

        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:
        logger.error("Failed to load settings: %s", exc)
        sys.exit(1)

    factory = sessionmaker_for(settings.database_url)

    for session in get_session(factory):
        total = populate_item_embeddings(session)
        logger.info("Done — embedded %d items total.", total)


if __name__ == "__main__":
    main()
