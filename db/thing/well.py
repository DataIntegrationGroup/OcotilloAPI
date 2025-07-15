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
from sqlalchemy import Column, Integer, ForeignKey, String, Float
from sqlalchemy.orm import relationship
from sqlalchemy_utils import TSVectorType

from db import lexicon_term
from db.base import Base, AutoBaseMixin
from db.thing.thing import ThingChildMixin


class WellThing(Base, AutoBaseMixin, ThingChildMixin):

    # location_id = Column(
    #     Integer, ForeignKey("location.id", ondelete="CASCADE"), nullable=False
    # )
    #
    # ose_pod_id = Column(String(50), nullable=True)
    # api_id = Column(String(50), nullable=True, default="")  # API well number
    # usgs_id = Column(String(50), nullable=True)  # USGS well number
    #
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
    casing_diameter = Column(Float, info={"unit": "inches"})
    casing_depth = Column(Float, info={"unit": "feet below ground surface"})
    casing_description = Column(String(50))

    construction_notes = Column(String(250))

    search_vector = Column(
        TSVectorType("construction_notes", "well_type", "casing_description")
    )
    # formation_zone = Column(String(100), ForeignKey("lexicon_term.term"), nullable=True)
    #
    # location = relationship("SampleLocation", backref="well", uselist=False)
    #
    # search_vector = Column(
    #     TSVectorType(
    #         "ose_pod_id",
    #         "api_id",
    #         "usgs_id",
    #         "well_type",
    #         "formation_zone",
    #         "construction_notes",
    #     )
    # )


class WellScreen(Base, AutoBaseMixin):
    well_id = Column(
        Integer, ForeignKey("well_thing.id", ondelete="CASCADE"), nullable=False
    )
    screen_depth_top = Column(
        Float, nullable=False, info={"unit": "feet below ground surface"}
    )
    screen_depth_bottom = Column(
        Float, nullable=False, info={"unit": "feet below ground surface"}
    )
    screen_type = lexicon_term()  # e.g., "PVC", "Steel", etc.

    # Define a relationship to well if needed
    # well = relationship("Well")


# ============= EOF =============================================
