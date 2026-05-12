"""GET /api/matches, GET /api/matches/{user_id}, POST /api/me/recompute."""
from __future__ import annotations

import base64
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

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

logger = logging.getLogger(__name__)

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
        logger.warning("Invalid match cursor %r — resetting to page 0", cursor)
        return 0


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

# Phase 1 cap: loading all matchable users' items into memory is fine at
# 0–500 users (max ~50k rows). Replace with chunked iteration or a
# server-side cursor before scaling beyond that.
_MAX_HEURISTIC_USERS = 500


def _load_cached_matches(
    user_id: uuid.UUID,
    db: DbSession,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[MatchCache], bool]:
    """Load a page of cached matches. Returns (rows, has_more).

    Fetches limit+1 rows so the caller can detect whether another page exists
    without a separate COUNT query.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=_CACHE_MAX_AGE_HOURS)
    rows = list(
        db.scalars(
            select(MatchCache)
            .where(
                or_(MatchCache.user_a_id == user_id, MatchCache.user_b_id == user_id),
                MatchCache.computed_at >= cutoff,
            )
            .order_by(desc(MatchCache.score))
            .limit(limit + 1)
            .offset(offset)
        ).all()
    )
    has_more = len(rows) > limit
    return rows[:limit], has_more


# ---------------------------------------------------------------------------
# Match cache refresh — split into read / compute / write phases
# ---------------------------------------------------------------------------


def _read_match_data(
    db_factory: sessionmaker[DbSession],
    user_id: uuid.UUID,
) -> tuple[list, list, list] | None:
    """Phase 1: fetch all data needed for match computation.

    Opens its own session and closes it before returning so read locks are
    released before the (longer) compute phase begins.
    """
    db = db_factory()
    try:
        matchable_ids = list(
            db.scalars(
                select(User.id)
                .where(User.is_matchable == True)  # noqa: E712
                .limit(_MAX_HEURISTIC_USERS)
            ).all()
        )

        if not matchable_ids:
            return None

        rows = list(
            db.execute(
                select(UserItem.user_id, UserItem.item_id, Item.service, Item.name)
                .join(Item, UserItem.item_id == Item.id)
                .where(UserItem.user_id.in_(matchable_ids))
            ).all()
        )

        if not rows:
            return None

        pop_rows = list(
            db.execute(
                select(UserItem.item_id, func.count(UserItem.user_id).label("pop"))
                .where(UserItem.user_id.in_(matchable_ids))
                .group_by(UserItem.item_id)
            ).all()
        )

        return matchable_ids, rows, pop_rows

    except Exception:
        logger.exception("Match cache read phase failed for user %s", user_id)
        return None
    finally:
        db.close()


def _compute_match_scores(
    user_id: uuid.UUID,
    matchable_ids: list,
    rows: list,
    pop_rows: list,
    now: datetime,
) -> list[MatchCache]:
    """Phase 2: pure Python computation — no DB access."""
    user_data: dict[uuid.UUID, dict[str, dict[uuid.UUID, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for row in rows:
        user_data[row.user_id][row.service][row.item_id] = row.name

    popularity: dict[uuid.UUID, int] = {row.item_id: row.pop for row in pop_rows}

    my_data = user_data.get(user_id, {})
    if not my_data:
        return []

    my_by_service = {svc: frozenset(items.keys()) for svc, items in my_data.items()}
    all_my = frozenset().union(*my_by_service.values())

    my_item_names: dict[uuid.UUID, str] = {}
    for svc_items in my_data.values():
        my_item_names.update(svc_items)

    results: list[MatchCache] = []
    for other_id, other_data in user_data.items():
        if other_id == user_id:
            continue

        other_by_service = {svc: frozenset(items.keys()) for svc, items in other_data.items()}
        all_other = frozenset().union(*other_by_service.values())

        score = heuristic_score(all_my, all_other, popularity)
        breakdown = heuristic_breakdown(my_by_service, other_by_service, popularity)

        item_names = {**my_item_names}
        for svc_items in other_data.values():
            item_names.update(svc_items)

        highlights = top_shared_highlights(my_by_service, other_by_service, item_names, popularity)

        a_id = min(user_id, other_id)
        b_id = max(user_id, other_id)
        results.append(
            MatchCache(
                user_a_id=a_id,
                user_b_id=b_id,
                score=score,
                breakdown=breakdown,
                highlights=[{"service": h.service, "item_name": h.item_name} for h in highlights],
                computed_at=now,
            )
        )

    return results


def _write_match_results(
    db_factory: sessionmaker[DbSession],
    results: list[MatchCache],
) -> None:
    """Phase 3: write computed match rows. Opens a short-lived write session."""
    db = db_factory()
    try:
        for row in results:
            db.merge(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Match cache write phase failed")
    finally:
        db.close()


def _refresh_match_cache(
    db_factory: sessionmaker[DbSession], user_id: uuid.UUID
) -> None:
    """Compute heuristic scores vs all matchable users and write to match_cache.

    Runs as a BackgroundTask. Splits into read / compute / write phases so that
    the write transaction is as short as possible.
    """
    data = _read_match_data(db_factory, user_id)
    if data is None:
        return

    matchable_ids, rows, pop_rows = data
    now = datetime.now(UTC)
    results = _compute_match_scores(user_id, matchable_ids, rows, pop_rows, now)

    if results:
        _write_match_results(db_factory, results)


# ---------------------------------------------------------------------------
# D1 — stale match_cache cleanup
# ---------------------------------------------------------------------------


def _cleanup_stale_match_cache(db_factory: sessionmaker[DbSession]) -> None:
    """Delete match_cache rows older than _CACHE_MAX_AGE_HOURS.

    Called by the hourly cleanup loop started in the app lifespan.
    """
    db = db_factory()
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=_CACHE_MAX_AGE_HOURS)
        db.execute(sa_delete(MatchCache).where(MatchCache.computed_at < cutoff))
        db.commit()
        logger.info("match_cache cleanup complete (cutoff=%s)", cutoff.isoformat())
    except Exception:
        db.rollback()
        logger.exception("match_cache cleanup failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/matches", response_model=MatchListOut)
@limiter.limit("30/minute")
def get_matches(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> MatchListOut:
    if not user.is_matchable:
        raise SyncUpError("NOT_MATCHABLE", "Set is_matchable=true before viewing matches", 403)

    offset = _decode_cursor(cursor)
    page, has_more = _load_cached_matches(user.id, db, limit=limit, offset=offset)

    if not page:
        # Empty page means either no cache or the cache expired mid-session.
        # Always schedule a background refresh so the client gets fresh results
        # on the next request, regardless of which page they were on.
        background_tasks.add_task(_refresh_match_cache, request.app.state.db, user.id)
        return MatchListOut(items=[], next_cursor=None)

    next_cursor = _encode_cursor(offset + limit) if has_more else None

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
    if user.id not in (row.user_a_id, row.user_b_id):
        raise SyncUpError("FORBIDDEN", "Not your match", 403)

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
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> Response:
    """Force recompute of the user's match cache. Rate-limited to 1/hour."""
    background_tasks.add_task(_refresh_match_cache, request.app.state.db, user.id)
    return Response(status_code=204)
