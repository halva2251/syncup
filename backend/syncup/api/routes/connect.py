"""Service connect routes: POST /api/connect/steam, POST /api/connect/lastfm."""
from __future__ import annotations

import logging
import uuid
from typing import Annotated, Self

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from syncup.api.schemas import ServiceConnectionOut
from syncup.auth.router import RequireAuth
from syncup.config import Settings
from syncup.db.models import ServiceConnection
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.ingest.lastfm import LastfmClient
from syncup.ingest.steam import SteamClient
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connect", tags=["connect"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ConnectSteamRequest(BaseModel):
    steam_id: str | None = Field(None, min_length=1)
    vanity_url: str | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        has_id = bool(self.steam_id)
        has_vanity = bool(self.vanity_url)
        if not has_id and not has_vanity:
            raise ValueError("Provide either steam_id or vanity_url")
        if has_id and has_vanity:
            raise ValueError("Provide either steam_id or vanity_url, not both")
        return self


class ConnectLastfmRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Shared upsert helper
# ---------------------------------------------------------------------------


def _upsert_connection(
    db: DbSession,
    user_id: uuid.UUID,
    service: str,
    external_user_id: str,
) -> ServiceConnection:
    """Insert or update a service_connections row and return it."""
    existing = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user_id,
            ServiceConnection.service == service,
        )
    )
    if existing is not None:
        existing.external_user_id = external_user_id
        existing.sync_status = "pending"
        existing.sync_error = None
        conn = existing
    else:
        conn = ServiceConnection(
            user_id=user_id,
            service=service,
            external_user_id=external_user_id,
            sync_status="pending",
        )
        db.add(conn)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race condition: two requests for the same user+service committed
        # simultaneously. The first one won; the connection already exists.
        logger.warning("Upsert race on %s for user %s", service, user_id)

    return conn


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/steam", response_model=ServiceConnectionOut)
@limiter.limit("10/minute")
def connect_steam(
    request: Request,
    body: ConnectSteamRequest,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> ServiceConnectionOut:
    """Connect a Steam account by Steam ID or vanity URL."""
    settings: Settings = request.app.state.settings

    try:
        with SteamClient(api_key=settings.steam_api_key) as steam:
            if body.vanity_url:
                steam_id = steam.resolve_vanity_url(body.vanity_url)
            else:
                steam_id = body.steam_id  # type: ignore[assignment]
            steam.get_player_summary(steam_id)
    except ValueError as exc:
        raise SyncUpError("STEAM_USER_NOT_FOUND", str(exc), 404) from exc
    except httpx.HTTPStatusError as exc:
        raise SyncUpError(
            "UPSTREAM_UNAVAILABLE", f"Steam API error: {exc.response.text}", 502
        ) from exc
    except httpx.RequestError as exc:
        raise SyncUpError("UPSTREAM_UNAVAILABLE", f"Could not reach Steam: {exc}", 502) from exc

    conn = _upsert_connection(db, user.id, "steam", steam_id)
    logger.info("User %s connected Steam (steam_id=%s)", user.id, steam_id)
    return ServiceConnectionOut.model_validate(conn)


@router.post("/lastfm", response_model=ServiceConnectionOut)
@limiter.limit("10/minute")
def connect_lastfm(
    request: Request,
    body: ConnectLastfmRequest,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> ServiceConnectionOut:
    """Connect a Last.fm account by username."""
    settings: Settings = request.app.state.settings

    try:
        with LastfmClient(api_key=settings.lastfm_api_key) as lastfm:
            lastfm.get_top_artists(body.username, limit=1)
    except ValueError as exc:
        raise SyncUpError("LASTFM_USER_NOT_FOUND", str(exc), 404) from exc
    except httpx.HTTPStatusError as exc:
        raise SyncUpError(
            "UPSTREAM_UNAVAILABLE", f"Last.fm API error: {exc.response.text}", 502
        ) from exc
    except httpx.RequestError as exc:
        raise SyncUpError("UPSTREAM_UNAVAILABLE", f"Could not reach Last.fm: {exc}", 502) from exc

    conn = _upsert_connection(db, user.id, "lastfm", body.username)
    logger.info("User %s connected Last.fm (username=%s)", user.id, body.username)
    return ServiceConnectionOut.model_validate(conn)
