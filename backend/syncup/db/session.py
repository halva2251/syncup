"""Engine + session factory for the application DB.

We expose a helper to construct a sessionmaker and a small generator
dependency for request-scoped sessions. The FastAPI layer will wire
this in when routes land.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def sessionmaker_for(database_url: str) -> sessionmaker[Session]:
    """Build a sessionmaker bound to a fresh engine for the given URL."""
    engine: Engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and ensure it is closed when the caller is done.

    Intended to be wrapped as a FastAPI dependency once routes exist.
    """
    session = factory()
    try:
        yield session
    finally:
        session.close()
