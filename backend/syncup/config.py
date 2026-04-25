"""Application settings loaded from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    debug: bool = False
    session_secret: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    # JSON list, e.g. '["http://127.0.0.1:3001"]'
    cors_allowed_origins: list[str] = [
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ]

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql://syncup:syncup@localhost:5432/syncup"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800  # seconds; 30 min keeps connections alive across idle periods

    # ── Token encryption ─────────────────────────────────────────────────────
    # base64-encoded 32-byte key; generate once per environment:
    # python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    syncup_token_encryption_key: str = ""

    # ── Spotify ───────────────────────────────────────────────────────────────
    spotify_client_id: str
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:3000/api/auth/spotify/callback"

    # ── Steam ────────────────────────────────────────────────────────────────
    steam_api_key: str = ""

    # ── Last.fm ──────────────────────────────────────────────────────────────
    lastfm_api_key: str = ""
    lastfm_shared_secret: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
