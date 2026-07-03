"""GET /api/me/recommendations — cross-domain item recommendations from user embedding."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import EMBEDDING_DIM, Item, UserEmbedding, UserItem
from syncup.db.pgvector import format_vec
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.ingest._text import normalize_title
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["recommendations"])

_RECOMMENDATION_LIMIT_MAX = 50


class ItemTypeFilter(StrEnum):
    """Allowlist of valid item_type values accepted by the recommendations endpoint."""

    game = "game"
    track = "track"
    artist = "artist"
    film = "film"
    show = "show"
    anime = "anime"
    manga = "manga"
    album = "album"
    community = "community"


class RecommendationOut(BaseModel):
    item_name: str
    service: str
    item_type: str
    similarity_score: float


class RecommendationListOut(BaseModel):
    items: list[RecommendationOut]


@router.get("/recommendations", response_model=RecommendationListOut)
@limiter.limit("30/minute")
def get_recommendations(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
    item_type: ItemTypeFilter | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=_RECOMMENDATION_LIMIT_MAX),
) -> RecommendationListOut:
    """Return item recommendations for the current user.

    Uses the user's combined taste embedding to find items close in embedding
    space that are not already in the user's library. Cross-domain by default:
    the combined vector spans all connected services, so asking for
    item_type=film returns recommendations informed by gaming and music taste.

    Returns 422 NO_EMBEDDING_AVAILABLE when the user has no combined embedding.
    Build one via POST /api/embeddings/build or POST /api/me/recompute.

    The DB is oversampled (limit * 5, capped at 200) before Python post-filtering,
    so up to `limit` items are returned even when some candidates have score <= 0.
    """
    embedding = db.execute(
        select(UserEmbedding.embedding).where(
            UserEmbedding.user_id == user.id,
            UserEmbedding.service == "combined",
        )
    ).scalar_one_or_none()

    if embedding is None:
        raise SyncUpError(
            "NO_EMBEDDING_AVAILABLE",
            "Build your taste vector first via POST /api/embeddings/build"
            " or POST /api/me/recompute.",
            422,
        )

    # Titles the user already owns on ANY service, for cross-service dedup. The
    # SQL below excludes owned items by ID, but the same title can exist under
    # multiple services (different IDs) — without this a user could be recommended
    # a game they already own from a different source.
    owned_rows = db.execute(
        select(Item.name, Item.item_type)
        .join(UserItem, UserItem.item_id == Item.id)
        .where(UserItem.user_id == user.id)
    ).all()
    owned_keys = {(normalize_title(r.name), r.item_type) for r in owned_rows}

    vec_str = format_vec(list(embedding))

    # Oversample so post-filters (score <= 0, owned-by-title, title dedup) don't
    # under-deliver.
    db_limit = min(limit * 5, 200)

    base_sql = (
        f"SELECT i.name, i.service, i.item_type,"
        f" i.embedding <=> CAST(:vec AS vector({EMBEDDING_DIM})) AS distance"
        f" FROM items i"
        f" WHERE i.embedding IS NOT NULL"
        f"   AND NOT EXISTS ("
        f"       SELECT 1 FROM user_items ui"
        f"       WHERE ui.user_id = :user_id AND ui.item_id = i.id"
        f"   )"
    )
    params: dict[str, object] = {
        "vec": vec_str,
        "user_id": str(user.id),
        "db_limit": db_limit,
    }
    if item_type is not None:
        base_sql += " AND i.item_type = :item_type"
        params["item_type"] = item_type.value

    base_sql += f" ORDER BY i.embedding <=> CAST(:vec AS vector({EMBEDDING_DIM})) LIMIT :db_limit"

    rows = db.execute(text(base_sql), params).all()

    items: list[RecommendationOut] = []
    seen_titles: set[tuple[str, str]] = set()
    for row in rows:
        score = max(0.0, min(1.0, 1.0 - float(row.distance)))
        if score <= 0.0:
            continue
        key = (normalize_title(row.name), row.item_type)
        if key in owned_keys:
            # User already owns this title (possibly on a different service).
            continue
        if key in seen_titles:
            # Same title already recommended from a higher-ranked row — dedup.
            # Rows are distance-ordered, so the first occurrence is the best.
            continue
        seen_titles.add(key)
        items.append(
            RecommendationOut(
                item_name=row.name,
                service=row.service,
                item_type=row.item_type,
                similarity_score=score,
            )
        )
        if len(items) >= limit:
            break

    return RecommendationListOut(items=items)
