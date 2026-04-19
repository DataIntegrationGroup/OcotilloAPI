# flake8: noqa: E501
"""Helpers for AEM ingest database access."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.engine import engine as shared_engine


def get_engine() -> Engine:
    """Return the shared app engine."""
    return shared_engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that yields a SQLAlchemy session with auto-rollback."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_raw_connection():
    """Get the underlying DBAPI connection for COPY protocol bulk loading."""
    return get_engine().raw_connection()
