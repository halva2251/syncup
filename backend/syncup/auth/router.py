"""Auth routes: signup, login, logout, and the require_auth dependency."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from syncup.auth.hashing import (
    hash_password,
    needs_rehash,
    verify_password,
    verify_password_dummy,
)
from syncup.config import Settings
from syncup.db.models import Session as SessionRow
from syncup.db.models import User
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SESSION_COOKIE = "syncup_session"
_SESSION_TTL = timedelta(days=30)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("display_name", mode="before")
    @classmethod
    def strip_display_name(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("cannot be blank")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    display_name: str
    avatar_url: str | None
    bio: str | None
    discord_handle: str | None
    languages: list[str] | None
    is_matchable: bool
    onboarded: bool
    created_at: datetime
    updated_at: datetime


class AuthOut(BaseModel):
    """Response wrapper for signup and login — needed for OpenAPI docs since these
    routes return JSONResponse directly to set cookies."""

    user: UserOut


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_session_token(user_id: uuid.UUID, db: DbSession) -> str:
    """Insert a new session row and return its token."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + _SESSION_TTL
    db.add(SessionRow(token=token, user_id=user_id, expires_at=expires_at))
    return token


def _set_session_cookie(response: Response, token: str, *, debug: bool) -> None:
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=int(_SESSION_TTL.total_seconds()),
        secure=not debug,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/signup", status_code=201, response_model=AuthOut)
@limiter.limit("5/minute")
def signup(
    request: Request,
    body: SignupRequest,
    db: Annotated[DbSession, Depends(get_db)],
) -> JSONResponse:
    """Create a new account and set a session cookie."""
    existing = db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        verify_password_dummy(body.password)  # constant-time: don't reveal email existence
        raise SyncUpError("EMAIL_TAKEN", "An account with that email already exists", 409)

    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        is_matchable=False,
        onboarded=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()

    token = _make_session_token(user.id, db)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Race condition: another request beat us to the same email between
        # our pre-check and the INSERT.
        raise SyncUpError("EMAIL_TAKEN", "An account with that email already exists", 409) from exc

    logger.info("New user signed up: %s", user.id)

    settings = request.app.state.settings
    user_data = UserOut.model_validate(user).model_dump(mode="json")
    response = JSONResponse({"user": user_data}, status_code=201)
    response.headers["Location"] = "/api/me"
    _set_session_cookie(response, token, debug=settings.debug)
    return response


@router.post("/login", response_model=AuthOut)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    db: Annotated[DbSession, Depends(get_db)],
) -> JSONResponse:
    """Verify credentials and set a session cookie."""
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        verify_password_dummy(body.password)  # constant-time: don't reveal email existence
        raise SyncUpError("INVALID_CREDENTIALS", "Invalid email or password", 401)

    if not verify_password(user.password_hash or "", body.password):
        raise SyncUpError("INVALID_CREDENTIALS", "Invalid email or password", 401)

    if needs_rehash(user.password_hash or ""):
        user.password_hash = hash_password(body.password)

    token = _make_session_token(user.id, db)
    db.commit()

    logger.info("User logged in: %s", user.id)

    settings = request.app.state.settings
    user_data = UserOut.model_validate(user).model_dump(mode="json")
    response = JSONResponse({"user": user_data})
    _set_session_cookie(response, token, debug=settings.debug)
    return response


@router.post("/logout", status_code=204)
@limiter.limit("30/minute")
def logout(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
) -> Response:
    """Invalidate the current session. Always returns 204 — no auth required."""
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        session = db.get(SessionRow, token)
        if session:
            db.delete(session)
            db.commit()

    settings: Settings = request.app.state.settings
    response = Response(status_code=204)
    response.delete_cookie(
        _SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        path="/",
    )
    return response


# ---------------------------------------------------------------------------
# Auth dependency — use as: user: RequireAuth
# ---------------------------------------------------------------------------


def require_auth(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
) -> User:
    """FastAPI dependency: return the current user or raise 401.

    Usage::

        from syncup.auth import RequireAuth

        @router.get("/me")
        def get_me(user: RequireAuth) -> ...:
            ...
    """
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        raise SyncUpError("UNAUTHORIZED", "Authentication required", 401)

    user = db.execute(
        select(User)
        .join(SessionRow, SessionRow.user_id == User.id)
        .where(
            and_(
                SessionRow.token == token,
                SessionRow.expires_at >= datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()

    if user is None:
        raise SyncUpError("UNAUTHORIZED", "Session expired or invalid", 401)

    return user


RequireAuth = Annotated[User, Depends(require_auth)]
