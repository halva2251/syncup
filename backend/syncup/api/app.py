"""FastAPI application — entry point for the SyncUp backend."""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Any

from dotenv import load_dotenv

load_dotenv()

import httpx  # noqa: E402
from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402

from syncup.config import Settings  # noqa: E402
from syncup.ingest.spotify import SpotifyClient  # noqa: E402

# ---------------------------------------------------------------------------
# Lifespan — build shared clients once at startup
# ---------------------------------------------------------------------------

def _make_spotify_client() -> SpotifyClient:
    settings = Settings()  # type: ignore[call-arg]
    return SpotifyClient(
        client_id=settings.spotify_client_id,
        redirect_uri=settings.spotify_redirect_uri,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # type: ignore[type-arg]
    app.state.spotify = _make_spotify_client()
    yield
    app.state.spotify.close()


app = FastAPI(title="SyncUp API", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/auth/spotify")
def spotify_auth_start(request: Request) -> RedirectResponse:
    """Redirect the user to Spotify's authorization page."""
    client: SpotifyClient = request.app.state.spotify
    verifier, challenge = client.generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    redirect_url = client.get_authorize_url(state=state, code_challenge=challenge)
    response = RedirectResponse(url=redirect_url)
    response.set_cookie("spotify_state", state, httponly=True, samesite="lax", max_age=600)
    response.set_cookie(
        "spotify_verifier", verifier, httponly=True, samesite="lax", max_age=600
    )
    return response


@app.get("/auth/spotify/callback")
def spotify_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> JSONResponse:
    """Exchange the Spotify authorization code for tokens.

    Callers are responsible for storing the returned tokens securely.
    This endpoint is temporary until the full DB session layer lands.
    """
    client: SpotifyClient = request.app.state.spotify
    cookie_state = request.cookies.get("spotify_state")
    verifier = request.cookies.get("spotify_verifier")

    if not cookie_state or cookie_state != state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch")
    if not verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier")

    try:
        tokens = client.exchange_code(code=code, code_verifier=verifier)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Spotify token exchange failed: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Spotify: {exc}") from exc

    response = JSONResponse({"token_type": tokens.token_type, "expires_in": tokens.expires_in})
    response.delete_cookie("spotify_state")
    response.delete_cookie("spotify_verifier")
    return response
