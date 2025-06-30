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
from db.lexicon import Lexicon, Category, TermCategoryAssociation, LexiconTriple
from schemas.response.lexicon import LexiconTermResponse, LexiconCategoryResponse
from schemas.create.lexicon import CreateLexiconTerm, CreateLexiconCategory, CreateTriple
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
    response_model=LexiconTermResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_term(term_data: CreateLexiconTerm, session=Depends(get_db_session)):
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
        add_lexicon_term(session, subject["term"], subject["definition"], subject["category"])
        subject = subject["term"]

    if isinstance(object_, dict):
        add_lexicon_term(session, object_["term"], object_["definition"], object_["category"])
        object_ = object_["term"]

    triple = LexiconTriple(subject=subject,
                           predicate=predicate,
                           object_=object_)
    session.add(triple)
    session.commit()
    return triple

# ============= EOF =============================================
