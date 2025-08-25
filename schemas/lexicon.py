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
from pydantic import BaseModel
from typing import List

from schemas import ORMBaseModel


# -------- CREATE ----------
class CreateLexiconCategory(BaseModel):
    """
    Pydantic model for creating a lexicon category.
    This model can be extended to include additional fields as needed.
    """

    name: str
    description: str | None = None


class CreateLexiconTerm(BaseModel):
    """
    Pydantic model for creating a lexicon term.
    This model can be extended to include additional fields as needed.
    """

    term: str
    definition: str
    categories: list[CreateLexiconCategory] | None = None


class CreateTriple(BaseModel):
    """
    Pydantic model for creating a triple.
    This model can be extended to include additional fields as needed.
    """

    subject: CreateLexiconTerm
    predicate: str
    object_: CreateLexiconTerm


# UPDATE =======================================================================


class UpdateLexiconCategory(BaseModel):
    name: str | None = None
    description: str | None = None


class UpdateLexiconTerm(BaseModel):
    term: str | None = None
    definition: str | None = None


class UpdateTriple(BaseModel):
    pass


# -------- RESPONSE ----------


class LexiconCategoryResponse(ORMBaseModel):
    """
    Pydantic model for the response of a lexicon category.
    This model can be extended to include additional fields as needed.
    """

    name: str
    description: str | None = None
    # terms: list[LexiconTermResponse] | None = None


class LexiconTermResponse(ORMBaseModel):
    """
    Pydantic model for the response of a lexicon term.
    This model can be extended to include additional fields as needed.
    """

    term: str
    definition: str
    categories: List[LexiconCategoryResponse] = []


# ============= EOF =============================================
