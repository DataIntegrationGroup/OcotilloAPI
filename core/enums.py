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
from enum import Enum

from db import LexiconCategory, LexiconTerm, LexiconTermCategoryAssociation
from db.engine import session_ctx


def build_enum_from_lexicon_category(category: str) -> Enum:
    with session_ctx() as session:
        sql = (
            session.query(LexiconTerm)
            .join(LexiconTermCategoryAssociation)
            .join(LexiconCategory)
            .where(LexiconCategory.name == category)
        )
        terms = session.execute(sql).scalars().all()

        return Enum(category, {c.term: c.definition for c in terms})


QCStatus = build_enum_from_lexicon_category("qc_type")
# ============= EOF =============================================
