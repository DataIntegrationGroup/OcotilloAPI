"""Utilities for preparing and keeping the database schema in sync."""

from db import Base
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy_searchable import sync_trigger
from sqlalchemy_utils import TSVectorType

APP_READ_GRANT_SQL = text(
    """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_read') THEN
            EXECUTE 'GRANT USAGE ON SCHEMA public TO app_read';
            EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_read';
            EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_read';
            EXECUTE 'GRANT app_read TO PUBLIC';
        END IF;
    END $$;
    """
)


def recreate_public_schema(session: Session) -> None:
    """Drop and recreate the public schema, PostGIS extension, and app_read grants."""
    session.execute(text("DROP SCHEMA public CASCADE"))
    session.execute(text("CREATE SCHEMA public"))
    session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    session.execute(APP_READ_GRANT_SQL)
    session.commit()


def sync_search_vector_triggers(session: Session) -> None:
    """Ensure SQLAlchemy-searchable triggers exist for every TSVector column."""
    conn = session.connection()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, TSVectorType):
                sync_trigger(conn, table.name, column.name, list(column.type.columns))
    session.commit()
