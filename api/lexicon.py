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
from fastapi import APIRouter, Depends, Query, status
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db.engine import get_db_session
from db.lexicon import Category, LexiconTriple, Lexicon, TermCategoryAssociation
from schemas.lexicon import (
    CreateLexiconTerm,
    CreateLexiconCategory,
    CreateTriple,
    LexiconTermResponse,
    LexiconCategoryResponse,
)
from services.lexicon import add_lexicon_term
from services.query_helper import simple_all_getter, paginated_all_getter

router = APIRouter(
    prefix="/lexicon",
    tags=["lexicon"],
)


@router.post(
    "/category/add",
    status_code=status.HTTP_201_CREATED,
)
def add_category(
    category_data: CreateLexiconCategory, session=Depends(get_db_session)
) -> LexiconCategoryResponse:
    """
    Endpoint to add a category to the lexicon.
    """
    data = category_data.model_dump()
    name = data["name"]
    description = data.get("description", "")

    category = Category(name=name, description=description)
    session.add(category)
    session.commit()
    return category


@router.post(
    "/add",
    summary="Add term",
    status_code=status.HTTP_201_CREATED,
)
def add_term(
    term_data: CreateLexiconTerm, session=Depends(get_db_session)
) -> LexiconTermResponse:
    """
    Endpoint to add a term to the lexicon.
    """
    data = term_data.model_dump()
    return add_lexicon_term(session, data["term"], data["definition"], data["category"])


@router.post(
    "/triple/add",
    summary="Add triple",
    status_code=status.HTTP_201_CREATED,
)
def add_triple(triple_data: CreateTriple, session=Depends(get_db_session)):
    triple_data = triple_data.model_dump()
    subject = triple_data["subject"]
    predicate = triple_data["predicate"]
    object_ = triple_data["object_"]

    if isinstance(subject, dict):
        add_lexicon_term(
            session, subject["term"], subject["definition"], subject["category"]
        )
        subject = subject["term"]

    if isinstance(object_, dict):
        add_lexicon_term(
            session, object_["term"], object_["definition"], object_["category"]
        )
        object_ = object_["term"]

    triple = LexiconTriple(subject=subject, predicate=predicate, object_=object_)
    session.add(triple)
    session.commit()
    return triple


@router.get("")
def get_lexicon_terms(
    session: session_dependency,
    category: str | None = None,
    term: str | None = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[LexiconTermResponse]:
    """
    Endpoint to retrieve lexicon terms.
    """
    sql = select(Lexicon)
    if category:
        sql = (
            sql.join(TermCategoryAssociation)
            .join(Category)
            .where(Category.name == category)
        )
    if term:
        sql = sql.where(Lexicon.term.ilike(f"%{term}%"))

    sql = order_sort_filter(sql, Lexicon, sort=sort, order=order, filter_=filter_)
    return paginate(query=sql, conn=session)
    # return paginated_all_getter(session, sql, filter_)


@router.get("/category")
def get_lexicon_categories(
    session: session_dependency,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[LexiconCategoryResponse]:
    """
    Endpoint to retrieve lexicon categories.
    """
    return paginated_all_getter(session, Category, sort, order, filter_)


# ============= EOF =============================================
