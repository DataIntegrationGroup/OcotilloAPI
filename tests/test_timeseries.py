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

from sqlalchemy import func, select, cast, Interval
from sqlalchemy_utils.types.range import intervals

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
    assert result == 10.5, "Expected 2 values in the result"


#
#
def test_timescale_db_histogram():
    session = next(get_db_session())
    sql = func.histogram(GroundwaterLevelObservation.value, 0, 100, 10)
    result = session.execute(sql).scalar()
    assert result is not None, "Expected a result from the timescale DB histogram query"
    assert len(result) == 12, "Expected 11 buckets in the histogram"


def test_timescale_db_time_bucket():
    session = next(get_db_session())

    sql = (
        select(
            func.time_bucket(
                cast("1 hour", Interval), GroundwaterLevelObservation.timestamp
            ).label("bucket"),
            func.avg(GroundwaterLevelObservation.value).label("avg_value"),
        )
        .group_by("bucket")
        .order_by("bucket")
    )

    results = session.execute(sql).all()
    assert (
        results is not None
    ), "Expected a result from the timescale DB time bucket query"
    assert len(results) > 0, "Expected at least one result from the time bucket query"

    assert isinstance(
        results[0][0], datetime.datetime
    ), "Expected a datetime result from the time bucket query"
    assert isinstance(
        results[0][1], float
    ), "Expected a datetime result from the time bucket query"


# ============= EOF =============================================
