"""GET /api/matches, GET /api/matches/{user_id}, POST /api/me/recompute."""
from __future__ import annotations

import base64
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, MatchCache, User, UserItem
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter
from syncup.matching.heuristic import (
    heuristic_breakdown,
    heuristic_score,
    top_shared_highlights,
)

router = APIRouter(prefix="/api", tags=["matches"])

_CACHE_MAX_AGE_HOURS = 24


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class MatchUserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    bio: str | None
    discord_handle: str | None


class SharedHighlightOut(BaseModel):
    service: str
    item_name: str


class MatchOut(BaseModel):
    user: MatchUserOut
    score: float
    breakdown: dict[str, float]
    shared_highlights: list[SharedHighlightOut]
    computed_at: datetime


class MatchListOut(BaseModel):
    items: list[MatchOut]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# Cursor helpers (simple offset cursor, replaced by ANN in Phase 2)
# ---------------------------------------------------------------------------


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(str(offset).encode()).decode()


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        return int(base64.b64decode(cursor).decode())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _load_cached_matches(user_id: uuid.UUID, db: DbSession) -> list[MatchCache]:
    cutoff = datetime.now(UTC) - timedelta(hours=_CACHE_MAX_AGE_HOURS)
    return list(
        db.scalars(
            select(MatchCache)
            .where(
                or_(MatchCache.user_a_id == user_id, MatchCache.user_b_id == user_id),
                MatchCache.computed_at >= cutoff,
            )
            .order_by(desc(MatchCache.score))
        ).all()
    )


def _refresh_match_cache(user_id: uuid.UUID, db: DbSession) -> None:
    """Compute heuristic scores vs all matchable users and write to match_cache."""
    rows = db.execute(
        select(UserItem.user_id, UserItem.item_id, Item.service, Item.name)
        .join(Item, UserItem.item_id == Item.id)
        .join(User, UserItem.user_id == User.id)
        .where(User.is_matchable == True)  # noqa: E712
    ).all()

    if not rows:
        return

    # Group: {user_id: {service: {item_id: name}}}
    user_data: dict[uuid.UUID, dict[str, dict[uuid.UUID, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for row in rows:
        user_data[row.user_id][row.service][row.item_id] = row.name

    # Item popularity: {item_id: count of users who have it}
    pop_rows = db.execute(
        select(UserItem.item_id, func.count(UserItem.user_id).label("pop"))
        .group_by(UserItem.item_id)
    ).all()
    popularity: dict[uuid.UUID, int] = {row.item_id: row.pop for row in pop_rows}

    my_data = user_data.get(user_id, {})
    if not my_data:
        return

    my_by_service = {svc: frozenset(items.keys()) for svc, items in my_data.items()}
    all_my = frozenset().union(*my_by_service.values())

    now = datetime.now(UTC)

    for other_id, other_data in user_data.items():
        if other_id == user_id:
            continue

        other_by_service = {svc: frozenset(items.keys()) for svc, items in other_data.items()}
        all_other = frozenset().union(*other_by_service.values())

        score = heuristic_score(all_my, all_other, popularity)
        breakdown = heuristic_breakdown(my_by_service, other_by_service, popularity)

        item_names: dict[uuid.UUID, str] = {}
        for svc_items in my_data.values():
            item_names.update(svc_items)
        for svc_items in other_data.values():
            item_names.update(svc_items)

        highlights = top_shared_highlights(my_by_service, other_by_service, item_names, popularity)

        a_id, b_id = (user_id, other_id) if user_id < other_id else (other_id, user_id)
        db.merge(
            MatchCache(
                user_a_id=a_id,
                user_b_id=b_id,
                score=score,
                breakdown=breakdown,
                highlights=[{"service": h.service, "item_name": h.item_name} for h in highlights],
                computed_at=now,
            )
        )

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise SyncUpError("INTERNAL_ERROR", "Failed to cache match results", 500) from exc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/matches", response_model=MatchListOut)
@limiter.limit("30/minute")
def get_matches(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> MatchListOut:
    if not user.is_matchable:
        raise SyncUpError("NOT_MATCHABLE", "Set is_matchable=true before viewing matches", 403)

    cached = _load_cached_matches(user.id, db)
    if not cached:
        _refresh_match_cache(user.id, db)
        cached = _load_cached_matches(user.id, db)

    offset = _decode_cursor(cursor)
    page = cached[offset : offset + limit]
    next_cursor = _encode_cursor(offset + limit) if offset + limit < len(cached) else None

    if not page:
        return MatchListOut(items=[], next_cursor=None)

    other_user_ids = [
        row.user_b_id if row.user_a_id == user.id else row.user_a_id for row in page
    ]
    other_users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(other_user_ids))).all()
    }

    items = []
    for row in page:
        other_id = row.user_b_id if row.user_a_id == user.id else row.user_a_id
        other = other_users.get(other_id)
        if not other:
            continue
        items.append(
            MatchOut(
                user=MatchUserOut.model_validate(other),
                score=row.score,
                breakdown=row.breakdown,
                shared_highlights=[SharedHighlightOut(**h) for h in row.highlights],
                computed_at=row.computed_at,
            )
        )

    return MatchListOut(items=items, next_cursor=next_cursor)


@router.get("/matches/{other_user_id}", response_model=MatchOut)
@limiter.limit("60/minute")
def get_match_detail(
    other_user_id: uuid.UUID,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> MatchOut:
    if not user.is_matchable:
        raise SyncUpError("NOT_MATCHABLE", "Set is_matchable=true before viewing matches", 403)

    a_id = min(user.id, other_user_id)
    b_id = max(user.id, other_user_id)
    row = db.get(MatchCache, (a_id, b_id))
    if not row:
        raise SyncUpError("NOT_FOUND", "Match not found", 404)

    other = db.get(User, other_user_id)
    if not other:
        raise SyncUpError("NOT_FOUND", "User not found", 404)

    return MatchOut(
        user=MatchUserOut.model_validate(other),
        score=row.score,
        breakdown=row.breakdown,
        shared_highlights=[SharedHighlightOut(**h) for h in row.highlights],
        computed_at=row.computed_at,
    )


@router.post("/me/recompute", status_code=204)
@limiter.limit("1/hour")
def recompute_matches(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> Response:
    """Force recompute of the user's match cache. Rate-limited to 1/hour."""
    _refresh_match_cache(user.id, db)
    return Response(status_code=204)
