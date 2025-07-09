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
from sqlalchemy import ForeignKey, Integer, Float
from sqlalchemy.orm import mapped_column, relationship

from db.base import AutoBaseMixin, Base
from db.observation.observation import ObservationMixin


class GroundwaterLevelObservation(Base, AutoBaseMixin, ObservationMixin):
    depth_to_water = mapped_column(
        Float,
        nullable=False,
        doc="Depth to water level in ft below measuring point",
        info={"unit": "ft"},
    )

    measuring_point_height = mapped_column(
        Float,
        nullable=False,
        doc="Height of the measuring point above the ground surface in ft",
        info={"unit": "ft"},
    )

    observation = relationship("Observation")


# ============= EOF =============================================
