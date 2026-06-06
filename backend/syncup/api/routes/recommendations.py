"""GET /api/me/recommendations — cross-domain item recommendations from user embedding."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

# Import the shared vec-formatting helper from matches.py — both routes use the
# same pgvector literal format and must stay in sync with the precision.
from syncup.api.routes.matches import _format_vec  # noqa: E402
from syncup.auth.router import RequireAuth
from syncup.db.models import EMBEDDING_DIM, UserEmbedding
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["recommendations"])

_RECOMMENDATION_LIMIT_MAX = 50


class ItemTypeFilter(str, Enum):
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

    The DB is oversampled (limit * 3, capped at 150) before Python post-filtering,
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
            "Build your taste vector first via POST /api/embeddings/build or POST /api/me/recompute.",
            422,
        )

    vec_str = _format_vec(list(embedding))

    # Oversample so post-filter (score <= 0) doesn't under-deliver.
    db_limit = min(limit * 3, 150)

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
    for row in rows:
        score = max(0.0, min(1.0, 1.0 - float(row.distance)))
        if score <= 0.0:
            continue
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
