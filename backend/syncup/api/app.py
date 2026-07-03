"""FastAPI application — entry point for the SyncUp backend."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

load_dotenv()

from slowapi.errors import RateLimitExceeded  # noqa: E402

from syncup.api.routes.connect import router as connect_router  # noqa: E402
from syncup.api.routes.connect import spotify_auth_router  # noqa: E402
from syncup.api.routes.dimensions import router as dimensions_router  # noqa: E402
from syncup.api.routes.embeddings import router as embeddings_router  # noqa: E402
from syncup.api.routes.items import router as items_router  # noqa: E402
from syncup.api.routes.matches import _cleanup_stale_match_cache  # noqa: E402
from syncup.api.routes.matches import router as matches_router  # noqa: E402
from syncup.api.routes.me import router as me_router  # noqa: E402
from syncup.api.routes.obsessions import router as obsessions_router  # noqa: E402
from syncup.api.routes.onboarding import router as onboarding_router  # noqa: E402
from syncup.api.routes.overrides import router as overrides_router  # noqa: E402
from syncup.api.routes.recommendations import router as recommendations_router  # noqa: E402
from syncup.api.routes.search import router as search_router  # noqa: E402
from syncup.api.routes.sync import router as sync_router  # noqa: E402
from syncup.api.routes.taste import router as taste_router  # noqa: E402
from syncup.auth.router import router as auth_router  # noqa: E402
from syncup.config import Settings  # noqa: E402
from syncup.db.session import sessionmaker_for  # noqa: E402
from syncup.exceptions import SyncUpError  # noqa: E402
from syncup.ingest.crypto import validate_key  # noqa: E402
from syncup.ingest.registry import close_all as close_all_clients  # noqa: E402
from syncup.ingest.registry import register_default_clients  # noqa: E402
from syncup.ingest.search.registry import close_all as close_all_search_clients  # noqa: E402
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
            parsed = json.loads(raw)
            # json.loads returns Any — a bare string, dict, or list of non-strings
            # is valid JSON but would misbehave deep inside CORSMiddleware at
            # request time; fail loudly at startup instead.
            if not isinstance(parsed, list) or not all(isinstance(o, str) for o in parsed):
                raise ValueError("not a JSON array of strings")
            return parsed
        except (ValueError, json.JSONDecodeError):
            debug = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
            if debug:
                logger.error("Could not parse CORS_ALLOWED_ORIGINS — using defaults (debug mode)")
                return ["http://127.0.0.1:3001", "http://localhost:3001"]
            raise RuntimeError(
                "CORS_ALLOWED_ORIGINS is set but could not be parsed as a JSON array "
                "of strings. Fix the value or remove it to use the default."
            )
    return ["http://127.0.0.1:3001", "http://localhost:3001"]


def _trusted_proxy_hosts() -> list[str]:
    """Read trusted reverse-proxy hosts from env.

    `trusted_hosts="*"` would let any client spoof `X-Forwarded-For` and
    bypass IP-based rate limiting (slowapi keys on `request.client.host`).
    Default to loopback only — the proxy and app run on the same host in our
    deployments; widen via env if a real multi-host setup needs it.
    """
    raw = os.environ.get("TRUSTED_PROXY_HOSTS")
    if raw:
        return [host.strip() for host in raw.split(",") if host.strip()]
    return ["127.0.0.1", "::1"]


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
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings()  # type: ignore[call-arg]

    if not settings.syncup_token_encryption_key:
        raise RuntimeError(
            "SYNCUP_TOKEN_ENCRYPTION_KEY is not set. "
            'Generate one: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"'
        )
    try:
        validate_key()
    except (ValueError, KeyError) as exc:
        raise RuntimeError(f"Invalid SYNCUP_TOKEN_ENCRYPTION_KEY: {exc}") from exc

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
    register_default_clients(settings)

    async def _cleanup_loop() -> None:
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(3600)
            await loop.run_in_executor(None, _cleanup_stale_match_cache, app.state.db)

    cleanup_task = asyncio.create_task(_cleanup_loop())
    logger.info("SyncUp API started (debug=%s)", settings.debug)
    yield
    cleanup_task.cancel()
    app.state.spotify.close()
    close_all_clients()
    close_all_search_clients()
    logger.info("SyncUp API shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="SyncUp API", version="0.1.0", lifespan=lifespan)

# Trust X-Forwarded-For only from known proxy hosts so the rate limiter sees
# the real client IP when running behind nginx / Caddy, without letting
# arbitrary clients spoof their IP and bypass rate limits (see TRUSTED_PROXY_HOSTS).
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware  # noqa: E402

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_trusted_proxy_hosts())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    settings: Settings | None = getattr(request.app.state, "settings", None)
    if settings is not None and not settings.debug and request.url.scheme == "https":
        # ProxyHeadersMiddleware rewrites request.url.scheme from X-Forwarded-Proto
        # for trusted proxies, so this reflects the real client-facing scheme —
        # sending HSTS over plain HTTP would get the directive cached by browsers
        # and could break HTTP access in misconfigured deployments.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    )
    return response


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
    # exc.errors() may contain Python exceptions in ctx fields; round-trip through
    # json.dumps(default=str) to make every value JSON-serializable. Drop "input"
    # — Pydantic v2 echoes the raw submitted value there, which would leak
    # passwords and other sensitive fields back to the client.
    safe_errors = [{k: v for k, v in err.items() if k != "input"} for err in exc.errors()]
    details = json.loads(json.dumps(safe_errors, default=str))
    return JSONResponse(
        {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": details,
            }
        },
        status_code=422,
    )


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
    return {"status": "ok"}


app.include_router(router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(connect_router)
app.include_router(spotify_auth_router)
app.include_router(sync_router)
app.include_router(taste_router)
app.include_router(obsessions_router)
app.include_router(overrides_router)
app.include_router(dimensions_router)
app.include_router(matches_router)
app.include_router(onboarding_router)
app.include_router(embeddings_router)
app.include_router(items_router)
app.include_router(search_router)
app.include_router(recommendations_router)
