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
import os
import re
from geoalchemy2 import load_spatialite
from sqlalchemy import create_engine, Column, Integer, DateTime, func, JSON
from sqlalchemy.event import listen
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, declared_attr
from sqlalchemy.util import await_only
from sqlalchemy_searchable import make_searchable


if os.environ.get("SPATIALITE_LIBRARY_PATH") is None:
    os.environ["SPATIALITE_LIBRARY_PATH"] = "/opt/homebrew/lib/mod_spatialite.dylib"

# engine = create_async_engine(
#     "sqlite+aiosqlite:///./development.db",
#     echo=True,
#     plugins=['geoalchemy2'],
# )


driver = os.environ.get("DB_DRIVER", "")

async_engine = None


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

        connection = connector.connect_async(
            instance_name,
            "asyncpg",
            db=database,
            password=password,
            user=user,
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

        def getconn():
            conn = connector.connect(
                instance_name,  # The Cloud SQL instance name
                "pg8000",
                user=user,
                password=password,
                db=database,
                ip_type="public",
            )
            return conn

        engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            echo=False,
        )
        return engine

    connector = Connector()
    engine = init_connection_pool(connector)

    async_engine = asyncio.run(get_async_engine())

else:
    if driver == "sqlite":
        name = os.environ.get("DB_NAME", "development.db")
        url = f"sqlite:///{name}"
    elif driver == "postgres":
        password = os.environ.get("POSTGRES_PASSWORD", "")
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        user = os.environ.get("POSTGRES_USER", "postgres")
        name = os.environ.get("POSTGRES_DB", "postgres")

        auth = f"{user}:{password}@" if user and password else ""
        port_part = f":{port}" if port else ""
        url = f"postgresql+pg8000://{auth}{host}{port_part}/{name}"
    else:
        url = "sqlite:///./development.db"

    engine = create_engine(
        url,
        # echo=True,
        plugins=["geoalchemy2"],
    )

    if "postgresql" not in url:

        def on_connect(dbapi_connection, connection_record):
            """
            Event listener to load SpatiaLite on connection.
            """
            load_spatialite(dbapi_connection)

            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        listen(engine, "connect", on_connect)


# sqlalchemy_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
if async_engine is not None:
    async_database_sessionmaker = async_sessionmaker(async_engine)
database_sessionmaker = sessionmaker(engine, expire_on_commit=False)


def get_db_session():
    session = database_sessionmaker()
    try:
        yield session
    finally:
        session.close()


Base = declarative_base()

make_searchable(Base.metadata)


def adder(session, table, model, **kwargs):
    """
    Helper function to add a new record to the database.
    """
    md = model.model_dump()
    if kwargs:
        md.update(kwargs)

    obj = table(**md)
    session.add(obj)
    session.commit()
    return obj


class AuditMixin:
    @declared_attr
    def created_at(self):
        return Column(DateTime, nullable=False, server_default=func.now())


def pascal_to_snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class AutoBaseMixin(AuditMixin):
    @declared_attr
    def __tablename__(self):
        return pascal_to_snake(self.__name__)

    @declared_attr
    def id(self):
        return Column(Integer, primary_key=True, autoincrement=True)


class PropertiesMixin:
    @declared_attr
    def properties(self):
        return Column(
            "properties",
            JSON,
            nullable=True,
            comment="JSONB column for storing additional properties",
        )


# ============= EOF =============================================
