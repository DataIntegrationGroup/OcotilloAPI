# flake8: noqa: E501
"""
Helpers for AEM ingest database access.

Defaults to the shared app engine when no explicit connection string is
provided, while still supporting ad hoc operator-supplied connection strings
for batch or one-off ingest runs.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.engine import engine as shared_engine

logger = logging.getLogger(__name__)

_engine_cache: dict[str, Engine] = {}


def get_engine(conn_string: str | None = None, echo: bool = False) -> Engine:
    """Return the shared app engine or a cached engine for *conn_string*."""
    if not conn_string:
        return shared_engine

    cached = _engine_cache.get(conn_string)
    if cached is None:
        cached = create_engine(
            conn_string,
            echo=echo,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
        )
        _engine_cache[conn_string] = cached
        logger.info(
            "AEM SQLAlchemy engine created: %s",
            cached.url.render_as_string(hide_password=True),
        )
    return cached


@contextmanager
def get_session(conn_string: str | None = None) -> Generator[Session, None, None]:
    """Context manager that yields a SQLAlchemy session with auto-rollback."""
    engine = get_engine(conn_string)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_raw_connection(conn_string: str | None = None):
    """Get the underlying DBAPI connection for COPY protocol bulk loading."""
    return get_engine(conn_string).raw_connection()
