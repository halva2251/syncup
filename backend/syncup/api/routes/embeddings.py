"""POST /api/embeddings/build — compute the current user's combined taste vector."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, PreferenceOverride, UserDimensionWeight, UserEmbedding, UserItem
from syncup.db.session import get_db
from syncup.embeddings.user_embeddings import aggregate_vectors
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])

# Maximum items per service to include in the user vector.
# Without a cap, a 500-game Steam library dominates the vector by sheer
# averaging mass, not by taste intensity.
_SERVICE_CAP = 50


class EmbeddingBuiltOut(BaseModel):
    service: str
    item_count: int
    computed_at: datetime


def build_user_embedding(
    db: DbSession,
    user_id: uuid.UUID,
) -> EmbeddingBuiltOut:
    """Core logic — query DB, aggregate vectors, upsert result.

    Separated from the route handler so it can be called from background tasks
    (e.g. POST /api/me/recompute).

    Raises:
        SyncUpError(NO_EMBEDDINGS_AVAILABLE, 422): no embedded items found.
    """
    # Single query: user_items JOIN items, LEFT JOIN dimension_weights and overrides.
    # Returns one row per qualifying (user_item, item) pair.
    stmt = (
        select(
            Item.service,
            UserItem.engagement_score,
            Item.embedding,
            PreferenceOverride.boost_multiplier,
            UserDimensionWeight.weight.label("dim_weight"),
        )
        .join(Item, UserItem.item_id == Item.id)
        .outerjoin(
            PreferenceOverride,
            (PreferenceOverride.user_id == user_id) & (PreferenceOverride.item_id == Item.id),
        )
        .outerjoin(
            UserDimensionWeight,
            (UserDimensionWeight.user_id == user_id)
            & (UserDimensionWeight.service == Item.service),
        )
        .where(
            UserItem.user_id == user_id,
            UserItem.excluded.is_(False),
            Item.embedding.is_not(None),
        )
    )
    rows = db.execute(stmt).fetchall()

    if not rows:
        raise SyncUpError(
            "NO_EMBEDDINGS_AVAILABLE",
            "No embedded items found. Run the enrichment and populate scripts first, "
            "or sync a connected service.",
            422,
        )

    # Group by service and apply per-service top-50 cap.
    by_service: dict[str, list] = defaultdict(list)
    for row in rows:
        by_service[row.service].append(row)

    pairs: list[tuple[list[float], float]] = []
    total_items = 0
    for service_rows in by_service.values():
        # Sort descending by engagement_score and take the top SERVICE_CAP items.
        capped = sorted(service_rows, key=lambda r: r.engagement_score, reverse=True)[:_SERVICE_CAP]
        for row in capped:
            dim_weight = row.dim_weight if row.dim_weight is not None else 1.0
            boost = row.boost_multiplier if row.boost_multiplier is not None else 1.0
            scale = dim_weight * boost
            # Scale the vector so log1p dampening inside aggregate_vectors applies
            # to engagement_score alone; dim_weight and boost remain true linear
            # multipliers: effective weight = log1p(engagement_score) * dim_weight * boost
            if scale > 0 and row.engagement_score > 0:
                pairs.append(([v * scale for v in row.embedding], row.engagement_score))
                total_items += 1

    if not pairs:
        raise SyncUpError(
            "NO_EMBEDDINGS_AVAILABLE",
            "All qualifying items have zero effective weight.",
            422,
        )

    combined = aggregate_vectors(pairs)
    now = datetime.now(UTC)

    embedding_row = UserEmbedding(
        user_id=user_id,
        service="combined",
        embedding=combined,
        computed_at=now,
    )
    db.merge(embedding_row)
    db.commit()

    logger.info(
        "Built combined embedding for user %s from %d items across %d service(s)",
        user_id,
        total_items,
        len(by_service),
    )
    return EmbeddingBuiltOut(service="combined", item_count=total_items, computed_at=now)


@router.post("/build", response_model=EmbeddingBuiltOut)
@limiter.limit("5/minute")
def build_embedding(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> EmbeddingBuiltOut:
    """Compute (or recompute) the current user's combined taste vector.

    Aggregates all non-excluded user items that have embeddings, applies per-service
    dimension weights and preference override boost multipliers, and writes a single
    384-dim L2-normalised vector to user_embeddings with service='combined'.

    Returns 422 NO_EMBEDDINGS_AVAILABLE if no items have embeddings yet.
    """
    return build_user_embedding(db, user.id)
