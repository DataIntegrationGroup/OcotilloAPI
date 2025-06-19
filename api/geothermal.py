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
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db import get_db_session, adder
from db.geothermal import (
    GeothermalTemperatureProfile,
    GeothermalTemperatureProfileObservation,
    GeothermalBottomHoleTemperature,
    GeothermalWellInterval,
    GeothermalHeatFlow,
    GeothermalThermalConductivity,
    GeothermalSampleSet,
    GeothermalBottomHoleTemperatureHeader,
)
from schemas.create.geothermal import CreateTemperatureProfile, CreateTemperatureProfileObservation, \
    CreateGeothermalSampleSet, CreateBottomHoleTemperatureHeader, CreateBottomHoleTemperature, CreateGeothermalInterval, \
    CreateThermalConductivity, CreateHeatFlow

router = APIRouter(prefix="/geothermal", tags=["geothermal"])


@router.post("/sample_set", status_code=status.HTTP_201_CREATED)
async def add_geothermal_sample_set(
    sample_set_data: CreateGeothermalSampleSet,  # Replace with appropriate schema
    session: Session = Depends(get_db_session),
):
    """
    Add a new geothermal sample set.
    """
    # Assuming you have a model for GeothermalSampleSet
    return adder(session, GeothermalSampleSet, sample_set_data)


@router.post("/bottom_hole_temperature_header", status_code=status.HTTP_201_CREATED)
async def add_bottom_hole_temperature_header(
    bottom_hole_temperature_header_data: CreateBottomHoleTemperatureHeader,
    session: Session = Depends(get_db_session),
):
    """
    Add a new bottom hole temperature header.
    """
    # Assuming you have a model for GeothermalBottomHoleTemperatureHeader
    return adder(
        session,
        GeothermalBottomHoleTemperatureHeader,
        bottom_hole_temperature_header_data,
    )


@router.post("/temperature_profile", status_code=status.HTTP_201_CREATED)
async def add_temperature_profile(
    temperature_profile_data: CreateTemperatureProfile,
    session: Session = Depends(get_db_session),
):
    """
    Add a new temperature profile.
    """
    return adder(session, GeothermalTemperatureProfile, temperature_profile_data)


@router.post("/temperature_profile_observation", status_code=status.HTTP_201_CREATED)
async def add_temperature_profile_observation(
    temperature_profile_observation_data: CreateTemperatureProfileObservation,
    session: Session = Depends(get_db_session),
):
    """
    Add a new temperature profile observation.
    """
    return adder(
        session,
        GeothermalTemperatureProfileObservation,
        temperature_profile_observation_data,
    )


@router.post("/bottom_hole_temperature", status_code=status.HTTP_201_CREATED)
async def add_bottom_hole_temperature(
    bottom_hole_temperature_data: CreateBottomHoleTemperature,
    session: Session = Depends(get_db_session),
):
    """
    Add a new bottom hole temperature.
    """
    return adder(
        session,
        GeothermalBottomHoleTemperature,  # Assuming this is the correct model
        bottom_hole_temperature_data,
    )


@router.post("/interval", status_code=status.HTTP_201_CREATED)
async def add_geothermal_interval(
    interval_data: CreateGeothermalInterval,  # Replace with appropriate schema
    session: Session = Depends(get_db_session),
):
    """
    Add a new geothermal interval.
    """
    # Assuming you have a model for GeothermalInterval
    return adder(session, GeothermalWellInterval, interval_data)


@router.post("/thermal_conductivity", status_code=status.HTTP_201_CREATED)
async def add_thermal_conductivity(
    thermal_conductivity_data: CreateThermalConductivity,  # Replace with appropriate schema
    session: Session = Depends(get_db_session),
):
    """
    Add a new geothermal thermal conductivity.
    """
    # Assuming you have a model for GeothermalThermalConductivity
    return adder(session, GeothermalThermalConductivity, thermal_conductivity_data)


@router.post("/heat_flow", status_code=status.HTTP_201_CREATED)
async def add_heat_flow(
    heat_flow_data: CreateHeatFlow,
    session: Session = Depends(get_db_session),
):
    """
    Add a new geothermal heat flow.
    """
    # Assuming you have a model for GeothermalHeatFlow
    return adder(session, GeothermalHeatFlow, heat_flow_data)


# ============= EOF =============================================
