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

import pytest
from sqlalchemy import func, select, cast, Interval
from sqlalchemy_utils.types.range import intervals

from db.engine import get_db_session

# from db.timeseries import GroundwaterLevelObservation
from tests import client


@pytest.mark.skip
def test_add_sample():
    response = client.post(
        "/sample/add",
        json={
            "collection_timestamp": datetime.datetime.now().isoformat(),
            "collection_method": "manual",
            "well_id": 1,
        },
    )

    assert response.status_code == 201
    # data = response.json()
    # assert "id" in data, "Expected 'id' in response data"
    # assert data["collection_method"] == "manual", "Expected 'method' to be 'manual'"


@pytest.mark.skip
def test_add_sample_timeseries():
    response = client.post(
        "/sample/time_series/add",
        json={
            "name": "Test Sample Timeseries",
            "observed_property": "groundwater level",
            "unit": "ft",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert (
        data["observed_property"] == "groundwater level"
    ), "Expected 'observed_property' to be 'groundwater level'"


@pytest.mark.skip
def test_add_sample_observation():
    response = client.post(
        "/sample/time_series/observations/add",
        json=[
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "value": 10.5,
                "sample_id": 1,
                "time_series_id": 1,
            }
        ],
    )

    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list), "Expected a list of observations"
    assert len(data) == 1, "Expected one observation to be added"
    assert data[0]["value"] == 10.5, "Expected observation value to be 10.5"
    assert data[0]["sample_id"] == 1, "Expected observation sample_id to be 1"
    assert data[0]["time_series_id"] == 1, "Expected observation time_series_id to be 1"


@pytest.mark.skip
def test_sample_timeseries():
    response = client.get("/sample/time_series/well/1")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1, "Expected at least one timeseries for the well"


@pytest.mark.skip
def test_sample_timeseries_observations():
    response = client.get("/sample/time_series/1/observations")
    data = response.json()
    assert response.status_code == 200
    assert isinstance(data, list), "Expected a list of observations"
    assert len(data) == 1, "Expected at least one observation for the timeseries"


# def test_add_timeseries():
#     response = client.post(
#         "/timeseries",
#         json={
#             "name": "Test Timeseries",
#             "description": "A test timeseries for groundwater level.",
#             "type": "groundwater_level",
#         },
#     )
#     assert response.status_code == 201


# def test_add_well_timeseries():
#     response = client.post(
#         "/timeseries/well",
#         json={
#             "name": "Test Well Timeseries",
#             "description": "A test timeseries for well data.",
#             "well_id": 1,
#         },
#     )
#     assert response.status_code == 201
#
#
# def test_add_well_observations():
#     response = client.post(
#         "/timeseries/well/groundwater_level/observations",
#         json=[
#             {
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "value": 10.5,
#                 "description": "Test observation for well.",
#                 "timeseries_id": 2,
#             },
#             {
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "value": 11.5,
#                 "description": "Test observation for well.",
#                 "timeseries_id": 2,
#             },
#         ],
#     )
#     assert response.status_code == 201
#
#
# def test_timescale_db():
#
#     session = next(get_db_session())
#     sql = func.first(
#         GroundwaterLevelObservation.value, GroundwaterLevelObservation.timestamp
#     )
#     result = session.execute(sql).scalar()
#     assert result is not None, "Expected a result from the timescale DB query"
#     assert result == 10.5, "Expected 2 values in the result"
#
#
# #
# #
# def test_timescale_db_histogram():
#     session = next(get_db_session())
#     sql = func.histogram(GroundwaterLevelObservation.value, 0, 100, 10)
#     result = session.execute(sql).scalar()
#     assert result is not None, "Expected a result from the timescale DB histogram query"
#     assert len(result) == 12, "Expected 11 buckets in the histogram"
#
#
# def test_timescale_db_time_bucket():
#     session = next(get_db_session())
#
#     sql = (
#         select(
#             func.time_bucket(
#                 cast("1 hour", Interval), GroundwaterLevelObservation.timestamp
#             ).label("bucket"),
#             func.avg(GroundwaterLevelObservation.value).label("avg_value"),
#         )
#         .group_by("bucket")
#         .order_by("bucket")
#     )
#
#     results = session.execute(sql).all()
#     assert (
#         results is not None
#     ), "Expected a result from the timescale DB time bucket query"
#     assert len(results) > 0, "Expected at least one result from the time bucket query"
#
#     assert isinstance(
#         results[0][0], datetime.datetime
#     ), "Expected a datetime result from the time bucket query"
#     assert isinstance(
#         results[0][1], float
#     ), "Expected a datetime result from the time bucket query"
#

# ============= EOF =============================================
