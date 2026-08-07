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
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GeothermalWellResponse(BaseModel):
    """Read model for a geothermal well sourced from the legacy NM_Wells mirror.

    NOTE: This currently reads directly from the ``NMW_WellHeaders`` /
    ``NMW_WellLocations`` staging tables (see ``db/nmw_legacy.py``). Once the
    NM_Wells -> Ocotillo transform lands, these rows will be backed by the
    ``thing`` table and ``thing_id`` will be populated. Until then ``thing_id``
    is always ``None`` and ``well_data_id`` (legacy GUID) is the identifier.
    """

    model_config = ConfigDict(from_attributes=True)

    well_data_id: UUID  # legacy NMW_WellHeaders.WellDataID
    thing_id: int | None = None  # populated after NM_Wells -> thing transform

    api: str | None = None
    name: str | None = None  # cur_well_nam
    well_number: str | None = None  # cur_well_num
    well_class: str | None = None
    well_type: str | None = None
    status: str | None = None  # cur_status
    operator: str | None = None  # cur_operatr
    owner: str | None = None  # cur_owner
    total_depth: float | None = None
    completion_date: datetime | None = None  # compl_date
    has_geothermal_data: bool | None = None  # gthrm_exist

    # location, joined from NMW_WellLocations on WellDataID
    county: str | None = None
    state: str | None = None
    latitude: float | None = None  # lat_dd83
    longitude: float | None = None  # long_dd83


class CreateTemperatureProfile(BaseModel):
    """
    Pydantic model for creating a temperature profile.
    This model can be extended to include additional fields as needed.
    """

    well_id: int


class CreateTemperatureProfileObservation(BaseModel):
    """
    Pydantic model for creating a temperature profile observation.
    This model can be extended to include additional fields as needed.
    """

    temperature_profile_id: int
    depth: float
    depth_unit: str = "ft"  # Assuming depth unit is a string (e.g., 'm', 'ft')
    temperature: float
    temperature_unit: str = (
        "F"  # Assuming temperature unit is a string (e.g., 'C', 'F')
    )


class CreateGeothermalSampleSet(BaseModel):
    well_id: int
    name: str | None = None  # = mapped_column(String(128))
    klass: str | None = None  # = mapped_column(String(24))
    type: str | None = None  # = mapped_column(String(50))

    # SampleFm: # = mapped_column(String(50))
    # SampleLoc: # = mapped_column(String(128))
    # SampleDate: # = mapped_column(DateTime)
    # From_Depth: # = mapped_column(Float)
    # To_Depth: # = mapped_column(Float)
    # SmpDpUnt: # = mapped_column(String(16))
    # From_TVD: # = mapped_column(Float)
    # To_TVD: # = mapped_column(Float)
    # From_Elev: # = mapped_column(Float)
    # To_Elev: # = mapped_column(Float)

    porosity: int | None = None  # = mapped_column(Integer)
    permeability: int | None = None  # = mapped_column(Integer)
    density: int | None = None  # = mapped_column(Integer)

    dst_tests: bool | None = False  # = mapped_column(Boolean)
    thin_section: bool | None = False  # = mapped_column(Boolean)
    geochron: bool | None = False  # = mapped_column(Boolean)
    geochem: bool | None = False  # = mapped_column(Boolean)
    geothermal: bool | None = False  # = mapped_column(Boolean)
    wholerock: bool | None = False  # = mapped_column(Boolean)
    paleontology: bool | None = False  # = mapped_column(Boolean)
    # EnteredBy: # = mapped_column(String(4))
    # EntryDate: # = mapped_column(DateTime)
    notes: str | None = None  # = mapped_column(Text)


class CreateBottomHoleTemperatureHeader(BaseModel):
    sample_set_id: int

    drill_fluid: str | None = None
    fluid_salinity: float | None = None
    fluid_resistivity: float | None = None
    fluid_ph: float | None = None
    fluid_level: float | None = None
    fluid_viscosity: float | None = None
    fluid_loss: float | None = None

    notes: str | None = None


class CreateBottomHoleTemperature(BaseModel):
    """
    Pydantic model for creating a bottom hole temperature observation.
    This model can be extended to include additional fields as needed.
    """

    header_id: int
    # depth: float
    temperature: float
    # depth_unit: str  # Assuming depth unit is a string (e.g., 'm', 'ft')
    temperature_unit: str = (
        "F"  # Assuming temperature unit is a string (e.g., 'C', 'F')
    )


class CreateGeothermalInterval(BaseModel):
    """
    Pydantic model for creating a geothermal well interval.
    This model can be extended to include additional fields as needed.
    """

    sample_set_id: int
    top_depth: float
    bottom_depth: float
    depth_unit: str = "ft"


class CreateThermalConductivity(BaseModel):
    """
    Pydantic model for creating a thermal conductivity observation.
    This model can be extended to include additional fields as needed.
    """

    interval_id: int
    conductivity: float
    conductivity_unit: str = (
        "W/m·K"  # Assuming unit is a string (e.g., 'W/m·K', 'mW/m·K')
    )


class CreateHeatFlow(BaseModel):
    """
    Pydantic model for creating a geothermal heat flow observation.
    This model can be extended to include additional fields as needed.
    """

    interval_id: int
    gradient: float
    gradient_unit: str = (
        "mW/m²"  # Assuming gradient unit is a string (e.g., 'mW/m²', 'W/m²')
    )

    ka: float  # Assuming ka is thermal diffusivity
    ka_unit: str = "m²/s"  # Assuming ka unit is a string (e.g., 'm²/s', 'cm²/s')
    kpr: float  # Assuming kpr is thermal conductivity
    kpr_unit: str = "m²/s"  # Assuming kpr unit is a string (e.g., 'm²/s', 'cm²/s')
    q: float  # Heat flow value
    q_unit: str = "mW/m²"  # Assuming heat flow unit is a string (e.g., 'mW/m²', 'W/m²')
    pm: float  # Assuming pm is power measurement
    pm_unit: str = "mW/m²"  # Assuming pm unit is a string (e.g., 'mW/m²', 'W/m²')


# ============= EOF =============================================
