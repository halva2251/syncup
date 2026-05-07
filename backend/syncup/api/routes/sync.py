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
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, ServiceConnection, UserItem
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.ingest.crypto import encrypt_token
from syncup.ingest.protocol import SyncClientError
from syncup.ingest.registry import get_client
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_ITEMS_TABLE = Item.__table__
_USER_ITEMS_TABLE = UserItem.__table__


class SyncTriggeredOut(BaseModel):
    status: Literal["syncing"]
    service: str


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


def _set_sync_error(
    session: DbSession, user_id: uuid.UUID, service: str, error: str
) -> None:
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
    except Exception:
        session.rollback()
        logger.exception(
            "Failed to write sync error status for user %s / %s", user_id, service
        )


# ---------------------------------------------------------------------------
# Generic background sync task
# ---------------------------------------------------------------------------


def _do_sync_generic(
    db_factory: sessionmaker[DbSession],
    user_id: uuid.UUID,
    service: str,
) -> None:
    session = db_factory()
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
                raw_item["engagement_score"],
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

    except Exception as exc:
        logger.exception("%s sync failed for user %s", service, user_id)
        session.rollback()
        _set_sync_error(session, user_id, service, _safe_error_message(exc))

    finally:
        session.close()


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

    conn.sync_status = "syncing"
    conn.sync_error = None
    db.commit()

    db_factory: sessionmaker[DbSession] = request.app.state.db
    background_tasks.add_task(_do_sync_generic, db_factory, user.id, service)

    return SyncTriggeredOut(status="syncing", service=service)
