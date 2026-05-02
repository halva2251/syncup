"""FastAPI application — entry point for the SyncUp backend."""
from __future__ import annotations

import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

load_dotenv()

from slowapi.errors import RateLimitExceeded  # noqa: E402

from syncup.api.routes.connect import router as connect_router  # noqa: E402
from syncup.api.routes.me import router as me_router  # noqa: E402
from syncup.api.routes.matches import router as matches_router  # noqa: E402
from syncup.api.routes.onboarding import router as onboarding_router  # noqa: E402
from syncup.api.routes.obsessions import router as obsessions_router  # noqa: E402
from syncup.api.routes.dimensions import router as dimensions_router  # noqa: E402
from syncup.api.routes.overrides import router as overrides_router  # noqa: E402
from syncup.api.routes.sync import router as sync_router  # noqa: E402
from syncup.api.routes.taste import router as taste_router  # noqa: E402
from syncup.auth.router import require_auth  # noqa: E402
from syncup.auth.router import router as auth_router  # noqa: E402
from syncup.config import Settings  # noqa: E402
from syncup.db.models import ServiceConnection  # noqa: E402
from syncup.db.session import get_db, sessionmaker_for  # noqa: E402
from syncup.exceptions import SyncUpError  # noqa: E402
from syncup.ingest.crypto import encrypt_token  # noqa: E402
from syncup.ingest.spotify import SpotifyClient  # noqa: E402
from syncup.limiter import limiter  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    """Read CORS allowed origins from env, with safe local-dev fallback."""
    raw = os.environ.get("CORS_ALLOWED_ORIGINS")
    if raw:
        try:
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            logger.warning("Could not parse CORS_ALLOWED_ORIGINS — using defaults")
    return ["http://127.0.0.1:3001", "http://localhost:3001"]


# ---------------------------------------------------------------------------
# Error helpers (SyncUpError lives in syncup.exceptions)
# ---------------------------------------------------------------------------


_HTTP_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
}


def _error_json(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


# ---------------------------------------------------------------------------
# Lifespan — build shared state once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # type: ignore[type-arg]
    settings = Settings()  # type: ignore[call-arg]

    if not settings.debug and not settings.syncup_token_encryption_key:
        raise RuntimeError(
            "SYNCUP_TOKEN_ENCRYPTION_KEY is not set. "
            "Generate one: python -c \"import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )

    app.state.settings = settings
    app.state.db = sessionmaker_for(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
    )
    app.state.limiter = limiter
    app.state.spotify = SpotifyClient(
        client_id=settings.spotify_client_id,
        redirect_uri=settings.spotify_redirect_uri,
    )
    logger.info("SyncUp API started (debug=%s)", settings.debug)
    yield
    app.state.spotify.close()
    logger.info("SyncUp API shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="SyncUp API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers — all errors return { "error": { "code", "message" } }
# ---------------------------------------------------------------------------

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = _error_json("RATE_LIMITED", "Too many requests — please try again later.", 429)
    if hasattr(exc, "headers") and exc.headers:
        response.headers.update(exc.headers)
    return response


@app.exception_handler(SyncUpError)
async def _syncup_error_handler(request: Request, exc: SyncUpError) -> JSONResponse:
    return _error_json(exc.code, exc.message, exc.status_code)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = _HTTP_STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    return _error_json(code, str(exc.detail), exc.status_code)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_json("VALIDATION_ERROR", str(exc.errors()), 422)


@app.exception_handler(Exception)
async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _error_json("INTERNAL_ERROR", "An unexpected error occurred", 500)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@router.get("/auth/spotify")
def spotify_auth_start(request: Request) -> RedirectResponse:
    """Redirect the user to Spotify's authorization page."""
    settings: Settings = request.app.state.settings
    client: SpotifyClient = request.app.state.spotify
    verifier, challenge = client.generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    redirect_url = client.get_authorize_url(state=state, code_challenge=challenge)
    response = RedirectResponse(url=redirect_url)
    _cookie_opts: dict[str, Any] = {
        "httponly": True,
        "samesite": "lax",
        "max_age": 600,
        "secure": not settings.debug,
    }
    response.set_cookie("spotify_state", state, **_cookie_opts)
    response.set_cookie("spotify_verifier", verifier, **_cookie_opts)
    return response


@router.get("/auth/spotify/callback")
def spotify_callback(
    request: Request,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    db: Annotated[DbSession, Depends(get_db)],
) -> RedirectResponse:
    """Complete the Spotify OAuth flow.

    Validates PKCE state, requires an authenticated SyncUp session, exchanges
    the code for tokens, encrypts them, upserts service_connections, and
    redirects to the frontend.  State/PKCE checks happen before auth so that
    a state mismatch returns 400 rather than 401.
    """
    client: SpotifyClient = request.app.state.spotify
    cookie_state = request.cookies.get("spotify_state")
    verifier = request.cookies.get("spotify_verifier")

    if not cookie_state or cookie_state != state:
        raise SyncUpError("OAUTH_STATE_MISMATCH", "OAuth state mismatch")
    if not verifier:
        raise SyncUpError("MISSING_PKCE_VERIFIER", "Missing PKCE verifier")

    # Auth check after PKCE validation so state mismatch errors are still 400.
    user = require_auth(request=request, db=db)

    try:
        tokens = client.exchange_code(code=code, code_verifier=verifier)
        spotify_profile = client.fetch_me(tokens.access_token)
    except httpx.HTTPStatusError as exc:
        logger.warning("Spotify token exchange failed: %s", exc.response.text)
        raise SyncUpError(
            "SPOTIFY_TOKEN_ERROR",
            f"Spotify token exchange failed: {exc.response.text}",
            exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("Could not reach Spotify: %s", exc)
        raise SyncUpError("UPSTREAM_UNAVAILABLE", f"Could not reach Spotify: {exc}", 502) from exc

    spotify_user_id: str | None = spotify_profile.get("id")
    if not spotify_user_id:
        raise SyncUpError("SPOTIFY_PROFILE_INVALID", "Spotify profile missing user id", 502)
    token_expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)
    access_enc = encrypt_token(tokens.access_token)
    refresh_enc = encrypt_token(tokens.refresh_token)

    existing = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.service == "spotify",
        )
    )
    if existing is not None:
        existing.external_user_id = spotify_user_id
        existing.access_token_encrypted = access_enc
        existing.refresh_token_encrypted = refresh_enc
        existing.token_expires_at = token_expires_at
        existing.sync_status = "pending"
        existing.sync_error = None
    else:
        db.add(
            ServiceConnection(
                user_id=user.id,
                service="spotify",
                external_user_id=spotify_user_id,
                access_token_encrypted=access_enc,
                refresh_token_encrypted=refresh_enc,
                token_expires_at=token_expires_at,
                sync_status="pending",
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race condition: two OAuth callbacks fired simultaneously for the same
        # user+service. The first one committed; the connection already exists.
        logger.warning("Spotify upsert race on user %s; connection already exists", user.id)

    logger.info("User %s connected Spotify (external_id=%s)", user.id, spotify_user_id)

    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("spotify_state")
    response.delete_cookie("spotify_verifier")
    return response


app.include_router(router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(connect_router)
app.include_router(sync_router)
app.include_router(taste_router)
app.include_router(obsessions_router)
app.include_router(overrides_router)
app.include_router(dimensions_router)
app.include_router(matches_router)
app.include_router(onboarding_router)
