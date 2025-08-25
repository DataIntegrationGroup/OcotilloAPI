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
from fastapi import APIRouter, Depends, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select, func
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    editor_dependency,
    admin_dependency,
    viewer_function,
)
from db.engine import get_db_session
from db.lexicon import Category, LexiconTriple, Lexicon, TermCategoryAssociation
from schemas.lexicon import (
    CreateLexiconTerm,
    CreateLexiconCategory,
    CreateTriple,
    LexiconTermResponse,
    LexiconCategoryResponse,
)
from services.crud_helper import model_patcher, model_deleter
from services.lexicon_helper import add_lexicon_term
from services.query_helper import (
    paginated_all_getter,
    order_sort_filter,
    simple_get_by_id,
)

router = APIRouter(
    prefix="/lexicon", tags=["lexicon"], dependencies=[Depends(viewer_function)]
)

# POST =========================================================================


@router.post(
    "/category",
    status_code=HTTP_201_CREATED,
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
    "/term",
    summary="Add term",
    status_code=HTTP_201_CREATED,
)
def add_term(
    term_data: CreateLexiconTerm, session: session_dependency, user: admin_dependency
) -> LexiconTermResponse:
    """
    Endpoint to add a term to the lexicon.
    """
    data = term_data.model_dump()
    return add_lexicon_term(
        session, data["term"], data["definition"], data["categories"], user=user
    )


@router.post(
    "/triple/add",
    summary="Add triple",
    status_code=HTTP_201_CREATED,
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


# PATCH ========================================================================


@router.patch("/term/{term_id}", status_code=HTTP_200_OK)
def update_lexicon_term(
    term_id: int,
    term_data: CreateLexiconTerm,
    session: session_dependency,
    user: editor_dependency,
):

    return model_patcher(session, Lexicon, term_id, term_data, user=user)


@router.patch("/category/{category_id}", status_code=HTTP_200_OK)
def update_lexicon_category(
    category_id: int,
    category_data: CreateLexiconCategory,
    session: session_dependency,
    user: editor_dependency,
):
    return model_patcher(session, Category, category_id, category_data, user=user)


# GET ==========================================================================


@router.get("/term", summary="Get lexicon terms", status_code=HTTP_200_OK)
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

    # If sort is 'categories', we do not apply sorting or filtering
    if sort == "categories":
        sort = None
        order = None

    sql = order_sort_filter(sql, Lexicon, sort=sort, order=order, filter_=filter_)

    if order is None:
        sql = sql.order_by(func.lower(Lexicon.term).asc())

    return paginate(query=sql, conn=session)


@router.get("/term/{term_id}", status_code=HTTP_200_OK)
def get_lexicon_term(term_id: int, session: session_dependency) -> LexiconTermResponse:
    return simple_get_by_id(session, Lexicon, term_id)


@router.get("/category")
def get_lexicon_categories(
    session: session_dependency,
    sort: str = "name",
    order: str = "asc",
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[LexiconCategoryResponse]:
    """
    Endpoint to retrieve lexicon categories.
    """
    return paginated_all_getter(session, Category, sort, order, filter_)


@router.get("/category/{category_id}")
def get_lexicon_category(category_id: int, session: session_dependency):
    return simple_get_by_id(session, Category, category_id)


# DELETE =======================================================================


@router.delete(
    "/term/{term_id}",
    summary="Delete a lexicon term by ID",
    status_code=HTTP_204_NO_CONTENT,
)
async def delete_lexicon_term(
    session: session_dependency, user: admin_dependency, term_id: int
):
    return model_deleter(session, Lexicon, term_id)


# ============= EOF =============================================
