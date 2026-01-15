# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================

import asyncio
import copy
import getpass
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.util import await_only

from services.util import get_bool_env

load_dotenv()
driver = os.environ.get("DB_DRIVER", "")


def get_iam_login_token() -> str:
    """
    Return a short-lived IAM DB auth token for Cloud SQL Postgres.
    """
    from google.auth import default
    from google.auth.transport.requests import Request

    scopes = ["https://www.googleapis.com/auth/sqlservice.login"]
    creds, _ = default()
    if hasattr(creds, "with_scopes"):
        creds = creds.with_scopes(scopes=scopes)
    else:
        creds = copy.copy(creds)
        creds._scopes = scopes  # type: ignore[attr-defined]
    creds.refresh(Request())
    if not getattr(creds, "token", None):
        raise RuntimeError("Unable to acquire IAM DB auth token.")
    return creds.token


async def get_async_engine():
    """
    Asynchronous database session generator.
    """
    connector = await create_async_connector()

    def asyncify_connection():
        from sqlalchemy.dialects.postgresql.asyncpg import (
            AsyncAdapt_asyncpg_connection,
        )

        instance_name = os.environ.get("CLOUD_SQL_INSTANCE_NAME")
        user = os.environ.get("CLOUD_SQL_USER")
        password = os.environ.get("CLOUD_SQL_PASSWORD")
        database = os.environ.get("CLOUD_SQL_DATABASE")
        use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)
        ip_type = os.environ.get("CLOUD_SQL_IP_TYPE", "public")

        connect_kwargs = {
            "db": database,
            "user": user,
            "enable_iam_auth": use_iam_auth,
            "ip_type": ip_type,
        }
        if use_iam_auth:
            connect_kwargs["password"] = get_iam_login_token()
        else:
            connect_kwargs["password"] = password

        connection = connector.connect_async(instance_name, "asyncpg", **connect_kwargs)

        return AsyncAdapt_asyncpg_connection(
            engine.dialect.dbapi,
            await_only(connection),
            prepared_statement_cache_size=100,
        )

    return create_async_engine(
        "postgresql+asyncpg://",
        echo=True,
        creator=asyncify_connection,
    )


if driver == "cloudsql":
    from google.cloud.sql.connector import Connector, create_async_connector

    def init_connection_pool(connector):
        instance_name = os.environ.get("CLOUD_SQL_INSTANCE_NAME")
        user = os.environ.get("CLOUD_SQL_USER")
        password = os.environ.get("CLOUD_SQL_PASSWORD")
        database = os.environ.get("CLOUD_SQL_DATABASE")
        use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)
        ip_type = os.environ.get("CLOUD_SQL_IP_TYPE", "public")

        def getconn():
            connect_kwargs = {
                "user": user,
                "db": database,
                "ip_type": ip_type,
                "enable_iam_auth": use_iam_auth,
            }
            if use_iam_auth:
                connect_kwargs["password"] = get_iam_login_token()
            else:
                connect_kwargs["password"] = password

            conn = connector.connect(
                instance_name,  # The Cloud SQL instance name
                "pg8000",
                **connect_kwargs,
            )
            return conn

        # Configure connection pool for parallel transfers
        pool_size = int(os.environ.get("DB_POOL_SIZE", "10"))
        max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "20"))

        engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        return engine

    connector = Connector()
    engine = init_connection_pool(connector)

    # async_engine = asyncio.run(get_async_engine())

else:
    # Check for DATABASE_URL first (Render/Heroku standard)
    # Falls back to individual env vars for backward compatibility
    database_url = os.environ.get("DATABASE_URL", "")

    if database_url:
        # Use DATABASE_URL if provided (e.g., from Render)
        # Convert postgresql:// to postgresql+pg8000:// for SQLAlchemy
        if database_url.startswith("postgres://"):
            # Handle legacy postgres:// scheme (some platforms use this)
            url = database_url.replace("postgres://", "postgresql+pg8000://", 1)
        elif database_url.startswith("postgresql://"):
            url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)
        else:
            url = database_url
    else:
        # Fall back to individual environment variables (backward compatible)
        password = os.environ.get("POSTGRES_PASSWORD", "")
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        # Default to current OS user if POSTGRES_USER not set or empty
        user = os.environ.get("POSTGRES_USER", "").strip() or getpass.getuser()
        name = os.environ.get("POSTGRES_DB", "postgres")

        auth = f"{user}:{password}@" if user and password else ""
        port_part = f":{port}" if port else ""
        url = f"postgresql+pg8000://{auth}{host}{port_part}/{name}"

    # Configure connection pool for parallel transfers
    # pool_size: number of persistent connections
    # max_overflow: additional connections during peak usage
    pool_size = int(os.environ.get("DB_POOL_SIZE", "10"))
    max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "20"))

    engine = create_engine(
        url,
        # echo=True,
        plugins=["geoalchemy2"],
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # Verify connections before use
    )

    async_engine = create_async_engine(
        url.replace("postgresql+pg8000", "postgresql+asyncpg"),
        plugins=["geoalchemy2"],
    )
    # if "postgresql" not in url:
    #
    #     def on_connect(dbapi_connection, connection_record):
    #         """
    #         Event listener to load SpatiaLite on connection.
    #         """
    #         load_spatialite(dbapi_connection)
    #
    #         cursor = dbapi_connection.cursor()
    #         cursor.execute("PRAGMA foreign_keys=ON")
    #         cursor.close()
    #
    #     listen(engine, "connect", on_connect)


# async_database_sessionmaker = async_sessionmaker(async_engine)
database_sessionmaker = sessionmaker(engine, expire_on_commit=False)


def get_db_session():
    with database_sessionmaker() as session:
        try:
            yield session
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


@contextmanager
def session_ctx():
    yield from get_db_session()


# ============= EOF =============================================
