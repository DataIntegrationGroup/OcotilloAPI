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
from pathlib import Path

from fastapi_pagination import add_pagination
from sqlalchemy import text, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DatabaseError

from db import Base
from db.engine import session_ctx
from db.lexicon import (
    LexiconCategory,
    LexiconTerm,
    LexiconTermCategoryAssociation,
)
from db.parameter import Parameter


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


def erase_and_rebuild_db():
    with session_ctx() as session:
        session.execute(text("DROP SCHEMA public CASCADE"))
        session.execute(text("CREATE SCHEMA public"))
        session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        session.commit()
        Base.metadata.drop_all(session.bind)
        Base.metadata.create_all(session.bind)

    init_lexicon()
    init_parameter()


def init_lexicon(path: str = None) -> None:
    if path is None:
        path = Path(__file__).parent / "lexicon.json"

    with open(path) as f:
        import json

        default_lexicon = json.load(f)

    with session_ctx() as session:
        terms = default_lexicon["terms"]
        categories = default_lexicon["categories"]
        category_names = [category["name"] for category in categories]
        existing_categories = dict(
            session.execute(
                select(LexiconCategory.name, LexiconCategory.id).where(
                    LexiconCategory.name.in_(category_names)
                )
            ).all()
        )
        category_rows = [
            {"name": category["name"], "description": category["description"]}
            for category in categories
            if category["name"] not in existing_categories
        ]
        if category_rows:
            session.execute(
                insert(LexiconCategory)
                .values(category_rows)
                .on_conflict_do_nothing(index_elements=["name"])
            )
            session.commit()
            existing_categories = dict(
                session.execute(
                    select(LexiconCategory.name, LexiconCategory.id).where(
                        LexiconCategory.name.in_(category_names)
                    )
                ).all()
            )

        term_names = [term_dict["term"] for term_dict in terms]
        existing_terms = dict(
            session.execute(
                select(LexiconTerm.term, LexiconTerm.id).where(
                    LexiconTerm.term.in_(term_names)
                )
            ).all()
        )
        term_rows = [
            {"term": term_dict["term"], "definition": term_dict["definition"]}
            for term_dict in terms
            if term_dict["term"] not in existing_terms
        ]
        if term_rows:
            session.execute(
                insert(LexiconTerm)
                .values(term_rows)
                .on_conflict_do_nothing(index_elements=["term"])
            )
            session.commit()
            existing_terms = dict(
                session.execute(
                    select(LexiconTerm.term, LexiconTerm.id).where(
                        LexiconTerm.term.in_(term_names)
                    )
                ).all()
            )

        term_ids = [existing_terms.get(term_name) for term_name in term_names]
        category_ids = [
            existing_categories.get(category_name) for category_name in category_names
        ]
        existing_links = set()
        if term_ids and category_ids:
            existing_links = set(
                session.execute(
                    select(
                        LexiconTermCategoryAssociation.term_id,
                        LexiconTermCategoryAssociation.category_id,
                    ).where(
                        LexiconTermCategoryAssociation.term_id.in_(
                            [term_id for term_id in term_ids if term_id is not None]
                        ),
                        LexiconTermCategoryAssociation.category_id.in_(
                            [
                                category_id
                                for category_id in category_ids
                                if category_id is not None
                            ]
                        ),
                    )
                ).all()
            )

        association_rows = []
        seen_links = set()
        for term_dict in terms:
            term_id = existing_terms.get(term_dict["term"])
            if term_id is None:
                continue
            for category in term_dict["categories"]:
                category_id = existing_categories.get(category)
                if category_id is None:
                    continue
                key = (term_id, category_id)
                if key in existing_links or key in seen_links:
                    continue
                seen_links.add(key)
                association_rows.append(
                    {"term_id": term_id, "category_id": category_id}
                )

        if association_rows:
            session.execute(
                insert(LexiconTermCategoryAssociation).values(association_rows)
            )
            session.commit()


def register_routes(app):
    if getattr(app.state, "routes_registered", False):
        return

    from admin.auth_routes import router as admin_auth_router
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
    from api.ngwmn import router as ngwmn_router
    from core.pygeoapi import mount_pygeoapi

    app.include_router(asset_router)
    app.include_router(admin_auth_router)
    app.include_router(author_router)
    app.include_router(contact_router)
    app.include_router(geospatial_router)
    app.include_router(group_router)
    mount_pygeoapi(app)
    app.include_router(lexicon_router)
    app.include_router(location_router)
    app.include_router(observation_router)
    app.include_router(publication_router)
    app.include_router(sample_router)
    app.include_router(sensor_router)
    app.include_router(search_router)
    app.include_router(thing_router)
    app.include_router(ngwmn_router)
    add_pagination(app)
    app.state.routes_registered = True


def configure_middleware(app):
    from starlette.middleware.cors import CORSMiddleware
    from starlette.middleware.sessions import SessionMiddleware

    if not getattr(app.state, "session_middleware_configured", False):
        session_secret_key = os.environ.get("SESSION_SECRET_KEY")
        if not session_secret_key:
            raise ValueError("SESSION_SECRET_KEY environment variable is not set.")
        app.add_middleware(SessionMiddleware, secret_key=session_secret_key)
        app.state.session_middleware_configured = True

    if not getattr(app.state, "cors_middleware_configured", False):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.state.cors_middleware_configured = True

    apitally_client_id = os.environ.get("APITALLY_CLIENT_ID")
    if apitally_client_id and not getattr(
        app.state, "apitally_middleware_configured", False
    ):
        from apitally.fastapi import ApitallyMiddleware

        app.add_middleware(
            ApitallyMiddleware,
            client_id=apitally_client_id,
            env=os.environ.get("ENVIRONMENT"),
            enable_request_logging=True,
            log_request_headers=True,
            log_request_body=True,
            log_response_body=True,
            capture_logs=True,
            capture_traces=False,
        )
        app.state.apitally_middleware_configured = True


def configure_admin(app):
    if getattr(app.state, "admin_configured", False):
        return

    from admin import create_admin

    create_admin(app)
    app.state.admin_configured = True


# ============= EOF =============================================
