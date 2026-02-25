"""Utilities for preparing and keeping the database schema in sync."""

import os

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy_searchable import sync_trigger
from sqlalchemy_utils import TSVectorType

from db import Base

APP_READ_GRANT_SQL = text("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_read') THEN
            EXECUTE 'GRANT USAGE ON SCHEMA public TO app_read';
            EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_read';
            EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_read';
        END IF;
    END $$;
    """)


def _parse_app_read_members() -> list[str]:
    members = os.environ.get("APP_READ_MEMBERS", "")
    parsed = [member.strip() for member in members.split(",") if member.strip()]
    # pygeoapi should always inherit the default read role.
    if "pygeoapi" not in {member.lower() for member in parsed}:
        parsed.append("pygeoapi")
    return parsed


def grant_app_read_members(executor: Session | Connection | None) -> None:
    """Grant app_read to each configured role if it exists."""
    if executor is None:
        return
    members = _parse_app_read_members()
    if not members:
        return
    for member in members:
        safe_member = member.replace("'", "''")
        quoted = f'"{safe_member}"'
        stmt = text(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{safe_member}') THEN
                    EXECUTE 'GRANT app_read TO {quoted}';
                END IF;
            END $$;
            """)
        executor.execute(stmt)


def recreate_public_schema(session: Session) -> None:
    """Drop and recreate the public schema, PostGIS extension, and app_read grants."""
    session.execute(text("DROP SCHEMA public CASCADE"))
    session.execute(text("CREATE SCHEMA public"))
    session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    session.execute(APP_READ_GRANT_SQL)
    grant_app_read_members(session)
    session.commit()


def sync_search_vector_triggers(session: Session) -> None:
    """Ensure SQLAlchemy-searchable triggers exist for every TSVector column."""
    conn = session.connection()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, TSVectorType):
                sync_trigger(conn, table.name, column.name, list(column.type.columns))
    session.commit()
