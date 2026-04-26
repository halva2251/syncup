"""Sync routes: POST /api/sync/{service} — trigger background data pull."""
from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from syncup.auth.router import RequireAuth
from syncup.config import Settings
from syncup.db.models import Item, ServiceConnection, UserItem
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.ingest.crypto import decrypt_token, encrypt_token
from syncup.ingest.lastfm import LastfmClient
from syncup.ingest.spotify import SpotifyClient
from syncup.ingest.steam import SteamClient
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_VALID_SERVICES = frozenset({"spotify", "steam", "lastfm"})
_TOKEN_REFRESH_BUFFER = timedelta(seconds=60)

# API fetch limits — centralised so they're easy to tune
_SPOTIFY_TOP_LIMIT = 50
_SPOTIFY_TIME_RANGE = "medium_term"
_SPOTIFY_RECENT_LIMIT = 50
_LASTFM_TOP_LIMIT = 50
_LASTFM_PERIOD = "overall"

_ITEMS_TABLE = Item.__table__
_USER_ITEMS_TABLE = UserItem.__table__

_SyncTask = Callable[[sessionmaker[DbSession], Settings, uuid.UUID], None]


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
    last_engaged_at: datetime | None = None,
) -> None:
    now = datetime.now(UTC)
    ins = pg_insert(_USER_ITEMS_TABLE).values(  # type: ignore[arg-type]
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        engagement_score=engagement_score,
        raw_value=raw_value,
        last_engaged_at=last_engaged_at,
        fetched_at=now,
    )
    db.execute(
        ins.on_conflict_do_update(
            index_elements=["user_id", "item_id"],
            set_={
                "engagement_score": ins.excluded.engagement_score,
                "raw_value": ins.excluded.raw_value,
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
    if isinstance(exc, ValueError):
        return str(exc)  # Our own ValueError messages are intentionally safe
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
# Per-service background task functions
# ---------------------------------------------------------------------------


def _do_sync_spotify(
    db_factory: sessionmaker[DbSession],
    settings: Settings,
    user_id: uuid.UUID,
) -> None:
    session = db_factory()
    try:
        conn = session.scalar(
            select(ServiceConnection).where(
                ServiceConnection.user_id == user_id,
                ServiceConnection.service == "spotify",
            )
        )
        if conn is None:
            return

        # Refresh token if expired or within the buffer window
        now = datetime.now(UTC)
        if (
            conn.token_expires_at is not None
            and conn.token_expires_at <= now + _TOKEN_REFRESH_BUFFER
        ):
            if conn.refresh_token_encrypted is None:
                raise ValueError("Missing refresh token — reconnect Spotify via OAuth")
            with SpotifyClient(
                client_id=settings.spotify_client_id,
                redirect_uri=settings.spotify_redirect_uri,
            ) as client:
                old_refresh = decrypt_token(conn.refresh_token_encrypted)
                new_tokens = client.refresh_access_token(old_refresh)
            conn.access_token_encrypted = encrypt_token(new_tokens.access_token)
            conn.refresh_token_encrypted = encrypt_token(new_tokens.refresh_token)
            conn.token_expires_at = now + timedelta(seconds=new_tokens.expires_in)
            session.flush()
            access_token = new_tokens.access_token
        else:
            if conn.access_token_encrypted is None:
                raise ValueError("Missing access token — reconnect Spotify via OAuth")
            access_token = decrypt_token(conn.access_token_encrypted)

        with SpotifyClient(
            client_id=settings.spotify_client_id,
            redirect_uri=settings.spotify_redirect_uri,
        ) as client:
            top_artists = client.fetch_top_artists(
                access_token, limit=_SPOTIFY_TOP_LIMIT, time_range=_SPOTIFY_TIME_RANGE
            )
            recently_played = client.fetch_recently_played(
                access_token, limit=_SPOTIFY_RECENT_LIMIT
            )

        items_synced = 0
        n_artists = len(top_artists)

        for i, artist in enumerate(top_artists):
            item_id = _upsert_item(
                session,
                "spotify",
                "artist",
                artist["id"],
                artist["name"],
                {"genres": artist.get("genres", [])},
            )
            # Rank 1 → 1.0, rank N → 1/N (normalised 0–1)
            score = (n_artists - i) / n_artists if n_artists else 0.0
            _upsert_user_item(session, user_id, item_id, score, float(n_artists - i))
            items_synced += 1

        # Aggregate recently-played: count occurrences + capture most-recent timestamp
        track_occurrences: dict[str, dict[str, Any]] = {}
        for event in recently_played:
            track = event["track"]
            tid = track["id"]
            if tid not in track_occurrences:
                track_occurrences[tid] = {
                    "name": track["name"],
                    "artists": [a["name"] for a in track.get("artists", [])],
                    "count": 0,
                    "played_at": event.get("played_at"),  # newest occurrence first
                }
            track_occurrences[tid]["count"] += 1

        max_count = max((info["count"] for info in track_occurrences.values()), default=1) or 1

        for tid, info in track_occurrences.items():
            item_id = _upsert_item(
                session,
                "spotify",
                "track",
                tid,
                info["name"],
                {"artists": info["artists"]},
            )
            count_raw = float(info["count"])
            score = count_raw / max_count
            last_engaged_at: datetime | None = None
            if info["played_at"]:
                try:
                    last_engaged_at = datetime.fromisoformat(info["played_at"])
                except (ValueError, TypeError):
                    pass
            _upsert_user_item(
                session, user_id, item_id, score, count_raw, last_engaged_at=last_engaged_at
            )
            items_synced += 1

        conn.sync_status = "ok"
        conn.last_synced_at = datetime.now(UTC)
        conn.sync_error = None
        session.commit()
        logger.info("Spotify sync done for user %s: %d items", user_id, items_synced)

    except Exception as exc:
        logger.exception("Spotify sync failed for user %s", user_id)
        session.rollback()
        _set_sync_error(session, user_id, "spotify", _safe_error_message(exc))

    finally:
        session.close()


def _do_sync_steam(
    db_factory: sessionmaker[DbSession],
    settings: Settings,
    user_id: uuid.UUID,
) -> None:
    session = db_factory()
    try:
        conn = session.scalar(
            select(ServiceConnection).where(
                ServiceConnection.user_id == user_id,
                ServiceConnection.service == "steam",
            )
        )
        if conn is None:
            return

        steam_id = conn.external_user_id

        with SteamClient(api_key=settings.steam_api_key) as steam:
            games = steam.get_owned_games(steam_id)

        max_playtime = (
            max((g.get("playtime_forever", 0) for g in games), default=1) or 1
        )

        items_synced = 0
        for game in games:
            appid = str(game["appid"])
            name = game.get("name", f"App {appid}")
            playtime = float(game.get("playtime_forever", 0))
            score = playtime / max_playtime

            rtime = game.get("rtime_last_played")
            last_engaged_at = (
                datetime.fromtimestamp(rtime, tz=UTC) if rtime else None
            )

            item_id = _upsert_item(
                session,
                "steam",
                "game",
                appid,
                name,
                {"img_icon_url": game.get("img_icon_url", "")},
            )
            _upsert_user_item(
                session, user_id, item_id, score, playtime, last_engaged_at=last_engaged_at
            )
            items_synced += 1

        conn.sync_status = "ok"
        conn.last_synced_at = datetime.now(UTC)
        conn.sync_error = None
        session.commit()
        logger.info("Steam sync done for user %s: %d games", user_id, items_synced)

    except Exception as exc:
        logger.exception("Steam sync failed for user %s", user_id)
        session.rollback()
        _set_sync_error(session, user_id, "steam", _safe_error_message(exc))

    finally:
        session.close()


def _do_sync_lastfm(
    db_factory: sessionmaker[DbSession],
    settings: Settings,
    user_id: uuid.UUID,
) -> None:
    session = db_factory()
    try:
        conn = session.scalar(
            select(ServiceConnection).where(
                ServiceConnection.user_id == user_id,
                ServiceConnection.service == "lastfm",
            )
        )
        if conn is None:
            return

        username = conn.external_user_id

        with LastfmClient(api_key=settings.lastfm_api_key) as lastfm:
            top_artists = lastfm.get_top_artists(
                username, limit=_LASTFM_TOP_LIMIT, period=_LASTFM_PERIOD
            )
            top_tracks = lastfm.get_top_tracks(
                username, limit=_LASTFM_TOP_LIMIT, period=_LASTFM_PERIOD
            )

        max_artist_plays = (
            max((float(a.get("playcount", 0)) for a in top_artists), default=1.0) or 1.0
        )
        max_track_plays = (
            max((float(t.get("playcount", 0)) for t in top_tracks), default=1.0) or 1.0
        )

        items_synced = 0

        for artist in top_artists:
            external_id = artist.get("mbid") or artist["name"]
            playcount = float(artist.get("playcount", 0))
            score = playcount / max_artist_plays
            item_id = _upsert_item(
                session, "lastfm", "artist", external_id, artist["name"], {}
            )
            _upsert_user_item(session, user_id, item_id, score, playcount)
            items_synced += 1

        for track in top_tracks:
            artist_name = track.get("artist", {}).get("name", "")
            external_id = track.get("mbid") or f"{track['name']}::{artist_name}"
            playcount = float(track.get("playcount", 0))
            score = playcount / max_track_plays
            item_id = _upsert_item(
                session,
                "lastfm",
                "track",
                external_id,
                track["name"],
                {"artist": artist_name},
            )
            _upsert_user_item(session, user_id, item_id, score, playcount)
            items_synced += 1

        conn.sync_status = "ok"
        conn.last_synced_at = datetime.now(UTC)
        conn.sync_error = None
        session.commit()
        logger.info("Last.fm sync done for user %s: %d items", user_id, items_synced)

    except Exception as exc:
        logger.exception("Last.fm sync failed for user %s", user_id)
        session.rollback()
        _set_sync_error(session, user_id, "lastfm", _safe_error_message(exc))

    finally:
        session.close()


_SYNC_TASKS: dict[str, _SyncTask] = {
    "spotify": _do_sync_spotify,
    "steam": _do_sync_steam,
    "lastfm": _do_sync_lastfm,
}


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
    if service not in _VALID_SERVICES:
        raise SyncUpError("INVALID_SERVICE", f"Unknown service: {service!r}", 400)

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
    settings: Settings = request.app.state.settings
    background_tasks.add_task(_SYNC_TASKS[service], db_factory, settings, user.id)

    return SyncTriggeredOut(status="syncing", service=service)
