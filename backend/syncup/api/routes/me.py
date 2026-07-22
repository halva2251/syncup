"""GET/PATCH /api/me and service-connection management."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from pydantic import BaseModel, Field, StrictBool, field_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from syncup.api.schemas import ServiceConnectionOut
from syncup.auth.router import RequireAuth, UserOut
from syncup.constants.languages import (
    MAX_LANGUAGE_CODE_LENGTH,
    MAX_LANGUAGES,
    SUPPORTED_LANGUAGE_CODES,
)
from syncup.db.models import Item, MatchCache, ServiceConnection, UserEmbedding, UserItem
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter
from syncup.profile_links import normalize_social_links

router = APIRouter(prefix="/api", tags=["users"])

_AVATAR_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _sniff_image_type(data: bytes) -> str | None:
    """Return the image content type matching the magic bytes, or None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class MeOut(BaseModel):
    user: UserOut
    connections: list[ServiceConnectionOut]


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = Field(default=None, max_length=500)
    discord_handle: str | None = Field(default=None, max_length=100)
    social_links: dict[str, str] | None = None
    avatar_url: str | None = Field(default=None, max_length=500)
    is_matchable: StrictBool | None = None
    languages: list[str] | None = None

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
            if v.startswith("/uploads/"):
                return v
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("must be an http(s) URL")
        return v

    @field_validator("social_links", mode="before")
    @classmethod
    def validate_social_links(cls, v: object) -> object:
        if v is None:
            return v
        return normalize_social_links(v)

    @field_validator("languages", mode="before")
    @classmethod
    def validate_languages(cls, v: object) -> object:
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("languages must be a list")
        seen: set[str] = set()
        for code in v:
            if not isinstance(code, str):
                raise ValueError("each language must be a string code")
            code = code.strip().lower()
            if not code:
                raise ValueError("language code cannot be blank")
            if len(code) > MAX_LANGUAGE_CODE_LENGTH:
                raise ValueError("invalid language code")
            if code not in SUPPORTED_LANGUAGE_CODES:
                raise ValueError(f"unsupported language code: {code}")
            seen.add(code)
        if len(seen) > MAX_LANGUAGES:
            raise ValueError(f"at most {MAX_LANGUAGES} languages allowed")
        return sorted(seen)


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


@router.delete("/me/connections/{service}", status_code=204)
@limiter.limit("30/minute")
def delete_connection(
    service: str,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> None:
    """Disconnect a service and remove its pulled data for the current user."""
    connection = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.service == service,
        )
    )
    if connection is None:
        raise SyncUpError("NOT_FOUND", "Service connection not found", 404)

    try:
        # Items are shared across users, so only remove this user's pulled
        # associations. The canonical catalog remains available to other users.
        db.execute(
            delete(UserItem).where(
                UserItem.user_id == user.id,
                UserItem.item_id.in_(select(Item.id).where(Item.service == service)),
            )
        )

        # Embeddings and the synthesized profile are derived from all services;
        # invalidate them so a later recompute cannot use disconnected data.
        db.execute(delete(UserEmbedding).where(UserEmbedding.user_id == user.id))
        # Cached compatibility scores and highlights may include the disconnected
        # service, so they must not remain visible until their normal expiry.
        db.execute(
            delete(MatchCache).where(
                or_(MatchCache.user_a_id == user.id, MatchCache.user_b_id == user.id)
            )
        )
        user.vibe_summary = None
        user.archetype = None
        user.key_themes = None
        user.vibe_computed_at = None

        db.delete(connection)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise SyncUpError("INTERNAL_ERROR", "Failed to disconnect service", 500) from exc


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
    if "social_links" in fields:
        user.social_links = body.social_links or {}
    if "avatar_url" in fields:
        user.avatar_url = body.avatar_url
    if "is_matchable" in fields and body.is_matchable is not None:
        user.is_matchable = body.is_matchable
        if not body.is_matchable:
            # Cached rows are otherwise served to every existing match for up to
            # 24 hours, even after this user opts out of discoverability.
            db.execute(
                delete(MatchCache).where(
                    or_(MatchCache.user_a_id == user.id, MatchCache.user_b_id == user.id)
                )
            )
    if "languages" in fields:
        user.languages = body.languages

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/me/avatar", response_model=UserOut)
@limiter.limit("10/minute")
def upload_avatar(
    request: Request,
    file: UploadFile,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> UserOut:
    """Upload a profile photo. Stores it locally and sets avatar_url to its path."""
    settings = request.app.state.settings

    # Content type is a UX hint; the magic-byte check below is the real gate.
    if file.content_type and file.content_type not in _AVATAR_CONTENT_TYPES:
        raise SyncUpError(
            "INVALID_FILE_TYPE",
            f"Expected a PNG, JPEG, WebP, or GIF image, got {file.content_type!r}",
            422,
        )

    data = file.file.read(settings.avatar_max_bytes + 1)
    if len(data) > settings.avatar_max_bytes:
        raise SyncUpError(
            "FILE_TOO_LARGE",
            f"Image must be {settings.avatar_max_bytes // (1024 * 1024)} MB or smaller",
            413,
        )

    detected = _sniff_image_type(data)
    if detected is None:
        raise SyncUpError(
            "INVALID_FILE_TYPE",
            "File does not look like a PNG, JPEG, WebP, or GIF image",
            422,
        )

    upload_root = Path(settings.upload_dir)
    avatar_dir = upload_root / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{_AVATAR_CONTENT_TYPES[detected]}"
    (avatar_dir / filename).write_bytes(data)

    # Best-effort cleanup of a previous locally-stored avatar.
    if user.avatar_url and user.avatar_url.startswith("/uploads/"):
        old = upload_root / user.avatar_url.removeprefix("/uploads/")
        try:
            if old.is_file() and old.resolve().is_relative_to(upload_root.resolve()):
                old.unlink()
        except OSError:
            pass

    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
