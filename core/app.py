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
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from db.base import Base
from db.engine import engine, session_ctx
from services.lexicon_helper import add_lexicon_term
from .settings import settings


def init_db():
    """
    Initialize the database by creating all tables.
    This function is called during application startup.
    """

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def init_hypertables():
    """
    Initialize hypertables for time-series data.
    This function is called during application startup.
    """
    # session = next(get_db_session())
    # Create hypertables for time-series data
    with session_ctx() as session:
        session.execute(
            text("select create_hypertable('observation', 'observation_datetime');")
        )

    # session.commit()
    # session.close()


def init_lexicon(path=None):
    if path is None:
        path = Path("..") / "core" / "lexicon.json"

    with open(path) as f:
        import json

        default_lexicon = json.load(f)

    # populate lexicon

    with session_ctx() as session:
        for term_dict in default_lexicon:
            try:
                add_lexicon_term(
                    session,
                    term_dict["term"],
                    term_dict["definition"],
                    term_dict["categories"],
                )
            except DatabaseError as e:
                print(
                    f"Failed to add term {term_dict['term']}: {term_dict['definition']} error: {e}"
                )

                session.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan event handler to initialize the database and lexicon.
    """
    if settings.get_enum("MODE") == "development":
        init_db()
        init_lexicon()
    yield


app = FastAPI(
    title="Sample Location API",
    description="API for managing sample locations",
    version="0.0.1",
    lifespan=lifespan,
)

# ============= EOF =============================================
