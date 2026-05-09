"""Application settings loaded from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    debug: bool = False
    # session_secret is reserved for future signed-cookie or JWT features.
    # Current sessions use a random token stored server-side — no signing needed.
    session_secret: str | None = None

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800  # seconds; 30 min keeps connections alive across idle periods

    # ── Token encryption ─────────────────────────────────────────────────────
    # base64-encoded 32-byte key; generate once per environment:
    # python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    syncup_token_encryption_key: str | None = None

    # ── Spotify ───────────────────────────────────────────────────────────────
    spotify_client_id: str
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:3000/api/auth/spotify/callback"

    # ── Steam ────────────────────────────────────────────────────────────────
    steam_api_key: str = ""

    # ── Last.fm ──────────────────────────────────────────────────────────────
    lastfm_api_key: str = ""
    lastfm_shared_secret: str = ""

    # ── AniList ──────────────────────────────────────────────────────────────
    # Register at https://anilist.co/settings/developer before use.
    anilist_client_id: str | None = None
    anilist_client_secret: str | None = None
    anilist_redirect_uri: str = "http://127.0.0.1:3000/api/connect/anilist/oauth/callback"

    # ── Trakt.tv ─────────────────────────────────────────────────────────────
    # Register at https://trakt.tv/oauth/applications before use.
    trakt_client_id: str | None = None
    trakt_client_secret: str | None = None
    trakt_redirect_uri: str = "http://127.0.0.1:3000/api/connect/trakt/oauth/callback"

    # ── Reddit ───────────────────────────────────────────────────────────────
    # Register at https://www.reddit.com/prefs/apps before use.
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_redirect_uri: str = "http://127.0.0.1:3000/api/connect/reddit/oauth/callback"
    reddit_user_agent: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
