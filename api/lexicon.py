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
from fastapi import APIRouter, Depends
from fastapi import status
from db import get_db_session
from db.lexicon import Lexicon, Category, CategoryLink
from schemas.response.lexicon import LexiconTermResponse, LexiconCategoryResponse
from schemas.create.lexicon import CreateLexiconTerm, CreateLexiconCategory
from services.lexicon import add_lexicon_term
from sqlalchemy import select


router = APIRouter(
    prefix="/lexicon",
)


@router.post(
    "/category/add",
    status_code=status.HTTP_201_CREATED,
    response_model=LexiconCategoryResponse,
)
def add_category(category_data: CreateLexiconCategory, session=Depends(get_db_session)):
    """
    Endpoint to add a category to the lexicon.
    """
    # Implementation for adding a category goes here
    data = category_data.model_dump()
    name = data["name"]
    description = data.get("description", "")

    category = Category(name=name, description=description)
    session.add(category)
    session.commit()
    return category
    # return LexiconTermResponse.from_orm(category)


@router.post(
    "/add",
    summary="Add term",
    response_model=LexiconTermResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_term(term_data: CreateLexiconTerm, session=Depends(get_db_session)):
    """
    Endpoint to add a term to the lexicon.
    """
    # Implementation for adding a term goes here

    data = term_data.model_dump()
    # category = data.pop("category")
    # term = Lexicon(**data)
    # if category is not None:
    # if isinstance(category, str):
    #     sql = select(Category).where(Category.name == category)
    #     category = session.scalar(sql).one_or_none()
    #     if category is not None:
    #         category_id = category.id
    # else:
    #     category_id = category
    #
    # link = CategoryLink()
    # link.category_id = category_id
    # link.term = term
    # session.add(link)

    # session.add(term)
    # session.commit()
    return add_lexicon_term(session, data["term"], data["definition"], data["category"])


# ============= EOF =============================================
