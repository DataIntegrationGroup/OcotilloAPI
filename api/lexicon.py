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
from sqlalchemy.exc import ProgrammingError
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_409_CONFLICT,
)

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    editor_dependency,
    admin_dependency,
    viewer_function,
)
from db import adder
from db.lexicon import Category, Lexicon, TermCategoryAssociation, LexiconTriple
from schemas.lexicon import (
    CreateLexiconTerm,
    CreateLexiconCategory,
    CreateTriple,
    LexiconTermResponse,
    LexiconCategoryResponse,
    LexiconTripleResponse,
    UpdateLexiconTerm,
    UpdateLexiconCategory,
    UpdateLexiconTriple,
)
from services.crud_helper import model_patcher, model_deleter
from services.exceptions_helper import PydanticStyleException
from services.lexicon_helper import add_lexicon_term, add_lexicon_triple
from services.query_helper import (
    paginated_all_getter,
    order_sort_filter,
    simple_get_by_id,
)

router = APIRouter(
    prefix="/lexicon", tags=["lexicon"], dependencies=[Depends(viewer_function)]
)


def database_error_handler(
    payload: UpdateLexiconTriple, error: ProgrammingError
) -> None:
    """
    Handle errors raised by the database when adding or updating a lexicon triple.
    """

    error_message = error.orig.args[0]["M"]
    print(error_message)

    if (
        error_message
        == 'insert or update on table "lexicon_triple" violates foreign key constraint "lexicon_triple_subject_fkey"'
    ):
        detail = {
            "loc": ["body", "subject"],
            "msg": f"Lexicon with term {payload.subject} not found.",
            "type": "value_error",
            "input": {"subject": payload.subject},
        }
    elif (
        error_message
        == 'insert or update on table "lexicon_triple" violates foreign key constraint "lexicon_triple_object__fkey"'
    ):
        detail = {
            "loc": ["body", "object_"],
            "msg": f"Lexicon with term {payload.object_} not found.",
            "type": "value_error",
            "input": {"object_": payload.object_},
        }

    raise PydanticStyleException(status_code=HTTP_409_CONFLICT, detail=[detail])


# POST =========================================================================


@router.post(
    "/category",
    status_code=HTTP_201_CREATED,
)
def add_category(
    category_data: CreateLexiconCategory,
    session: session_dependency,
    user: admin_dependency,
) -> LexiconCategoryResponse:
    """
    Endpoint to add a category to the lexicon.
    """
    return adder(session, Category, category_data, user=user)


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
    "/triple",
    summary="Add triple",
    status_code=HTTP_201_CREATED,
)
def add_triple(
    triple_data: CreateTriple, session: session_dependency, user: admin_dependency
) -> LexiconTripleResponse:
    triple_data = triple_data.model_dump()
    subject = triple_data["subject"]
    predicate = triple_data["predicate"]
    object_ = triple_data["object_"]
    return add_lexicon_triple(session, subject, predicate, object_, user=user)


# PATCH ========================================================================


@router.patch("/term/{term_id}", status_code=HTTP_200_OK)
def update_lexicon_term(
    term_id: int,
    term_data: UpdateLexiconTerm,
    session: session_dependency,
    user: editor_dependency,
) -> LexiconTermResponse:

    return model_patcher(session, Lexicon, term_id, term_data, user=user)


@router.patch("/category/{category_id}", status_code=HTTP_200_OK)
def update_lexicon_category(
    category_id: int,
    category_data: UpdateLexiconCategory,
    session: session_dependency,
    user: editor_dependency,
) -> LexiconCategoryResponse:
    return model_patcher(session, Category, category_id, category_data, user=user)


@router.patch("/triple/{triple_id}", status_code=HTTP_200_OK)
def update_lexicon_triple(
    triple_id: int,
    triple_data: UpdateLexiconTriple,
    session: session_dependency,
    user: editor_dependency,
) -> LexiconTripleResponse:
    try:
        return model_patcher(session, LexiconTriple, triple_id, triple_data, user=user)
    except ProgrammingError as e:
        database_error_handler(triple_data, e)


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
def get_lexicon_category(
    category_id: int, session: session_dependency
) -> LexiconCategoryResponse:
    return simple_get_by_id(session, Category, category_id)


@router.get("/triple", summary="Get lexicon triples", status_code=HTTP_200_OK)
async def get_lexicon_triples(
    session: session_dependency,
    sort: str = "subject",
    order: str = "asc",
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[LexiconTripleResponse]:
    """
    Endpoint to retrieve lexicon triples.
    """
    return paginated_all_getter(session, LexiconTriple, sort, order, filter_)


@router.get("/triple/{triple_id}", status_code=HTTP_200_OK)
async def get_lexicon_triple(
    triple_id: int, session: session_dependency
) -> LexiconTripleResponse:
    return simple_get_by_id(session, LexiconTriple, triple_id)


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


@router.delete(
    "/category/{category_id}",
    summary="Delete a lexicon category by ID",
    status_code=HTTP_204_NO_CONTENT,
)
async def delete_lexicon_category(
    session: session_dependency, user: admin_dependency, category_id: int
):
    return model_deleter(session, Category, category_id)


# ============= EOF =============================================
