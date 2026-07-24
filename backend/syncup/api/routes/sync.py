"""Sync routes: POST /api/sync/{service} — trigger background data pull."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, ServiceConnection, UserItem
from syncup.db.session import get_db
from syncup.embeddings.vibe_synthesizer import synthesize_vibe
from syncup.exceptions import SyncUpError
from syncup.ingest.crypto import encrypt_token
from syncup.ingest.protocol import SyncClientError
from syncup.ingest.registry import get_client
from syncup.limiter import limiter
from syncup.matching.recompute import recompute_user_matching_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_ITEMS_TABLE = Item.__table__
_USER_ITEMS_TABLE = UserItem.__table__


class SyncTriggeredOut(BaseModel):
    status: Literal["syncing"]
    service: str
    poll_url: str


# ---------------------------------------------------------------------------
# Upsert helpers (PostgreSQL dialect — atomic insert-or-update)
# ---------------------------------------------------------------------------


def _upsert_item(
    db: DbSession,
    service: str,
    item_type: str,
    external_id: str,
    name: str,
    meta: dict[str, Any],
) -> uuid.UUID:
    ins = pg_insert(_ITEMS_TABLE).values(  # type: ignore[arg-type]
        id=uuid.uuid4(),
        service=service,
        item_type=item_type,
        external_id=external_id,
        name=name,
        metadata=meta,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["service", "item_type", "external_id"],
        set_={"name": ins.excluded.name, "metadata": ins.excluded.metadata},
    ).returning(_ITEMS_TABLE.c.id)
    return db.execute(stmt).scalar_one()  # type: ignore[no-any-return]


def _upsert_user_item(
    db: DbSession,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    engagement_score: float,
    raw_value: float | None,
    raw_type: str,
    last_engaged_at: datetime | None = None,
) -> None:
    now = datetime.now(UTC)
    ins = pg_insert(_USER_ITEMS_TABLE).values(  # type: ignore[arg-type]
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        engagement_score=engagement_score,
        raw_value=raw_value,
        raw_type=raw_type,
        last_engaged_at=last_engaged_at,
        fetched_at=now,
    )
    db.execute(
        ins.on_conflict_do_update(
            index_elements=["user_id", "item_id"],
            set_={
                "engagement_score": ins.excluded.engagement_score,
                "raw_value": ins.excluded.raw_value,
                "raw_type": ins.excluded.raw_type,
                "last_engaged_at": ins.excluded.last_engaged_at,
                "fetched_at": ins.excluded.fetched_at,
            },
        )
    )


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error string — never exposes raw upstream responses."""
    if isinstance(exc, SyncClientError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Upstream API returned {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return "Network error reaching upstream service"
    return "Sync failed — please retry"


def _set_sync_error(session: DbSession, user_id: uuid.UUID, service: str, error: str) -> None:
    """Write sync_status=error after a failed sync; safe to call after rollback."""
    try:
        session.execute(
            update(ServiceConnection)
            .where(
                ServiceConnection.user_id == user_id,
                ServiceConnection.service == service,
            )
            .values(sync_status="error", sync_error=error[:1000])
        )
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Failed to write sync error status for user %s / %s", user_id, service)


# ---------------------------------------------------------------------------
# Generic background sync task
# ---------------------------------------------------------------------------

_MAX_AUTO_EMBED_ITEMS = 200


def _embed_new_items(session: DbSession, user_id: uuid.UUID, service: str) -> None:
    """Embed items from this sync that don't have embeddings yet.

    Called within the sync session after a successful commit. Embedding failures
    are logged but do not roll back the sync — items can be embedded by the
    populate script later.
    """
    from syncup.embeddings.item_text import item_to_text
    from syncup.embeddings.semantic import embed_batch

    items = list(
        session.scalars(
            select(Item)
            .join(UserItem, UserItem.item_id == Item.id)
            .where(
                UserItem.user_id == user_id,
                Item.service == service,
                Item.embedding.is_(None),
            )
            # Cap the synchronous embed_batch call for power users with huge
            # libraries — remaining items stay embedding=NULL and get picked
            # up by this same query on the user's next sync.
            .limit(_MAX_AUTO_EMBED_ITEMS)
        ).all()
    )

    if not items:
        return

    texts = [item_to_text(item) for item in items]
    try:
        embeddings = embed_batch(texts)
    except Exception:
        logger.warning("Auto-embed skipped for user %s/%s: embed_batch failed", user_id, service)
        return

    now = datetime.now(UTC)
    for item, emb in zip(items, embeddings, strict=True):
        item.embedding = emb
        item.embedding_computed_at = now
    session.commit()
    logger.info("Auto-embedded %d items for user %s / %s", len(items), user_id, service)


def embed_and_recompute_imported_service(
    db_factory: sessionmaker[DbSession], user_id: uuid.UUID, service: str
) -> None:
    """Embed a CSV import before rebuilding its derived matching data."""
    session = db_factory()
    try:
        _embed_new_items(session, user_id, service)
    except Exception:
        logger.exception("Post-import embedding failed for user %s/%s", user_id, service)
    finally:
        session.close()
    recompute_user_matching_data(db_factory, user_id)


def _do_sync_generic(
    db_factory: sessionmaker[DbSession],
    user_id: uuid.UUID,
    service: str,
    llm_api_key: str | None = None,
    llm_base_url: str = "https://api.deepseek.com",
    llm_model: str = "deepseek-chat",
) -> None:
    session = db_factory()
    sync_ok = False
    try:
        conn = session.scalar(
            select(ServiceConnection).where(
                ServiceConnection.user_id == user_id,
                ServiceConnection.service == service,
            )
        )
        if conn is None:
            return

        client = get_client(service)

        # Refresh OAuth token if the client signals it is needed.
        new_tokens = client.refresh_token(conn)
        if new_tokens is not None:
            conn.access_token_encrypted = encrypt_token(new_tokens.access_token)
            if new_tokens.refresh_token is not None:
                conn.refresh_token_encrypted = encrypt_token(new_tokens.refresh_token)
            conn.token_expires_at = new_tokens.expires_at
            session.flush()

        raw_items = client.fetch_items(conn)

        items_synced = 0
        for raw_item in raw_items:
            item_id = _upsert_item(
                session,
                service,
                raw_item["item_type"],
                raw_item["external_id"],
                raw_item["name"],
                raw_item["metadata"],
            )
            _upsert_user_item(
                session,
                user_id,
                item_id,
                max(0.0, min(1.0, raw_item["engagement_score"])),
                raw_item["raw_value"],
                raw_item["raw_type"],
                last_engaged_at=raw_item["last_engaged_at"],
            )
            items_synced += 1

        conn.sync_status = "ok"
        conn.last_synced_at = datetime.now(UTC)
        conn.sync_error = None
        session.commit()
        logger.info("%s sync done for user %s: %d items", service, user_id, items_synced)
        sync_ok = True
        try:
            _embed_new_items(session, user_id, service)
        except Exception:
            logger.warning("Auto-embed failed for user %s/%s — sync preserved", user_id, service)

    except Exception as exc:
        logger.exception("%s sync failed for user %s", service, user_id)
        session.rollback()
        _set_sync_error(session, user_id, service, _safe_error_message(exc))

    finally:
        session.close()

    if sync_ok:
        # New or changed service data must affect matching without requiring the
        # user to discover and press the manual refresh control.
        recompute_user_matching_data(db_factory, user_id)
        if llm_api_key:
            synthesize_vibe(db_factory, user_id, llm_api_key, llm_base_url, llm_model)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/{service}", response_model=SyncTriggeredOut)
@limiter.limit("5/minute")
def trigger_sync(
    service: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> SyncTriggeredOut:
    """Trigger a background data pull for a connected service."""
    try:
        get_client(service)
    except KeyError:
        raise SyncUpError("SERVICE_NOT_FOUND", f"Unknown service: {service!r}", 404) from None

    conn = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.service == service,
        )
    )
    if conn is None:
        raise SyncUpError(
            "SERVICE_NOT_CONNECTED",
            f"{service} is not connected. Connect it first.",
            404,
        )

    if conn.sync_status == "syncing":
        raise SyncUpError("ALREADY_SYNCING", "A sync is already in progress.", 409)

    # request.app.state.db is the sessionmaker factory passed to the background
    # task — distinct from the route-scoped `db` session injected via Depends(get_db).
    # Guard against it being absent (e.g. during testing with partial app state).
    if not hasattr(request.app.state, "db"):
        raise SyncUpError("INTERNAL_ERROR", "Database not initialised", 500)

    conn.sync_status = "syncing"
    conn.sync_error = None
    db.commit()

    db_factory: sessionmaker[DbSession] = request.app.state.db
    settings = request.app.state.settings
    background_tasks.add_task(
        _do_sync_generic,
        db_factory,
        user.id,
        service,
        settings.llm_api_key,
        settings.llm_base_url,
        settings.llm_model,
    )

    return SyncTriggeredOut(status="syncing", service=service, poll_url="/api/me")
