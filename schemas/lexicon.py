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
from pydantic import BaseModel, ConfigDict, AwareDatetime
from typing import List
from schemas import UTCAwareDatetime


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
    categories: list[str]


class CreateLexiconTriple(BaseModel):
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


class UpdateLexiconTriple(BaseModel):
    subject: str | None = None
    predicate: str | None = None
    object_: str | None = None


# -------- RESPONSE ----------


class BaseLexiconResponse(BaseModel):
    id: int
    created_at: UTCAwareDatetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class LexiconCategoryResponse(BaseLexiconResponse):
    """
    Pydantic model for the response of a lexicon category.
    This model can be extended to include additional fields as needed.
    """

    name: str
    description: str | None = None
    # terms: list[LexiconTermResponse] | None = None


class LexiconTermResponse(BaseLexiconResponse):
    """
    Pydantic model for the response of a lexicon term.
    This model can be extended to include additional fields as needed.
    """

    term: str
    definition: str
    categories: List[LexiconCategoryResponse] = []


class LexiconTripleResponse(BaseLexiconResponse):
    subject: str
    predicate: str
    object_: str


# ============= EOF =============================================
