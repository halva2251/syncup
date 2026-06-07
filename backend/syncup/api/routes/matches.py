"""GET /api/matches, GET /api/matches/{user_id}, POST /api/me/recompute."""

import base64
import logging
import threading
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import and_, desc, func, or_, select, text
from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from syncup.api.routes.embeddings import build_user_embedding  # noqa: E402
from syncup.auth.router import RequireAuth
from syncup.db.models import EMBEDDING_DIM, Item, MatchCache, User, UserEmbedding, UserItem
from syncup.db.pgvector import format_vec
from syncup.db.session import get_db
from syncup.embeddings.vibe_synthesizer import synthesize_vibe
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
_SEMANTIC_CANDIDATE_LIMIT = 50

# In-flight guard: dedupe redundant background match-cache refreshes for the same
# user. Without it, repeated empty-page GET /api/matches requests (which schedule a
# refresh each time) can stack N concurrent _refresh_match_cache runs, amplifying
# the db.merge()-in-a-loop write contention. BackgroundTasks run in the process
# threadpool, so a module-level set + lock is sufficient.
_refresh_in_flight: set[uuid.UUID] = set()
_refresh_in_flight_lock = threading.Lock()


def _try_acquire_refresh(user_id: uuid.UUID) -> bool:
    """Return True and mark the user in-flight if no refresh is already scheduled."""
    with _refresh_in_flight_lock:
        if user_id in _refresh_in_flight:
            return False
        _refresh_in_flight.add(user_id)
        return True


def _release_refresh(user_id: uuid.UUID) -> None:
    with _refresh_in_flight_lock:
        _refresh_in_flight.discard(user_id)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class MatchUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    matching_mode: Literal["heuristic", "semantic"]


class MatchListOut(BaseModel):
    items: list[MatchOut]
    next_cursor: str | None


def _parse_highlights(raw: object) -> list[SharedHighlightOut]:
    """Defensively parse cached highlight JSON.

    A drifted or legacy match_cache row (e.g. a malformed dict or a non-dict
    entry) must not 500 the whole matches response — skip the bad entry and log.
    """
    result: list[SharedHighlightOut] = []
    if not isinstance(raw, list):
        return result
    for entry in raw:
        try:
            result.append(SharedHighlightOut.model_validate(entry))
        except (ValidationError, TypeError):
            logger.warning("Skipping malformed highlight in match_cache: %r", entry)
    return result


# ---------------------------------------------------------------------------
# Cursor helpers — keyset on (score DESC, user_a_id ASC, user_b_id ASC)
#
# Using both PK columns as tie-breakers guarantees stable pagination regardless
# of whether the current user is the A-side or B-side of the match pair.
# A single user_b_id tie-breaker would silently skip rows when the current user
# appears as user_b_id (multiple rows would share the same user_b_id value).
# ---------------------------------------------------------------------------


def _encode_cursor(score: float, user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> str:
    """Encode a keyset cursor as base64(score:user_a_id:user_b_id).

    `repr(score)` round-trips losslessly back to the same float (Python's
    repr produces the shortest string that parses back to the exact value),
    unlike `:.6f` which rounds and breaks the `score == cursor_score`
    tie-break branch in keyset pagination.
    """
    return base64.b64encode(f"{score!r}:{user_a_id}:{user_b_id}".encode()).decode()


def _decode_cursor(
    cursor: str | None,
) -> tuple[float, uuid.UUID, uuid.UUID] | None:
    """Decode a keyset cursor; return None on any parse error."""
    if cursor is None:
        return None
    try:
        decoded = base64.b64decode(cursor).decode()
        score_str, a_str, b_str = decoded.split(":", 2)
        return float(score_str), uuid.UUID(a_str), uuid.UUID(b_str)
    except Exception:
        logger.warning("Invalid match cursor %r — ignoring", cursor)
        return None


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
    cursor_score: float | None = None,
    cursor_user_a_id: uuid.UUID | None = None,
    cursor_user_b_id: uuid.UUID | None = None,
) -> tuple[list[MatchCache], bool]:
    """Load a page of cached matches using a keyset cursor on
    (score DESC, user_a_id ASC, user_b_id ASC).

    Returns (rows, has_more). Fetches limit+1 to detect the next page without COUNT.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=_CACHE_MAX_AGE_HOURS)
    base_filter = [
        or_(MatchCache.user_a_id == user_id, MatchCache.user_b_id == user_id),
        MatchCache.computed_at >= cutoff,
    ]
    if cursor_score is not None and cursor_user_a_id is not None and cursor_user_b_id is not None:
        base_filter.append(
            or_(
                MatchCache.score < cursor_score,
                and_(MatchCache.score == cursor_score, MatchCache.user_a_id > cursor_user_a_id),
                and_(
                    MatchCache.score == cursor_score,
                    MatchCache.user_a_id == cursor_user_a_id,
                    MatchCache.user_b_id > cursor_user_b_id,
                ),
            )
        )
    rows = list(
        db.scalars(
            select(MatchCache)
            .where(*base_filter)
            .order_by(
                desc(MatchCache.score), MatchCache.user_a_id.asc(), MatchCache.user_b_id.asc()
            )
            .limit(limit + 1)
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
                matching_mode="heuristic",
            )
        )

    return results


def _write_match_results(
    db_factory: sessionmaker[DbSession],
    results: list[MatchCache],
) -> None:
    """Phase 3: write computed match rows. Opens a short-lived write session.

    Uses a single bulk upsert rather than `db.merge()` per row — merge() issues
    a SELECT then INSERT/UPDATE per row, which is hundreds of round-trips for a
    full candidate set.
    """
    db = db_factory()
    try:
        if results:
            values = [
                {
                    "user_a_id": row.user_a_id,
                    "user_b_id": row.user_b_id,
                    "score": row.score,
                    "breakdown": row.breakdown,
                    "highlights": row.highlights,
                    "computed_at": row.computed_at,
                    "matching_mode": row.matching_mode,
                }
                for row in results
            ]
            stmt = pg_insert(MatchCache).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[MatchCache.user_a_id, MatchCache.user_b_id],
                set_={
                    "score": stmt.excluded.score,
                    "breakdown": stmt.excluded.breakdown,
                    "highlights": stmt.excluded.highlights,
                    "computed_at": stmt.excluded.computed_at,
                    "matching_mode": stmt.excluded.matching_mode,
                },
            )
            db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Match cache write phase failed")
    finally:
        db.close()


def _read_semantic_data(
    db_factory: sessionmaker[DbSession],
    user_id: uuid.UUID,
) -> tuple[list[tuple[uuid.UUID, float]], list, list] | None:
    """Load the user's combined embedding and run ANN search.

    Returns (candidate_pairs, item_rows, pop_rows) or None when the user has no
    combined embedding or no ANN neighbours are found.
    """
    db = db_factory()
    try:
        embedding = db.execute(
            select(UserEmbedding.embedding).where(
                UserEmbedding.user_id == user_id,
                UserEmbedding.service == "combined",
            )
        ).scalar_one_or_none()

        if embedding is None:
            return None

        vec_str = format_vec(list(embedding))

        ann_rows = list(
            db.execute(
                text(
                    f"""
                    SELECT user_id, embedding <=> CAST(:vec AS vector({EMBEDDING_DIM})) AS distance
                    FROM user_embeddings
                    WHERE service = 'combined'
                      AND user_id != :user_id
                      AND user_id IN (SELECT id FROM users WHERE is_matchable = true)
                    ORDER BY embedding <=> CAST(:vec AS vector({EMBEDDING_DIM}))
                    LIMIT :limit
                    """
                ),
                {"vec": vec_str, "user_id": str(user_id), "limit": _SEMANTIC_CANDIDATE_LIMIT},
            ).all()
        )

        if not ann_rows:
            return None

        candidate_pairs = [(uuid.UUID(str(r.user_id)), float(r.distance)) for r in ann_rows]
        candidate_ids = [pair[0] for pair in candidate_pairs]
        all_user_ids = [user_id, *candidate_ids]

        item_rows = list(
            db.execute(
                select(UserItem.user_id, UserItem.item_id, Item.service, Item.name)
                .join(Item, UserItem.item_id == Item.id)
                .where(UserItem.user_id.in_(all_user_ids))
            ).all()
        )

        pop_rows = list(
            db.execute(
                select(UserItem.item_id, func.count(UserItem.user_id).label("pop"))
                .where(UserItem.user_id.in_(all_user_ids))
                .group_by(UserItem.item_id)
            ).all()
        )

        return candidate_pairs, item_rows, pop_rows

    except Exception:
        logger.exception("Semantic data read failed for user %s", user_id)
        return None
    finally:
        db.close()


def _compute_semantic_scores(
    user_id: uuid.UUID,
    candidate_pairs: list[tuple[uuid.UUID, float]],
    item_rows: list,
    pop_rows: list,
    now: datetime,
) -> list[MatchCache]:
    """Compute semantic match rows from ANN distances. Score = 1 - distance, clamped to [0, 1]."""
    if not candidate_pairs:
        return []

    popularity: dict[uuid.UUID, int] = {r.item_id: r.pop for r in pop_rows}

    user_data: dict[uuid.UUID, dict[str, dict[uuid.UUID, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for row in item_rows:
        user_data[row.user_id][row.service][row.item_id] = row.name

    my_data = user_data.get(user_id, {})
    my_by_service = {svc: frozenset(items.keys()) for svc, items in my_data.items()}
    my_item_names: dict[uuid.UUID, str] = {}
    for svc_items in my_data.values():
        my_item_names.update(svc_items)

    results: list[MatchCache] = []
    for other_id, distance in candidate_pairs:
        raw_similarity = 1.0 - distance
        if raw_similarity <= 0.0:
            # cosine distance > 1.0 means opposite or unrelated taste vectors — skip
            continue
        score = min(1.0, raw_similarity)

        other_data = user_data.get(other_id, {})
        other_by_service = {svc: frozenset(items.keys()) for svc, items in other_data.items()}

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
                breakdown={"combined": score},
                highlights=[{"service": h.service, "item_name": h.item_name} for h in highlights],
                computed_at=now,
                matching_mode="semantic",
            )
        )

    return results


def _build_embedding_bg(db_factory: sessionmaker[DbSession], user_id: uuid.UUID) -> None:
    """Build the user's combined embedding. Swallows NO_EMBEDDINGS_AVAILABLE gracefully."""
    db = db_factory()
    try:
        build_user_embedding(db, user_id)
    except SyncUpError:
        logger.debug("No item embeddings for user %s — skipping embedding build", user_id)
    except Exception:
        logger.exception("Unexpected error building embedding for user %s", user_id)
    finally:
        db.close()


def _refresh_match_cache(db_factory: sessionmaker[DbSession], user_id: uuid.UUID) -> None:
    """Recompute match scores and write to match_cache.

    Uses the semantic ANN path when a combined embedding exists; that path is
    authoritative — even if every ANN neighbour scores <= 0 it does NOT fall
    through to the heuristic path, which would recompute against all users, flip
    matching_mode, and churn symmetric cache rows (roadmap §2.6 b). The heuristic
    item-overlap path is used only when the user has no combined embedding at all.

    Runs as a BackgroundTask; splits into read / compute / write phases so the
    write transaction is as short as possible. Always releases the in-flight guard.
    """
    try:
        semantic_data = _read_semantic_data(db_factory, user_id)

        if semantic_data is not None:
            candidate_pairs, item_rows, pop_rows = semantic_data
            now = datetime.now(UTC)
            results = _compute_semantic_scores(user_id, candidate_pairs, item_rows, pop_rows, now)
            if results:
                _write_match_results(db_factory, results)
            # Semantic mode is authoritative once an embedding exists — stop here.
            return

        data = _read_match_data(db_factory, user_id)
        if data is None:
            return

        matchable_ids, rows, pop_rows = data
        now = datetime.now(UTC)
        results = _compute_match_scores(user_id, matchable_ids, rows, pop_rows, now)

        if results:
            _write_match_results(db_factory, results)
    finally:
        _release_refresh(user_id)


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

    cursor_data = _decode_cursor(cursor)
    page, has_more = _load_cached_matches(
        user.id,
        db,
        limit=limit,
        cursor_score=cursor_data[0] if cursor_data else None,
        cursor_user_a_id=cursor_data[1] if cursor_data else None,
        cursor_user_b_id=cursor_data[2] if cursor_data else None,
    )

    if not page:
        # Empty page means either no cache or the cache expired mid-session.
        # Schedule a background refresh so the client gets fresh results on the
        # next request — but only if one isn't already in flight for this user,
        # to avoid stacking redundant concurrent refreshes.
        if _try_acquire_refresh(user.id):
            background_tasks.add_task(_refresh_match_cache, request.app.state.db, user.id)
        return MatchListOut(items=[], next_cursor=None)

    last_row = page[-1]
    next_cursor = (
        _encode_cursor(last_row.score, last_row.user_a_id, last_row.user_b_id) if has_more else None
    )

    other_user_ids = [row.user_b_id if row.user_a_id == user.id else row.user_a_id for row in page]
    other_users = {
        u.id: u for u in db.scalars(select(User).where(User.id.in_(other_user_ids))).all()
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
                shared_highlights=_parse_highlights(row.highlights),
                computed_at=row.computed_at,
                matching_mode=cast(Literal["heuristic", "semantic"], row.matching_mode),
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
        shared_highlights=_parse_highlights(row.highlights),
        computed_at=row.computed_at,
        matching_mode=cast(Literal["heuristic", "semantic"], row.matching_mode),
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
    background_tasks.add_task(_build_embedding_bg, request.app.state.db, user.id)
    background_tasks.add_task(_refresh_match_cache, request.app.state.db, user.id)
    settings = request.app.state.settings
    if settings.llm_api_key:
        background_tasks.add_task(
            synthesize_vibe,
            request.app.state.db,
            user.id,
            settings.llm_api_key,
            settings.llm_base_url,
            settings.llm_model,
        )
    return Response(status_code=204)
