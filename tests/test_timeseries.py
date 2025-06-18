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
import datetime

from tests import client


def test_add_well_timeseries():
    response = client.post(
        "/timeseries/well",
        json={
            "name": "Test Well Timeseries",
            "description": "A test timeseries for well data.",
            "well_id": 1,
        },
    )
    assert response.status_code == 201


def test_add_well_observations():
    response = client.post(
        "/timeseries/well/groundwater_level/observations",
        json=[
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "value": 10.5,
                "description": "Test observation for well.",
                "timeseries_id": 1,
            },
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "value": 11.5,
                "description": "Test observation for well.",
                "timeseries_id": 1,
            },
        ],
    )
    assert response.status_code == 201


# ============= EOF =============================================
