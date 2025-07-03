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

from sqlalchemy import func

from db import get_db_session
from db.timeseries import GroundwaterLevelObservation
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
                "timeseries_id": 2,
            },
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "value": 11.5,
                "description": "Test observation for well.",
                "timeseries_id": 2,
            },
        ],
    )
    assert response.status_code == 201


def test_timescale_db():

    session = next(get_db_session())
    sql = func.first(
        GroundwaterLevelObservation.value, GroundwaterLevelObservation.timestamp
    )
    result = session.execute(sql).scalar()
    assert result is not None, "Expected a result from the timescale DB query"
#
#
def test_timescale_db_histogram():
    session = next(get_db_session())
    sql = func.histogram(GroundwaterLevelObservation.value, 0, 100, 10)
    result = session.execute(sql).scalar()
    print("Histogram Result:", result)
    assert result is not None, "Expected a result from the timescale DB histogram query"


# ============= EOF =============================================
