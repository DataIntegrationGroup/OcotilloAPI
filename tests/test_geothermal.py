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
import pytest

from tests import client


def test_geothermal_temperature_profile():
    """
    Test the geothermal temperature profile endpoint.
    This test should create a temperature profile and verify its creation.
    """

    # Create a sample temperature profile data

    response = client.post(
        "/geothermal/temperature_profile",
        json={
            "well_id": 1,
            # "name": "Test Profile",
            # "description": "A test geothermal temperature profile",
            # "depth": 1000,
            # "temperature": 50.0
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["well_id"] == 1
    # assert response.json()["name"] == "Test Profile"


def test_geothermal_temperature_profile_observation():
    """
    Test the geothermal temperature profile observation endpoint.
    This test should create a temperature profile observation and verify its creation.
    """

    # Create a sample temperature profile observation data
    response = client.post(
        "/geothermal/temperature_profile_observation",
        json={"temperature_profile_id": 1, "depth": 100, "temperature": 25.0},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["temperature_profile_id"] == 1
    assert data["depth"] == 100
    assert data["temperature"] == 25.0


def test_geothermal_sample_set():
    """
    Test the geothermal sample set endpoint.
    This test should create a sample set and verify its creation.
    """

    # Create a sample geothermal sample set data
    response = client.post(
        "/geothermal/sample_set",
        json={
            "well_id": 1,
            "name": "Test Sample Set",
            "note": "A test geothermal sample set",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["well_id"] == 1
    assert data["name"] == "Test Sample Set"


def test_geothermal_bottom_hole_temperature_header():
    """
    Test the geothermal bottom hole temperature header endpoint.
    This test should create a bottom hole temperature header and verify its creation.
    """

    # Create a sample bottom hole temperature header data
    response = client.post(
        "/geothermal/bottom_hole_temperature_header",
        json={
            "sample_set_id": 1,
            "drill_fluid": "mud",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["sample_set_id"] == 1


def test_geothermal_bottom_hole_temperature():
    """
    Test the geothermal bottom hole temperature endpoint.
    This test should create a bottom hole temperature record and verify its creation.
    """

    # Create a sample bottom hole temperature data
    response = client.post(
        "/geothermal/bottom_hole_temperature",
        json={"header_id": 1, "temperature": 60.0, "temperature_unit": "F"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["header_id"] == 1
    assert data["temperature"] == 60.0


def test_geothermal_interval():
    """
    Test the geothermal interval endpoint.
    This test should create a geothermal interval and verify its creation.
    """

    # Create a sample geothermal interval data
    response = client.post(
        "/geothermal/interval",
        json={
            "sample_set_id": 1,
            "top_depth": 100,
            "bottom_depth": 200,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["sample_set_id"] == 1
    assert data["top_depth"] == 100
    assert data["bottom_depth"] == 200


def test_geothermal_thermal_conductivity():
    """
    Test the geothermal thermal conductivity endpoint.
    This test should create a geothermal thermal conductivity record and verify its creation.
    """

    # Create a sample geothermal thermal conductivity data
    response = client.post(
        "/geothermal/thermal_conductivity",
        json={
            "interval_id": 1,
            "conductivity": 2.5,
            "conductivity_unit": "W/m·K",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["interval_id"] == 1
    assert data["conductivity"] == 2.5
    assert data["conductivity_unit"] == "W/m·K"


def test_geothermal_heatflow():
    """
    Test the geothermal heat flow endpoint.
    This test should create a geothermal heat flow record and verify its creation.
    """

    # Create a sample geothermal heat flow data
    response = client.post(
        "/geothermal/heat_flow",
        json={
            "interval_id": 1,
            "gradient": 0.01,
            "gradient_unit": "mW/m²",
            "ka": 0.001,
            "ka_unit": "m²/s",  # Assuming ka is thermal diffusivity
            "kpr": 0.002,
            "kpr_unit": "m²/s",  # Assuming kpr is thermal conductivity
            "q": 100.0,  # Heat flow value
            "q_unit": "mW/m²",  # Assuming heat flow unit is mW/m²
            "pm": 0.003,  # Assuming pm is some parameter related to heat flow
            "pm_unit": "m²/s",  # Assuming pm is a unit related to heat flow
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["interval_id"] == 1
    assert data["gradient"] == 0.01


# ============= EOF =============================================
