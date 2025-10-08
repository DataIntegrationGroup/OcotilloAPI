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
SQLAlchemy model for the Sensor table.
"""
from datetime import datetime

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import relationship, mapped_column, Mapped

from db.base import Base, AutoBaseMixin, ReleaseMixin

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from db.deployment import Deployment
    from db.thing import Thing
    from db.observation import Observation


class Sensor(Base, AutoBaseMixin, ReleaseMixin):
    """
    The `Sensor` table serves as the central asset inventory for all physical hardware used for data collection.
    Its purpose is to track each unique piece of equipment as a distinct asset.

    This table is distinct from the `AnalysisMethod` table, as it deals exclusively with tangible, physical objects.

    This class can be extended to create specific sensor types.
    """

    # Define common attributes for sensors here
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=True)
    serial_no: Mapped[str] = mapped_column(String(50), nullable=True)
    datetime_installed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    datetime_removed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recording_interval: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(String(50), nullable=True)

    # --- Relationships ---
    # One-To-Many: A piece of Equipment can generate many Observations.
    observations: Mapped[List["Observation"]] = relationship(
        "Observation",
        back_populates="sensor",
    )

    # One-To-Many: A Sensor (or piece of equipment) can have many Deployments over its lifetime.
    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment", back_populates="sensor"
    )

    # --- Association Proxies ---
    # Proxy to directly access the Things where this Equipment has been deployed.
    things: AssociationProxy[List["Thing"]] = association_proxy("deployments", "thing")


# ============= EOF =============================================
