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
"""
db/base.py

This file defines the foundational components for the SQLAlchemy models.
It includes:
1.  The declarative base class (`Base`) that all models will inherit from.
2.  A helper function (`lexicon_term`) to create standardized foreign key columns
    referencing the `lexicon_term` table.
3. A helper function (`pascal_to_snake`) to convert class names from PascalCase to snake_case
    for automatic table naming.
4. Mixins for common functionality:
    - `AutoBaseMixin`: Adds automatic table naming and an auto-incrementing primary key.
    - `PropertiesMixin`: Adds a JSONB properties column for storing additional attributes.
    - `ReleaseMixin`: Adds a release status column referencing the `lexicon_term` table.
    - `AuditMixin`: Adds standard audit columns (created_at, created_by, updated_at, updated_by).
5.  A simple `User` model for tracking user information in audit columns.
6.  Polymorphic helper mixins (`HasStatusHistory`, `HasNotes`, `HasAttribution`, etc.)
    which provide a clean, reusable way to add relationships to the polymorphic
    metadata tables. Any model that can have a status history (like Thing or Location)
    can simply inherit from the `HasStatusHistory` mixin.
7.  An `AuditMixin` to add standard audit columns to tables.
"""

from sqlalchemy import (
    Column,
    DateTime,
    func,
    Integer,
    JSON,
    String,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column
from sqlalchemy_searchable import make_searchable
from sqlalchemy_continuum import make_versioned
import re


make_versioned()


class Base(DeclarativeBase):
    pass


make_searchable(Base.metadata)


def lexicon_term(foreignkeykw=None, **kw):
    """Create a SQLAlchemy mapped column for a self-referencing lexicon term.

    This helper function simplifies the creation of a string column that also
    acts as a foreign key to the 'term' column of the 'lexicon_term' table.
    It standardizes the column type to String(100) and sets the onupdate
    behavior to "CASCADE"."""

    fkw = foreignkeykw if foreignkeykw else {}

    return mapped_column(
        String(100),
        ForeignKey("lexicon_term.term", onupdate="CASCADE", **fkw),
        **kw,
    )


def pascal_to_snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class ReleaseMixin:
    """Mixin to add release status to a model."""

    @declared_attr
    def release_status(self):
        return lexicon_term(default="draft")


class AuditMixin:
    """Mixin to add standard audit columns to a model."""

    @declared_attr
    def created_at(self):
        return Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.timezone("UTC", func.now()),
        )

    # TODO: there is probably no need to store both the id and name of the user. We should decide which attribute
    #  included in the token payload is the most appropriate to use as the user identifier.
    # included "claims"
    # sub:  the subject of the token, which is a unique identifier for the user
    # name: the name of the user
    # email: the email address of the user
    # given_name: the first name of the user
    # preferred_username: the preferred username of the user
    # nickname: the nickname of the user
    @declared_attr
    def created_by_name(self):
        return Column(
            String(255),
            nullable=True,
        )

    @declared_attr
    def created_by_id(self):
        return Column(
            String(255),
            nullable=True,
        )

    @declared_attr
    def updated_by_name(self):
        return Column(
            String(255),
            nullable=True,
        )

    @declared_attr
    def updated_by_id(self):
        return Column(
            String(255),
            nullable=True,
        )


class AutoBaseMixin(AuditMixin):
    """Mixin to add automatic table naming and an auto-incrementing primary key."""

    @declared_attr
    def __tablename__(self):
        return pascal_to_snake(self.__name__)

    @declared_attr
    def id(self):
        return Column(Integer, primary_key=True, autoincrement=True)


class PropertiesMixin:
    """Mixin to add a JSONB properties column for storing additional attributes."""

    @declared_attr
    def properties(self):
        return Column(
            "properties",
            JSON,
            nullable=True,
            comment="JSONB column for storing additional properties",
        )


class User(Base):
    """Represents a user in the system."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    username: Mapped[str] = mapped_column(String(length=255), nullable=False)

    def __str__(self):
        return self.username


# ============= EOF =============================================
