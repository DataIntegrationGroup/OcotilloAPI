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
from pathlib import Path

from fastapi_pagination import add_pagination
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from db import Base
from db.engine import engine, session_ctx
from db.parameter import Parameter
from services.lexicon_helper import add_lexicon_term, add_lexicon_category


# ============= EOF =============================================
def init_db():
    """
    Initialize the database by creating all tables.
    This function is called during application startup.
    """

    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


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


def init_parameter(path: str = None) -> None:
    """
    Populate the parameter table to allow their use in creating and editing
    observations
    """
    if path is None:
        path = Path(__file__).parent / "parameter.json"

    with open(path) as f:
        import json

        default_parameter = json.load(f)

    with session_ctx() as session:
        for param in default_parameter:
            try:
                parameter_obj = Parameter(
                    parameter_name=param["parameter_name"],
                    matrix=param["matrix"],
                    parameter_type=param["parameter_type"],
                    cas_number=param["cas_number"],
                    default_unit=param["default_unit"],
                )
                session.add(parameter_obj)
                session.commit()
            except DatabaseError as e:
                print(f"Failed to add parameter {param['parameter_name']}: error: {e}")
                session.rollback()


def erase_and_rebuild_db(session: Session):
    from sqlalchemy import text

    with session.bind.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

    Base.metadata.drop_all(session.bind)
    Base.metadata.create_all(session.bind)


def init_lexicon(path: str = None) -> None:
    if path is None:
        path = Path(__file__).parent / "lexicon.json"

    with open(path) as f:
        import json

        default_lexicon = json.load(f)

    # populate lexicon

    with session_ctx() as session:
        terms = default_lexicon["terms"]
        categories = default_lexicon["categories"]
        for category in categories:
            try:
                add_lexicon_category(session, category["name"], category["description"])
            except DatabaseError as e:
                print(f"Failed to add category {category['name']}: error: {e}")
                session.rollback()
                continue

        for term_dict in terms:
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


def register_routes(app):
    from api.group import router as group_router
    from api.contact import router as contact_router
    from api.location import router as location_router
    from api.thing import router as thing_router
    from api.sensor import router as sensor_router

    from api.sample import router as sample_router
    from api.observation import router as observation_router

    from api.lexicon import router as lexicon_router

    from api.publication import router as publication_router
    from api.author import router as author_router
    from api.asset import router as asset_router
    from api.search import router as search_router
    from api.geospatial import router as geospatial_router

    app.include_router(asset_router)
    app.include_router(author_router)
    app.include_router(contact_router)
    app.include_router(geospatial_router)
    app.include_router(group_router)
    app.include_router(lexicon_router)
    app.include_router(location_router)
    app.include_router(observation_router)
    app.include_router(publication_router)
    app.include_router(sample_router)
    app.include_router(sensor_router)
    app.include_router(search_router)
    app.include_router(thing_router)
    add_pagination(app)
