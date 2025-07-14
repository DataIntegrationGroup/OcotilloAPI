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
from sqlalchemy import Integer, ForeignKey, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, mapped_column, declared_attr

from db import lexicon_term
from db.base import AutoBaseMixin, Base, ReleaseMixin


class ThingChildMixin:
    @declared_attr
    def thing_id(self):
        return mapped_column(
            Integer,
            ForeignKey("thing.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )

    @declared_attr
    def thing(self):
        return relationship("Thing")


class Thing(Base, AutoBaseMixin, ReleaseMixin):
    name = mapped_column(String(255), nullable=False)

    asset_associations = relationship(
        "AssetThingAssociation",
        back_populates="thing",
        cascade="all, delete-orphan",
    )
    assets = association_proxy("asset_associations", "asset")


class ThingIdLink(Base, AutoBaseMixin):
    """
    Represents a link associated with a Thing.
    """

    thing_id = mapped_column(Integer, ForeignKey("thing.id", ondelete="CASCADE"))
    relation = lexicon_term(nullable=False)
    alternate_id = mapped_column(String(100), nullable=False)
    alternate_organization = lexicon_term(nullable=False)

    # thing = relationship("Thing", back_populates="links")


# ============= EOF =============================================
