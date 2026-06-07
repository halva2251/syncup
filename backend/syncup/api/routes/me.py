"""GET/PATCH /api/me — current user profile and service connections."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StrictBool, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from syncup.api.schemas import ServiceConnectionOut
from syncup.auth.router import RequireAuth, UserOut
from syncup.db.models import ServiceConnection
from syncup.db.session import get_db
from syncup.limiter import limiter

router = APIRouter(prefix="/api", tags=["users"])


class MeOut(BaseModel):
    user: UserOut
    connections: list[ServiceConnectionOut]


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = Field(default=None, max_length=500)
    discord_handle: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    is_matchable: StrictBool | None = None

    @field_validator("display_name", "bio", "discord_handle", mode="before")
    @classmethod
    def strip_and_validate(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("cannot be blank")
        return v

    @field_validator("avatar_url", mode="before")
    @classmethod
    def validate_avatar_url(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("must be an http(s) URL")
        return v


@router.get("/me", response_model=MeOut)
@limiter.limit("60/minute")
def get_me(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> MeOut:
    """Return the authenticated user's profile and service connection statuses."""
    connections = db.scalars(
        select(ServiceConnection).where(ServiceConnection.user_id == user.id)
    ).all()

    return MeOut(
        user=UserOut.model_validate(user),
        connections=[ServiceConnectionOut.model_validate(c) for c in connections],
    )


@router.patch("/me", response_model=UserOut)
@limiter.limit("30/minute")
def patch_me(
    body: ProfilePatch,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> UserOut:
    """Partially update the authenticated user's profile."""
    fields = body.model_fields_set

    if "display_name" in fields and body.display_name is not None:
        user.display_name = body.display_name
    if "bio" in fields:
        user.bio = body.bio
    if "discord_handle" in fields:
        user.discord_handle = body.discord_handle
    if "avatar_url" in fields:
        user.avatar_url = body.avatar_url
    if "is_matchable" in fields and body.is_matchable is not None:
        user.is_matchable = body.is_matchable

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
