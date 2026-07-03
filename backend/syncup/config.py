"""Application settings loaded from environment variables."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import field_validator
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
    steam_openid_return_to: str = "http://127.0.0.1:3000/api/connect/steam/openid/callback"
    steam_openid_realm: str = "http://127.0.0.1:3000"

    # ── Last.fm ──────────────────────────────────────────────────────────────
    # Public-data methods (by username) only need an API key. The shared secret
    # is required for the optional web-auth flow. See docs/api-keys.md.
    lastfm_api_key: str = ""
    lastfm_shared_secret: str = ""
    lastfm_redirect_uri: str = "http://127.0.0.1:3000/api/connect/lastfm/oauth/callback"

    # ── Post-auth redirect ───────────────────────────────────────────────────
    # URL to send users after OAuth/web-auth/OpenID callbacks.
    # In dev, this should be the frontend origin (e.g. http://127.0.0.1:3001).
    frontend_url: str = "http://127.0.0.1:3001"

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

    # ── Phase 2 ML ───────────────────────────────────────────────────────────
    # Sentence-transformers model used for semantic item embeddings.
    # all-MiniLM-L6-v2 outputs 384-dim vectors; must match EMBEDDING_DIM.
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # LLM settings for vibe synthesis. Optional — if llm_api_key is unset,
    # vibe synthesis is skipped and the taste card shows items only.
    # Defaults to DeepSeek (OpenAI-compatible). Point llm_base_url at any
    # OpenAI-compatible provider (e.g. "https://api.openai.com" for GPT).
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # TMDB API key for film/show genre enrichment and autocomplete. Optional —
    # if unset, films/shows embed with name+year only and autocomplete for
    # those categories returns empty results.
    tmdb_api_key: str | None = None

    # MusicBrainz requires a custom User-Agent header. No API key required.
    # Format: "AppName/Version (ContactEmail or URL)"
    musicbrainz_user_agent: str = "SyncUp/0.1.0"

    # Google Books API key. Optional — if set, book autocomplete uses Google
    # Books (much faster); otherwise falls back to Open Library.
    google_books_api_key: str | None = None

    @field_validator("frontend_url", mode="before")
    @classmethod
    def validate_frontend_url(cls, v: object) -> str:
        if v is None or v == "":
            return "http://127.0.0.1:3001"
        if not isinstance(v, str):
            raise ValueError("FRONTEND_URL must be a string")
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("FRONTEND_URL must be an absolute http(s) URL")
        return v.rstrip("/")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
