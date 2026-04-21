"""Declarative base shared by all ORM models."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root of the ORM hierarchy. All models inherit from this."""

    pass
