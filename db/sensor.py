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

from sqlalchemy import String, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import relationship, mapped_column, Mapped

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

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

    # --- Columns ---
    nma_pk_equipment: Mapped[str] = mapped_column(
        String(36),
        nullable=True,
        comment="Preserves the primary key (GlobalID) of the Equipment table from NMAquifer.",
    )
    # TODO: Is  a name field necessary? If it is, we should consider standardizing naming conventions.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sensor_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="A controlled vocabulary field to categorize the equipment (e.g., 'Pressure Transducer', 'Barometer', 'Data Logger', etc).",
    )
    model: Mapped[str] = mapped_column(
        String(50), nullable=True, comment="The specific model of the equipment."
    )
    serial_no: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        comment="The serial number of the equipment.",
    )
    # TODO: What data type should `pcn_number` be? Should it be a string or integer?
    pcn_number: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        comment="The Property Control Number (PCN) assigned to equipment for inventory tracking. This is only available for equipment owned by the NMBGMR.",
    )
    owner_agency: Mapped[str] = lexicon_term(
        nullable=True, comment="The agency or organization that owns the equipment."
    )
    sensor_status: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field to indicate the current status of the equipment (e.g., 'In Service', 'In Repair', 'Retired', 'Lost', etc).",
    )
    notes: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="A field for general notes or comments about the equipment.",
    )

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
