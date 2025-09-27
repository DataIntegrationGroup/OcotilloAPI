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
from db.engine import get_db_session
from db.lexicon import (
    LexiconCategory,
    LexiconTerm,
    LexiconTermCategoryAssociation,
    LexiconTriple,
)
from sqlalchemy.orm import Session
from sqlalchemy import select

from services.audit_helper import audit_add


def add_lexicon_term(
    session: Session,
    term: str,
    definition: str,
    categories: list | None,
    user: dict = None,
) -> LexiconTerm:
    """
    Add a term to the lexicon with its definition and category.

    """
    db_categories = []
    if isinstance(categories, list):

        category_names = [c.get("name") for c in categories]

        sql = select(LexiconCategory).where(LexiconCategory.name.in_(category_names))
        associated_categories = session.scalars(sql).all()
        associated_category_names = [c.name for c in associated_categories]

        unassociated_categories = [
            category
            for category in categories
            if category.get("name") not in associated_category_names
        ]
        for category in unassociated_categories:
            # Create a new category if it does not exist
            category = LexiconCategory(
                name=category.get("name"), description=category.get("description")
            )
            audit_add(user, category)
            session.add(category)
            # session.commit()
            # session.flush()

            db_categories.append(category)

        db_categories.extend(associated_categories)

    # Check if the term already exists
    sql = select(LexiconTerm).where(LexiconTerm.term == term)
    dbterm = session.scalars(sql).one_or_none()
    if dbterm is None:
        dbterm = LexiconTerm(term=term, definition=definition)
        audit_add(user, dbterm)
        session.add(dbterm)

    if len(db_categories) > 0:
        for category in db_categories:
            link = LexiconTermCategoryAssociation()

            link.category = category
            link.term = dbterm
            audit_add(user, link)
            session.add(link)

    session.commit()

    return dbterm


def add_lexicon_triple(
    session: Session,
    subject: dict,
    predicate: str,
    object_: dict,
    user: dict = None,
) -> LexiconTriple:
    """
    Add a triple to the lexicon.
    """
    # add subject and object to db if they don't already exist
    for term in subject, object_:
        if isinstance(term, dict):
            sql = select(LexiconTerm).where(LexiconTerm.term == term["term"])
            existing_term = session.scalars(sql).one_or_none()
            if existing_term is None:
                add_lexicon_term(
                    session,
                    term["term"],
                    term["definition"],
                    term["categories"],
                    user=user,
                )

    triple = LexiconTriple(
        subject=subject["term"], predicate=predicate, object_=object_["term"]
    )
    audit_add(user, triple)
    session.add(triple)
    session.commit()
    return triple


def get_terms_by_category(category: str) -> list:
    """
    Fetches the terms from the database by category.

    Returns:
        list: A list of terms.
    """

    with next(get_db_session()) as session:

        sql = select(LexiconTerm)
        sql = sql.join(LexiconTermCategoryAssociation)
        sql = sql.join(LexiconCategory)
        sql = sql.filter(LexiconCategory.name == category)

        categories = [lex.term for lex in session.scalars(sql).all()]

    return categories


# ============= EOF =============================================
