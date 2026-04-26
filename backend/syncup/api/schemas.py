"""Shared Pydantic schemas used across API routes."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ServiceConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service: str
    external_user_id: str
    sync_status: str
    last_synced_at: datetime | None
    token_expires_at: datetime | None
    sync_error: str | None
