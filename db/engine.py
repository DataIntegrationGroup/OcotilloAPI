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

import copy
import getpass
import logging
import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.util import await_only

from services.env import get_bool_env

# Load .env file. Do not override env vars already set by the runtime.
load_dotenv(override=False)
driver = os.environ.get("DB_DRIVER", "")
logger = logging.getLogger(__name__)


def is_pool_logging_enabled() -> bool:
    return bool(
        get_bool_env("DB_POOL_LOGGING", False)
        or get_bool_env("API_DEBUG_TIMING", False)
    )


def _install_pool_logging(engine):
    if not is_pool_logging_enabled():
        return

    @event.listens_for(engine, "checkout")
    def log_checkout(dbapi_connection, connection_record, connection_proxy):
        connection_record.info["checked_out_at"] = time.perf_counter()
        logger.info(
            "db pool checkout",
            extra={
                "event": "db_pool_checkout",
                "pool_status": engine.pool.status(),
            },
        )

    @event.listens_for(engine, "checkin")
    def log_checkin(dbapi_connection, connection_record):
        checked_out_at = connection_record.info.pop("checked_out_at", None)
        hold_ms = None
        if checked_out_at is not None:
            hold_ms = round((time.perf_counter() - checked_out_at) * 1000, 2)
        logger.info(
            "db pool checkin",
            extra={
                "event": "db_pool_checkin",
                "connection_hold_ms": hold_ms,
                "pool_status": engine.pool.status(),
            },
        )

    @event.listens_for(engine, "invalidate")
    def log_invalidate(dbapi_connection, connection_record, exception):
        logger.warning(
            "db pool invalidate",
            extra={
                "event": "db_pool_invalidate",
                "pool_status": engine.pool.status(),
                "exception_type": (type(exception).__name__ if exception else None),
            },
        )


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

        connection = connector.connect_async(
            instance_name,
            "asyncpg",
            **connect_kwargs,
        )

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
        pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

        engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
        )
        _install_pool_logging(engine)
        return engine

    connector = Connector()
    engine = init_connection_pool(connector)

    # async_engine = asyncio.run(get_async_engine())

else:
    # if driver == "sqlite":
    #     name = os.environ.get("DB_NAME", "development.db")
    #     url = f"sqlite:///{name}"
    # elif driver == "postgres":
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    # Default to current OS user if POSTGRES_USER not set or empty
    user = os.environ.get("POSTGRES_USER", "").strip() or getpass.getuser()
    name = os.environ.get("POSTGRES_DB", "postgres")

    auth = f"{user}:{password}@" if user and password else ""
    port_part = f":{port}" if port else ""
    url = f"postgresql+pg8000://{auth}{host}{port_part}/{name}"
    # else:
    #     url = "sqlite:///./development.db"

    # Configure connection pool for parallel transfers
    # pool_size: number of persistent connections
    # max_overflow: additional connections during peak usage
    pool_size = int(os.environ.get("DB_POOL_SIZE", "10"))
    max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
    pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

    engine = create_engine(
        url,
        # echo=True,
        plugins=["geoalchemy2"],
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,  # Verify connections before use
    )
    _install_pool_logging(engine)

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
