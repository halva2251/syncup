"""Engine + session factory for the application DB.

We expose a helper to construct a sessionmaker and a small generator
dependency for request-scoped sessions.
"""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def sessionmaker_for(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 1800,
) -> sessionmaker[Session]:
    """Build a sessionmaker bound to a fresh engine for the given URL.

    Args:
        database_url: SQLAlchemy connection string.
        pool_size: number of connections to keep open permanently.
        max_overflow: connections above pool_size allowed under load.
        pool_recycle: seconds after which idle connections are recycled;
            prevents "server closed the connection unexpectedly" errors.
    """
    engine: Engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and ensure it is closed when the caller is done.

    The caller is responsible for calling ``session.commit()`` before
    the context exits. On any exception the session is rolled back
    automatically. Intended to be wrapped as a FastAPI dependency.
    """
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: yield a request-scoped DB session.

    The session factory is taken from ``app.state.db``, which is created
    once at startup in the lifespan context manager.
    """
    yield from get_session(request.app.state.db)
