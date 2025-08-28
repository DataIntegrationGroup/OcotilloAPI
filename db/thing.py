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
from xmlrpc.client import Boolean

from sqlalchemy import Integer, ForeignKey, String, Column, Float
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy_utils import TSVectorType

from db import lexicon_term
from db.base import AutoBaseMixin, Base, ReleaseMixin


class Thing(Base, AutoBaseMixin, ReleaseMixin):
    name = mapped_column(String(255), nullable=False)
    description = mapped_column(String(500))
    thing_type = lexicon_term(nullable=True)
    spring_type = lexicon_term(nullable=True)

    asset_associations = relationship(
        "AssetThingAssociation",
        back_populates="thing",
        overlaps="things",
        cascade="all, delete-orphan",
    )
    assets = association_proxy("asset_associations", "asset")

    location_associations = relationship(
        "LocationThingAssociation",
        back_populates="thing",
        overlaps="location",
        cascade="all, delete-orphan",
        order_by="LocationThingAssociation.effective_start.desc()",
    )
    locations = association_proxy("location_associations", "location")

    contact_associations = relationship(
        "ThingContactAssociation",
        back_populates="thing",
        overlaps="contacts",
        cascade="all, delete-orphan",
    )
    contacts = association_proxy("contact_associations", "contact")

    # Well fields
    well_depth = Column(
        Float,
        nullable=True,
        info={"unit": "feet below ground surface"},
    )
    hole_depth = Column(
        Float, nullable=True, info={"unit": "feet below ground surface"}
    )
    well_type = lexicon_term()
    # e.g., "Production", "Observation", etc.
    #
    well_casing_diameter = Column(Float, info={"unit": "inches"})
    well_casing_depth = Column(Float, info={"unit": "feet below ground surface"})
    well_casing_description = Column(String(50))

    well_construction_notes = Column(String(250))

    # Spring fields

    search_vector = Column(
        TSVectorType(
            "name", "well_construction_notes", "well_type", "well_casing_description"
        )
    )

    samples = relationship(
        "Sample", back_populates="thing", cascade="all, delete-orphan", uselist=True
    )


class ThingIdLink(Base, AutoBaseMixin):
    """
    Represents a link associated with a Thing.
    """

    thing_id = mapped_column(Integer, ForeignKey("thing.id", ondelete="CASCADE"))
    relation = lexicon_term(nullable=False)
    alternate_id = mapped_column(String(100), nullable=False)
    alternate_organization = lexicon_term(nullable=False)

    thing = relationship("Thing", backref="links")


class WellScreen(Base, AutoBaseMixin):
    thing_id = Column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    screen_depth_top = Column(
        Float, nullable=False, info={"unit": "feet below ground surface"}
    )
    screen_depth_bottom = Column(
        Float, nullable=False, info={"unit": "feet below ground surface"}
    )
    screen_type = lexicon_term()  # e.g., "PVC", "Steel", etc.

    screen_description = Column(
        String(1000), nullable=True, info={"unit": "description of the screen"}
    )
    # Define a relationship to well if needed
    # well = relationship("Well")


# TODO: this could be the model used to handle AMP monitoring
# class FieldSamplingAdministation(Base, AutoBaseMixin):
#     # the thing being monitored
#     thing_id: Mapped[int] = mapped_column(Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False)
#
#     monitoring_frequency: Mapped[str] = mapped_column(lexicon_term(), nullable=False)
#     well_logger_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
#     monitor_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
#     sample_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)


# ============= EOF =============================================
