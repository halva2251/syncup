"""Service connect routes: POST /api/connect/steam, POST /api/connect/lastfm,
POST /api/connect/letterboxd/import, GET /api/connect/anilist/oauth/*."""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Self

import httpx
from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from syncup.api.schemas import ServiceConnectionOut
from syncup.auth.router import RequireAuth, require_auth
from syncup.config import Settings
from syncup.db.models import Item, ServiceConnection, UserItem
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.ingest.anilist import AniListClient
from syncup.ingest.crypto import encrypt_token
from syncup.ingest.lastfm import LastfmClient
from syncup.ingest.protocol import SyncClientError
from syncup.ingest.steam import SteamClient
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connect", tags=["connect"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ConnectSteamRequest(BaseModel):
    steam_id: str | None = Field(None, min_length=1, max_length=100)
    vanity_url: str | None = Field(None, min_length=1, max_length=100)

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
        # simultaneously. The first one won; re-query to return a live object.
        logger.warning("Upsert race on %s for user %s", service, user_id)
        conn = db.scalar(
            select(ServiceConnection).where(
                ServiceConnection.user_id == user_id,
                ServiceConnection.service == service,
            )
        )

    return conn  # type: ignore[return-value]


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
    except (SyncClientError, ValueError) as exc:
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
    except (SyncClientError, ValueError) as exc:
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


# ---------------------------------------------------------------------------
# Letterboxd — CSV diary import
# ---------------------------------------------------------------------------

_LETTERBOXD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

_ITEMS_TABLE = Item.__table__
_USER_ITEMS_TABLE = UserItem.__table__


class LetterboxdImportOut(BaseModel):
    imported: int


@router.post("/letterboxd/import", response_model=LetterboxdImportOut, status_code=201)
@limiter.limit("10/minute")
def import_letterboxd(
    request: Request,
    file: UploadFile,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> LetterboxdImportOut:
    """Import a Letterboxd diary CSV export — wipe-and-replace transaction."""
    # content_type is client-supplied and easily spoofed, so this is a UX
    # signal for catching wrong file types by accident, not a security gate.
    # We include octet-stream because many browsers send it for .csv files.
    allowed_content_types = {"text/csv", "text/plain", "application/octet-stream"}
    if file.content_type and file.content_type not in allowed_content_types:
        raise SyncUpError(
            "INVALID_FILE_TYPE",
            f"Expected a CSV file, got {file.content_type!r}",
            422,
        )

    data = file.file.read(_LETTERBOXD_MAX_BYTES + 1)
    if len(data) > _LETTERBOXD_MAX_BYTES:
        raise SyncUpError("FILE_TOO_LARGE", "File must be 10 MB or smaller", 413)

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyncUpError("INVALID_CSV", "File must be UTF-8 encoded", 422) from exc

    from syncup.ingest.letterboxd import LetterboxdClient

    client = LetterboxdClient()
    try:
        raw_items = client.parse_csv(text)
    except SyncClientError as exc:
        raise SyncUpError("INVALID_CSV", str(exc), 422) from exc

    # Wipe-and-replace in a single transaction:
    # 1. Delete existing letterboxd user_items for this user.
    # 2. Upsert each item into the canonical catalog and user_items.
    # 3. Upsert the service_connections row with sync_status="ok".
    # 4. Commit — rollback on any failure preserves the old data.

    db.execute(
        delete(_USER_ITEMS_TABLE)
        .where(_USER_ITEMS_TABLE.c.user_id == user.id)
        .where(
            _USER_ITEMS_TABLE.c.item_id.in_(
                select(_ITEMS_TABLE.c.id).where(_ITEMS_TABLE.c.service == "letterboxd")
            )
        )
    )

    now = datetime.now(UTC)
    for raw_item in raw_items:
        ins_item = pg_insert(_ITEMS_TABLE).values(
            id=uuid.uuid4(),
            service="letterboxd",
            item_type=raw_item["item_type"],
            external_id=raw_item["external_id"],
            name=raw_item["name"],
            metadata=raw_item["metadata"],
        )
        item_id: uuid.UUID = db.execute(
            ins_item.on_conflict_do_update(
                index_elements=["service", "item_type", "external_id"],
                set_={
                    "name": ins_item.excluded.name,
                    "metadata": ins_item.excluded.metadata,
                },
            ).returning(_ITEMS_TABLE.c.id)
        ).scalar_one()

        ins_ui = pg_insert(_USER_ITEMS_TABLE).values(
            id=uuid.uuid4(),
            user_id=user.id,
            item_id=item_id,
            engagement_score=raw_item["engagement_score"],
            raw_value=raw_item["raw_value"],
            raw_type=raw_item["raw_type"],
            last_engaged_at=raw_item["last_engaged_at"],
            fetched_at=now,
        )
        db.execute(
            ins_ui.on_conflict_do_update(
                index_elements=["user_id", "item_id"],
                set_={
                    "engagement_score": ins_ui.excluded.engagement_score,
                    "raw_value": ins_ui.excluded.raw_value,
                    "raw_type": ins_ui.excluded.raw_type,
                    "last_engaged_at": ins_ui.excluded.last_engaged_at,
                    "fetched_at": ins_ui.excluded.fetched_at,
                },
            )
        )

    # Upsert connection row — set directly to "ok" (no intermediate sync step).
    existing_conn = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.service == "letterboxd",
        )
    )
    if existing_conn is not None:
        existing_conn.sync_status = "ok"
        existing_conn.sync_error = None
    else:
        db.add(
            ServiceConnection(
                user_id=user.id,
                service="letterboxd",
                external_user_id=str(user.id),
                sync_status="ok",
            )
        )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Letterboxd import failed for user %s", user.id)
        raise SyncUpError("IMPORT_FAILED", "Import failed — please retry", 500) from exc

    logger.info("User %s imported %d Letterboxd films", user.id, len(raw_items))
    return LetterboxdImportOut(imported=len(raw_items))


# ---------------------------------------------------------------------------
# AniList — OAuth 2.0 authorization code flow
# ---------------------------------------------------------------------------

_ANILIST_STATE_COOKIE = "anilist_state"


def _anilist_client(settings: Settings) -> AniListClient:
    """Instantiate AniListClient from settings.

    Raises SyncUpError(503) if AniList credentials are not configured.
    """
    if not settings.anilist_client_id or not settings.anilist_client_secret:
        raise SyncUpError(
            "SERVICE_NOT_CONFIGURED",
            "AniList OAuth is not configured — set ANILIST_CLIENT_ID and ANILIST_CLIENT_SECRET",
            503,
        )
    return AniListClient(
        client_id=settings.anilist_client_id,
        client_secret=settings.anilist_client_secret,
        redirect_uri=settings.anilist_redirect_uri,
    )


@router.get("/anilist/oauth/start")
@limiter.limit("10/minute")
def anilist_oauth_start(
    request: Request,
    user: RequireAuth,
) -> RedirectResponse:
    """Redirect the user to AniList's authorization page."""
    settings: Settings = request.app.state.settings
    client = _anilist_client(settings)

    state = secrets.token_urlsafe(16)
    url = client.get_authorize_url(state=state)

    _cookie_opts: dict[str, Any] = {
        "httponly": True,
        "samesite": "lax",
        "max_age": 600,
        "secure": not settings.debug,
    }
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(_ANILIST_STATE_COOKIE, state, **_cookie_opts)
    return response


@router.get("/anilist/oauth/callback")
@limiter.limit("10/minute")
def anilist_oauth_callback(
    request: Request,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    db: Annotated[DbSession, Depends(get_db)],
) -> RedirectResponse:
    """Complete the AniList OAuth flow.

    State validation runs before auth so a state mismatch returns 400, not 401,
    matching the Spotify callback pattern.
    """
    # State check FIRST — keeps error semantics clean (400 vs 401).
    cookie_state = request.cookies.get(_ANILIST_STATE_COOKIE)
    if not cookie_state or cookie_state != state:
        raise SyncUpError("OAUTH_STATE_MISMATCH", "OAuth state mismatch", 400)

    user = require_auth(request=request, db=db)

    settings: Settings = request.app.state.settings
    with _anilist_client(settings) as client:
        try:
            tokens = client.exchange_code(code)
            me = client.fetch_me(tokens.access_token)
        except SyncClientError as exc:
            raise SyncUpError("ANILIST_TOKEN_ERROR", str(exc), 400) from exc
        except httpx.HTTPStatusError as exc:
            raise SyncUpError(
                "ANILIST_TOKEN_ERROR",
                f"AniList token exchange failed: {exc.response.text}",
                exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise SyncUpError(
                "UPSTREAM_UNAVAILABLE", f"Could not reach AniList: {exc}", 502
            ) from exc

    anilist_user_id = str(me.get("id") or "")
    if not anilist_user_id:
        raise SyncUpError("ANILIST_PROFILE_INVALID", "AniList profile missing user id", 502)

    access_enc = encrypt_token(tokens.access_token)
    refresh_enc = encrypt_token(tokens.refresh_token) if tokens.refresh_token else None

    existing = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.service == "anilist",
        )
    )
    if existing is not None:
        existing.external_user_id = anilist_user_id
        existing.access_token_encrypted = access_enc
        existing.refresh_token_encrypted = refresh_enc
        existing.token_expires_at = tokens.expires_at
        existing.sync_status = "pending"
        existing.sync_error = None
    else:
        db.add(
            ServiceConnection(
                user_id=user.id,
                service="anilist",
                external_user_id=anilist_user_id,
                access_token_encrypted=access_enc,
                refresh_token_encrypted=refresh_enc,
                token_expires_at=tokens.expires_at,
                sync_status="pending",
            )
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("AniList upsert race on user %s; connection already exists", user.id)

    logger.info("User %s connected AniList (anilist_id=%s)", user.id, anilist_user_id)

    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(_ANILIST_STATE_COOKIE)
    return response
