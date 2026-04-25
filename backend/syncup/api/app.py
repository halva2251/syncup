"""FastAPI application — entry point for the SyncUp backend."""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRouter

load_dotenv()

from syncup.config import Settings  # noqa: E402
from syncup.ingest.spotify import SpotifyClient  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions + error helpers
# ---------------------------------------------------------------------------

class SyncUpError(Exception):
    """Application-level error with a machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


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
    app.state.settings = settings
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
    allow_origins=["http://127.0.0.1:3001", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers — all errors return { "error": { "code", "message" } }
# ---------------------------------------------------------------------------

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
) -> JSONResponse:
    """Exchange the Spotify authorization code for tokens.

    Temporary endpoint: once the DB session layer lands this will write
    encrypted tokens to service_connections and redirect to the frontend.
    """
    client: SpotifyClient = request.app.state.spotify
    cookie_state = request.cookies.get("spotify_state")
    verifier = request.cookies.get("spotify_verifier")

    if not cookie_state or cookie_state != state:
        raise SyncUpError("OAUTH_STATE_MISMATCH", "OAuth state mismatch")
    if not verifier:
        raise SyncUpError("MISSING_PKCE_VERIFIER", "Missing PKCE verifier")

    try:
        tokens = client.exchange_code(code=code, code_verifier=verifier)
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

    response = JSONResponse({"token_type": tokens.token_type, "expires_in": tokens.expires_in})
    response.delete_cookie("spotify_state")
    response.delete_cookie("spotify_verifier")
    return response


app.include_router(router)
