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
from db.lexicon import Lexicon
from schemas.lexicon import CreateLexiconTerm, LexiconTermResponse

router = APIRouter(
    prefix="/lexicon",
)


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
    term = Lexicon(**data)
    session.add(term)
    session.commit()
    return term


# ============= EOF =============================================
