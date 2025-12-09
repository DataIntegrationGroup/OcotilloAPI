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
from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import mapped_column, relationship, Mapped
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy

from db.base import AutoBaseMixin, Base, lexicon_term


class LexiconTerm(Base, AutoBaseMixin):
    """
    Lexicon model for storing terms and their definitions.
    This model can be extended to include additional fields as needed.
    """

    __tablename__ = "lexicon_term"
    term: Mapped[str] = mapped_column(unique=True, nullable=False)
    definition: Mapped[str] = mapped_column(nullable=False)

    category_associations = relationship(
        "LexiconTermCategoryAssociation",
        back_populates="term",
        cascade="all, delete-orphan",
    )
    categories: AssociationProxy[list["LexiconCategory"]] = association_proxy(
        "category_associations", "category"
    )

    def __repr__(self):
        return f"<LexiconTerm(term={self.term}, definition={self.definition})>"


class LexiconCategory(Base, AutoBaseMixin):
    """
    Model for storing categories of terms.
    This can be used to group terms into different categories.
    """

    __tablename__ = "lexicon_category"
    name = mapped_column(String(100), unique=True, nullable=False)
    description = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f"<LexiconCategory(name={self.name}, description={self.description})>"


class LexiconTermCategoryAssociation(Base, AutoBaseMixin):
    """
    Model for linking terms to categories.
    This can be used to create a many-to-many relationship between terms and categories.
    """

    __tablename__ = "lexicon_term_category_association"

    term_id = mapped_column(
        Integer, ForeignKey("lexicon_term.id", ondelete="CASCADE"), nullable=False
    )
    category_id = mapped_column(
        Integer,
        ForeignKey("lexicon_category.id", ondelete="CASCADE"),
        nullable=False,
    )

    term = relationship("LexiconTerm")
    category = relationship("LexiconCategory")

    def __repr__(self):
        return f"<LexiconTermCategoryAssociation(term_id={self.term.id}, category_id={self.category.id})>"


class LexiconTriple(Base, AutoBaseMixin):
    """
    Model for storing triples in the lexicon.
    This can be used to represent relationships between terms.
    """

    subject = lexicon_term(nullable=False, foreignkeykw={"ondelete": "CASCADE"})
    predicate = mapped_column(String(100), nullable=False)
    object_ = lexicon_term(nullable=False, foreignkeykw={"ondelete": "CASCADE"})

    subject_term = relationship(
        "LexiconTerm", foreign_keys=[subject], passive_deletes=True
    )
    object_term = relationship(
        "LexiconTerm", foreign_keys=[object_], passive_deletes=True
    )

    def __repr__(self):
        return f"<LexiconTriples(subject={self.subject}, predicate={self.predicate}, object_={self.object_})>"


# ============= EOF =============================================
