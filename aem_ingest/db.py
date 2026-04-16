"""
aem_ingest.db — Thin wrappers around the shared db.engine infrastructure.

Provides get_engine(), get_session(), and get_raw_connection() that the
ingest pipeline uses for bulk loading.  When a conn_string is provided
(e.g. from the CLI --db-conn flag), a dedicated engine is created for
that connection.  Otherwise, the shared application engine from
db.engine is reused.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Module-level cache for conn-string-based engines (CLI / batch use).
_engine: Engine | None = None


def get_engine(conn_string: str, echo: bool = False) -> Engine:
    """Create or return a cached SQLAlchemy engine for *conn_string*.

    The ingest pipeline accepts an explicit connection string (from a CLI
    flag or batch config), so it cannot simply reuse the app-level engine
    from ``db.engine`` which is configured via env vars.  We keep a
    module-level cache so repeated calls within the same process reuse
    the same pool.
    """
    global _engine
    if _engine is None or str(_engine.url) != conn_string:
        _engine = create_engine(
            conn_string,
            echo=echo,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
        )
        logger.info(
            "SQLAlchemy engine created: %s",
            _engine.url.render_as_string(hide_password=True),
        )
    return _engine


@contextmanager
def get_session(conn_string: str) -> Generator[Session, None, None]:
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


def get_raw_connection(conn_string: str):
    """Get the underlying DBAPI connection for COPY protocol.

    Used for psycopg2 copy_expert() bulk loading of millions of rows.
    """
    engine = get_engine(conn_string)
    return engine.raw_connection()
