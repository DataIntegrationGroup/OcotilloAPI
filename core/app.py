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
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from db import engine, Base, get_db_session
from services.lexicon import add_lexicon_term
from .settings import settings


def init_db():
    """
    Initialize the database by creating all tables.
    This function is called during application startup.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def init_extensions():
    """
    Initialize database extensions such as TimescaleDB.
    This function is called during application startup.
    """
    session = next(get_db_session())
    try:
        session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
        session.commit()
    except DatabaseError:
        session.rollback()


def init_lexicon():
    with open("./core/lexicon.json") as f:
        import json

        default_lexicon = json.load(f)

    # populate lexicon

    session = next(get_db_session())

    for term_dict in default_lexicon:
        try:
            add_lexicon_term(
                session,
                term_dict["term"],
                term_dict["definition"],
                term_dict["category"],
            )
        except DatabaseError:
            session.rollback()


def create_superuser():
    from admin.user import User

    session = next(get_db_session())
    user = User(
        username="admin",
        password="admin",
        is_superuser=True,
    )
    session.add(user)
    session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan event handler to initialize the database and lexicon.
    """
    if settings.get_enum("MODE") == "development":
        init_db()
        create_superuser()
        init_lexicon()
    yield


app = FastAPI(
    title="Sample Location API",
    description="API for managing sample locations",
    version="0.0.1",
    lifespan=lifespan,
)

# ============= EOF =============================================
