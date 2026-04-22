"""Application settings loaded from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    spotify_client_id: str
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:3000/api/auth/spotify/callback"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
