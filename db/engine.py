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
from sqlalchemy.engine import URL
from sqlalchemy.orm import (
    sessionmaker,
)

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
                "exception_type": (
                    type(exception).__name__ if exception else None
                ),  # noqa: E501
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


# Configure connection pool for parallel transfers
# pool_size: number of persistent connections
# max_overflow: additional connections during peak usage
pool_size = int(os.environ.get("DB_POOL_SIZE", "5"))
max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))


def get_cloudsql_socket_host(instance_name: str | None = None) -> str:
    instance = instance_name or os.environ.get("CLOUD_SQL_INSTANCE_NAME", "")
    if not instance:
        message = "CLOUD_SQL_INSTANCE_NAME must be set for DB_DRIVER=cloudsql"
        raise RuntimeError(message)
    socket_dir = os.environ.get("CLOUD_SQL_SOCKET_DIR", "/cloudsql")
    socket_dir = socket_dir.rstrip("/")
    return f"{socket_dir}/{instance}"


def build_cloudsql_url(password: str | None = None) -> URL:
    user = os.environ.get("CLOUD_SQL_USER", "")
    database = os.environ.get("CLOUD_SQL_DATABASE", "")
    if not user:
        raise RuntimeError("CLOUD_SQL_USER must be set for DB_DRIVER=cloudsql")
    if not database:
        message = "CLOUD_SQL_DATABASE must be set for DB_DRIVER=cloudsql"
        raise RuntimeError(message)
    socket_host = get_cloudsql_socket_host()
    return URL.create(
        "postgresql+psycopg2",
        username=user,
        password=password,
        database=database,
        query={"host": socket_host},
    )


def init_cloudsql_engine():
    use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)
    password = None if use_iam_auth else os.environ.get("CLOUD_SQL_PASSWORD")
    if not use_iam_auth and not password:
        raise RuntimeError(
            "CLOUD_SQL_PASSWORD must be set when CLOUD_SQL_IAM_AUTH is false"
        )

    engine = create_engine(
        build_cloudsql_url(password=password),
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,
    )

    if use_iam_auth:

        @event.listens_for(engine, "do_connect")
        def inject_iam_token(dialect, conn_rec, cargs, cparams):
            cparams["password"] = get_iam_login_token()

    _install_pool_logging(engine)
    return engine


if driver == "cloudsql":
    engine = init_cloudsql_engine()

else:
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    # Default to current OS user if POSTGRES_USER not set or empty
    user = os.environ.get("POSTGRES_USER", "").strip() or getpass.getuser()
    name = os.environ.get("POSTGRES_DB", "postgres")

    auth = f"{user}:{password}@" if user and password else ""
    port_part = f":{port}" if port else ""
    url = f"postgresql+psycopg2://{auth}{host}{port_part}/{name}"

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
