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
import os

from geoalchemy2 import load_spatialite
from sqlalchemy import create_engine, Column, Integer, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.event import listen
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, declared_attr

if os.environ.get("SPATIALITE_LIBRARY_PATH") is None:
    os.environ["SPATIALITE_LIBRARY_PATH"] = "/opt/homebrew/lib/mod_spatialite.dylib"

# engine = create_async_engine(
#     "sqlite+aiosqlite:///./development.db",
#     echo=True,
#     plugins=['geoalchemy2'],
# )

engine = create_engine(
    "sqlite:///./development.db",
    # echo=True,
    plugins=["geoalchemy2"],
)


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
database_sessionmaker = sessionmaker(engine, expire_on_commit=False)


async def get_db_session():
    session = database_sessionmaker()
    yield session
    session.close()


Base = declarative_base()


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

    @declared_attr
    def updated_at(self):
        return Column(
            DateTime,
            nullable=False,
            server_default=func.now(),
            server_onupdate=func.now(),
        )


class AutoBaseMixin(AuditMixin):
    @declared_attr
    def __tablename__(self):
        return self.__name__.lower()

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
