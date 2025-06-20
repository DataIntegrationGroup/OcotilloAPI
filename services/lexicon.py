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
from db.lexicon import Category, Lexicon, TermCategoryAssociation
from sqlalchemy.orm import Session
from sqlalchemy import select


def add_lexicon_term(session: Session, term: str, definition: str, category: str | int):
    """
    Add a term to the lexicon with its definition and category.

    """

    if isinstance(category, str):
        sql = select(Category).where(Category.name == category)
        dbcategory = session.scalars(sql).one_or_none()
        if dbcategory is None:
            # Create a new category if it does not exist
            dbcategory = Category(name=category)
            session.add(dbcategory)
            session.flush()
    else:
        dbcategory = session.get(Category, category)

    term = Lexicon(term=term, definition=definition)
    session.add(term)

    if dbcategory is not None:
        link = TermCategoryAssociation()

        link.category = dbcategory
        link.term = term

        session.add(link)

    session.commit()

    return term


# ============= EOF =============================================
