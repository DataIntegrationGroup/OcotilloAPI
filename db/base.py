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
from sqlalchemy import (
    Column,
    DateTime,
    func,
    Integer,
    JSON,
    String,
    Boolean,
    Text,
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


def lexicon_term(**kw):
    return mapped_column(String(100), ForeignKey("lexicon_term.term"), **kw)


def pascal_to_snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class ReleaseMixin:
    @declared_attr
    def release_status(self):
        return lexicon_term(default="draft")


class AuditMixin:
    @declared_attr
    def created_at(self):
        return Column(DateTime, nullable=False, server_default=func.now())


class AutoBaseMixin(AuditMixin):
    @declared_attr
    def __tablename__(self):
        return pascal_to_snake(self.__name__)

    @declared_attr
    def id(self):
        return Column(Integer, primary_key=True, autoincrement=True)


class PropertiesMixin:
    @declared_attr
    def properties(self):
        return Column(
            "properties",
            JSON,
            nullable=True,
            comment="JSONB column for storing additional properties",
        )


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    username: Mapped[str] = mapped_column(String(length=255), nullable=False)
    password: Mapped[str] = mapped_column(String(length=255), nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __str__(self):
        return self.username


# ============= EOF =============================================
