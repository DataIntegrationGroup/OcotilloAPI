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
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from db import AutoBaseMixin, Base


class Lexicon(Base, AutoBaseMixin):
    """
    Lexicon model for storing terms and their definitions.
    This model can be extended to include additional fields as needed.
    """

    __tablename__ = "lexicon_term"
    term = mapped_column(String(100), unique=True, nullable=False)
    definition = mapped_column(String(255), nullable=False)

    # category_id = mapped_column(Integer, nullable=False)
    # category = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f"<Lexicon(category={self.category_id}, term={self.term}, definition={self.definition})>"


class Category(Base, AutoBaseMixin):
    """
    Model for storing categories of terms.
    This can be used to group terms into different categories.
    """

    __tablename__ = "lexicon_category"
    name = mapped_column(String(100), unique=True, nullable=False)
    description = mapped_column(String(255), nullable=True)

    # terms = relationship(
    #     "lexicon",
    #     backref="category",
    #     cascade="all, delete-orphan",
    #     lazy="dynamic"
    # )
    def __repr__(self):
        return f"<Category(name={self.name}, description={self.description})>"


class TermCategoryAssociation(Base, AutoBaseMixin):
    """
    Model for linking terms to categories.
    This can be used to create a many-to-many relationship between terms and categories.
    """

    __tablename__ = "lexicon_term_category_association"

    lexicon_term = mapped_column(
        String(100), ForeignKey("lexicon_term.term"), nullable=False
    )
    category_name = mapped_column(
        String(255), ForeignKey("lexicon_category.name"), nullable=False
    )

    term = relationship("Lexicon")
    category = relationship("Category")

    def __repr__(self):
        return f"<TermCategoryAssociation(term_id={self.term_id}, category_id={self.category_id})>"


# ============= EOF =============================================
