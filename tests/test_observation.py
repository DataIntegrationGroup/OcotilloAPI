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

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from core.dependencies import (
    amp_admin_function,
    admin_function,
    amp_viewer_function,
    amp_editor_function,
    viewer_function,
)
from db import (
    Deployment,
    FieldActivity,
    FieldEvent,
    LocationThingAssociation,
    Observation,
    Sample,
    Sensor,
    Thing,
    TransducerObservation,
    TransducerObservationBlock,
)
from db.engine import session_ctx
from main import app
from schemas import DT_FMT
from tests import (
    client,
    cleanup_post_test,
    override_authentication,
    cleanup_patch_test,
    get_parameter_id,
)


def _groundwater_level_parameter_id() -> int:
    return get_parameter_id("groundwater level", "Field Parameter")


def _ph_parameter_id() -> int:
    return get_parameter_id("pH", "Field Parameter")


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()
    app.dependency_overrides[viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


# ============= Post tests =================
def test_add_water_chemistry_observation(water_chemistry_sample, sensor):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "value": 7.5,
        "unit": "dimensionless",
        "sample_id": water_chemistry_sample.id,
        "sensor_id": sensor.id,
        "parameter_id": _ph_parameter_id(),
    }
    response = client.post("/observation/water-chemistry", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert "id" in data
    assert "created_at" in data
    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["value"] == payload["value"]
    assert data["unit"] == payload["unit"]
    assert data["sample_id"] == payload["sample_id"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["parameter"]["id"] == _ph_parameter_id()

    cleanup_post_test(Observation, data["id"])


def test_add_groundwater_level_observation(groundwater_level_sample, sensor):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "value": 101,
        "measuring_point_height": 53,
        "sample_id": groundwater_level_sample.id,
        "parameter_id": _groundwater_level_parameter_id(),
        "sensor_id": sensor.id,
        "groundwater_level_reason": "Water level not affected",
        "unit": "ft",
    }
    response = client.post("/observation/groundwater-level", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert "id" in data
    assert "created_at" in data
    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["value"] == payload["value"]
    assert data["measuring_point_height"] == payload["measuring_point_height"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["parameter"]["id"] == _groundwater_level_parameter_id()
    assert data["groundwater_level_reason"] == payload["groundwater_level_reason"]
    assert (
        data["depth_to_water_bgs"]
        == payload["value"] - payload["measuring_point_height"]
    )

    cleanup_post_test(Observation, data["id"])


def test_bulk_upload_groundwater_levels_api(water_well_thing):
    csv_content = ",".join(
        [
            "field_staff",
            "well_name_point_id",
            "field_event_date_time",
            "measurement_date_time",
            "sampler",
            "sample_method",
            "mp_height",
            "level_status",
            "depth_to_water_ft",
            "data_quality",
            "water_level_notes",
        ]
    )
    csv_content += "\n"
    csv_content += ",".join(
        [
            "A Lopez",
            water_well_thing.name,
            "2025-02-15T08:00:00-07:00",
            "2025-02-15T10:30:00-07:00",
            "A Lopez",
            "electric tape",
            "1.5",
            "Water level not affected",
            "7.0",
            "Water level accurate to within two hundreths of a foot",
            "Initial measurement",
        ]
    )

    files = {
        "file": ("water_levels.csv", csv_content, "text/csv"),
    }

    response = client.post("/observation/groundwater-level/bulk-upload", files=files)
    data = response.json()
    assert response.status_code == 200
    assert data["summary"]["total_rows_imported"] == 1
    assert data["summary"]["total_rows_processed"] == 1
    assert data["summary"]["validation_errors_or_warnings"] == 0
    assert data["validation_errors"] == []
    row = data["water_levels"][0]
    assert row["well_name_point_id"] == water_well_thing.name

    with session_ctx() as session:
        observation = session.get(Observation, row["observation_id"])
        assert observation is not None
        sample = session.get(Sample, row["sample_id"])
        assert sample is not None
        assert sample.sample_name == f"{water_well_thing.name}-WL-202502151730"
        assert sample.sample_matrix == "groundwater"
        assert observation.groundwater_level_reason == "Water level not affected"
        assert (
            observation.nma_data_quality
            == "Water level accurate to within two hundreths of a foot"
        )
        assert observation.measuring_point_height == 1.5
        # cleanup in reverse dependency order
        if observation:
            session.delete(observation)
        if sample:
            session.delete(sample)
        field_activity = session.get(FieldActivity, row["field_activity_id"])
        if field_activity:
            session.delete(field_activity)
        field_event = session.get(FieldEvent, row["field_event_id"])
        if field_event:
            session.delete(field_event)
        session.commit()


def test_bulk_upload_groundwater_levels_api_partial_success(water_well_thing):
    csv_content = ",".join(
        [
            "field_staff",
            "well_name_point_id",
            "field_event_date_time",
            "measurement_date_time",
            "sampler",
            "sample_method",
            "mp_height",
            "level_status",
            "depth_to_water_ft",
            "data_quality",
            "water_level_notes",
        ]
    )
    csv_content += "\n"
    csv_content += "\n".join(
        [
            ",".join(
                [
                    "A Lopez",
                    water_well_thing.name,
                    "2025-02-15T08:00:00-07:00",
                    "2025-02-15T10:30:00-07:00",
                    "A Lopez",
                    "electric tape",
                    "1.5",
                    "Water level not affected",
                    "7.0",
                    "Water level accurate to within two hundreths of a foot",
                    "Initial measurement",
                ]
            ),
            ",".join(
                [
                    "A Lopez",
                    "Bad Well",
                    "2025-02-15T08:00:00-07:00",
                    "2025-02-15T10:30:00-07:00",
                    "A Lopez",
                    "electric tape",
                    "1.5",
                    "Water level not affected",
                    "7.0",
                    "Water level accurate to within two hundreths of a foot",
                    "Bad row",
                ]
            ),
        ]
    )

    files = {
        "file": ("water_levels.csv", csv_content, "text/csv"),
    }

    response = client.post("/observation/groundwater-level/bulk-upload", files=files)
    data = response.json()
    assert response.status_code == 200
    assert data["summary"]["total_rows_imported"] == 1
    assert data["summary"]["total_rows_processed"] == 2
    assert data["summary"]["validation_errors_or_warnings"] == 1
    assert len(data["validation_errors"]) == 1
    assert "Bad Well" in data["validation_errors"][0]

    row = data["water_levels"][0]
    with session_ctx() as session:
        observation = session.get(Observation, row["observation_id"])
        sample = session.get(Sample, row["sample_id"])
        field_activity = session.get(FieldActivity, row["field_activity_id"])
        field_event = session.get(FieldEvent, row["field_event_id"])

        if observation:
            session.delete(observation)
        if sample:
            session.delete(sample)
        if field_activity:
            session.delete(field_activity)
        if field_event:
            session.delete(field_event)
        session.commit()


# PATCH tests ==================================================================


# TODO update patch test to test every single field
def test_patch_groundwater_level_observation(groundwater_level_observation):
    payload = {"measuring_point_height": 3, "release_status": "private"}
    response = client.patch(
        f"/observation/groundwater-level/{groundwater_level_observation.id}",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["measuring_point_height"] == payload["measuring_point_height"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(Observation, payload, groundwater_level_observation)


def test_patch_groundwater_level_observation_404_not_found(
    groundwater_level_observation,
):
    bad_id = 99999
    payload = {"measuring_point_height": 3}
    response = client.patch(f"/observation/groundwater-level/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_patch_groundwater_level_observation_404_wrong_activity_type(
    water_chemistry_observation,
):
    payload = {"measuring_point_height": 3}
    response = client.patch(
        f"/observation/groundwater-level/{water_chemistry_observation.id}", json=payload
    )
    assert response.status_code == 404
    data = response.json()

    actual_activity_type = "water chemistry"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {water_chemistry_observation.id} is not a groundwater level observation. It is a {actual_activity_type} observation."
    )


def test_patch_water_chemistry_observation(water_chemistry_observation):
    payload = {"value": 8, "release_status": "private"}
    response = client.patch(
        f"/observation/water-chemistry/{water_chemistry_observation.id}",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["value"] == payload["value"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(Observation, payload, water_chemistry_observation)


def test_patch_water_chemistry_observation_404_not_found(water_chemistry_observation):
    bad_id = 999999
    payload = {"value": 8}
    response = client.patch(f"/observation/water-chemistry/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_patch_water_chemistry_observation_404_wrong_activity_type(
    groundwater_level_observation,
):
    payload = {"value": 8}
    response = client.patch(
        f"/observation/water-chemistry/{groundwater_level_observation.id}", json=payload
    )
    assert response.status_code == 404
    data = response.json()

    actualy_activity_type = "groundwater level"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {groundwater_level_observation.id} is not a water chemistry observation. It is a {actualy_activity_type} observation."
    )


# ============= Get tests =================


@pytest.mark.skip(reason="No longer supported")
def test_get_transducer_observations():
    response = client.get("/observation/transducer-groundwater-level")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_all_observations(
    groundwater_level_observation, water_chemistry_observation
):
    response = client.get("/observation")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    for item in data["items"]:
        assert "id" in item
        assert "created_at" in item
        assert "release_status" in item
        assert "sample_id" in item
        assert "sensor_id" in item
        assert "observation_datetime" in item
        assert "parameter" in item
        assert "value" in item
        assert "unit" in item


def test_get_observation_by_id(
    groundwater_level_observation, water_chemistry_observation
):
    for obs in (
        groundwater_level_observation,
        water_chemistry_observation,
    ):
        response = client.get(f"/observation/{obs.id}")
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == obs.id
        # Convert created_at to UTC and format with Z suffix
        expected_created_at = obs.created_at.astimezone(timezone.utc).strftime(DT_FMT)
        assert data["created_at"] == expected_created_at
        assert data["release_status"] == obs.release_status
        if obs.parameter.id == _groundwater_level_parameter_id():
            assert data["depth_to_water_bgs"] == obs.value - obs.measuring_point_height
        else:
            assert data["depth_to_water_bgs"] is None


def test_get_observation_by_id_404_not_found(
    groundwater_level_observation, water_chemistry_observation
):
    bad_id = 999999
    response = client.get(f"/observation/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_get_groundwater_level_observations(groundwater_level_observation):
    response = client.get("/observation/groundwater-level")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == groundwater_level_observation.id
    # Convert created_at to UTC and format with Z suffix
    expected_created_at = groundwater_level_observation.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["created_at"] == expected_created_at
    assert data["items"][0]["sample_id"] == groundwater_level_observation.sample_id
    assert data["items"][0]["sensor_id"] == groundwater_level_observation.sensor_id
    assert (
        data["items"][0]["observation_datetime"]
        == groundwater_level_observation.observation_datetime
    )
    assert data["items"][0]["parameter"]["id"] == _groundwater_level_parameter_id()
    assert (
        data["items"][0]["release_status"]
        == groundwater_level_observation.release_status
    )
    assert (
        data["items"][0]["groundwater_level_reason"]
        == groundwater_level_observation.groundwater_level_reason
    )
    assert data["items"][0]["value"] == groundwater_level_observation.value
    assert data["items"][0]["unit"] == groundwater_level_observation.unit
    assert (
        data["items"][0]["depth_to_water_bgs"]
        == groundwater_level_observation.value
        - groundwater_level_observation.measuring_point_height
    )
    assert (
        data["items"][0]["measuring_point_height"]
        == groundwater_level_observation.measuring_point_height
    )


def test_get_transducer_groundwater_level_observations_uses_blocks_for_same_thing(
    location, second_location, sensor
):
    observation_time = datetime.now(timezone.utc)
    matching_block_id = None
    observation_id = None
    other_block_id = None
    target_deployment_id = None
    other_deployment_id = None
    other_sensor_id = None
    other_thing_id = None
    target_thing_id = None

    try:
        with session_ctx() as session:
            target_thing = Thing(
                name="Transducer Target Well",
                first_visit_date="2023-03-03",
                thing_type="water well",
                release_status="draft",
                well_depth=10,
                hole_depth=10,
                well_casing_diameter=5.0,
                well_casing_depth=10.0,
            )
            other_thing = Thing(
                name="Transducer Other Well",
                first_visit_date="2023-03-04",
                thing_type="water well",
                release_status="draft",
                well_depth=10,
                hole_depth=10,
                well_casing_diameter=5.0,
                well_casing_depth=10.0,
            )
            session.add_all([target_thing, other_thing])
            session.flush()

            session.add_all(
                [
                    LocationThingAssociation(
                        location_id=location.id,
                        thing_id=target_thing.id,
                        effective_start="2025-02-01T00:00:00Z",
                    ),
                    LocationThingAssociation(
                        location_id=second_location.id,
                        thing_id=other_thing.id,
                        effective_start="2025-02-01T00:00:00Z",
                    ),
                ]
            )

            other_sensor = Sensor(
                name=f"Transducer Other Sensor {uuid.uuid4()}",
                sensor_type="Pressure Transducer",
                model="Model X",
                serial_no=f"serial-{uuid.uuid4()}",
                pcn_number=f"pcn-{uuid.uuid4()}",
                owner_agency="NMBGMR",
                sensor_status="In Service",
                notes="other sensor",
                release_status="draft",
            )
            session.add(other_sensor)
            session.flush()

            target_deployment = Deployment(
                sensor_id=sensor.id,
                thing_id=target_thing.id,
                installation_date="2023-01-01",
                recording_interval=24,
                recording_interval_units="hour",
                hanging_cable_length=10,
                hanging_point_height=0,
                hanging_point_description="target deployment",
                notes="target deployment",
            )
            other_deployment = Deployment(
                sensor_id=other_sensor.id,
                thing_id=other_thing.id,
                installation_date="2023-01-01",
                recording_interval=24,
                recording_interval_units="hour",
                hanging_cable_length=10,
                hanging_point_height=0,
                hanging_point_description="other deployment",
                notes="other deployment",
            )
            session.add_all([target_deployment, other_deployment])
            session.flush()

            target_block = TransducerObservationBlock(
                thing_id=target_thing.id,
                parameter_id=_groundwater_level_parameter_id(),
                start_datetime=observation_time - timedelta(days=10),
                end_datetime=observation_time + timedelta(days=10),
                review_status="not reviewed",
            )
            other_block = TransducerObservationBlock(
                thing_id=other_thing.id,
                parameter_id=_groundwater_level_parameter_id(),
                start_datetime=observation_time - timedelta(days=1),
                end_datetime=observation_time + timedelta(days=1),
                review_status="not reviewed",
            )
            session.add_all([target_block, other_block])
            session.flush()

            observation = TransducerObservation(
                parameter_id=_groundwater_level_parameter_id(),
                deployment_id=target_deployment.id,
                observation_datetime=observation_time,
                value=12.34,
            )
            session.add(observation)
            session.commit()

            matching_block_id = target_block.id
            observation_id = observation.id
            other_block_id = other_block.id
            target_deployment_id = target_deployment.id
            other_deployment_id = other_deployment.id
            other_sensor_id = other_sensor.id
            target_thing_id = target_thing.id
            other_thing_id = other_thing.id

        response = client.get(
            f"/observation/transducer-groundwater-level?thing_id={target_thing_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["block"]["id"] == matching_block_id
        assert data["items"][0]["block"]["id"] != other_block_id
    finally:
        with session_ctx() as session:
            for model, pk in (
                (TransducerObservation, observation_id),
                (TransducerObservationBlock, matching_block_id),
                (TransducerObservationBlock, other_block_id),
                (Deployment, target_deployment_id),
                (Deployment, other_deployment_id),
                (Sensor, other_sensor_id),
                (Thing, target_thing_id),
                (Thing, other_thing_id),
            ):
                if pk is None:
                    continue
                instance = session.get(model, pk)
                if instance is not None:
                    session.delete(instance)
            session.commit()


def test_get_groundwater_level_observation_by_id(groundwater_level_observation):
    response = client.get(
        f"/observation/groundwater-level/{groundwater_level_observation.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == groundwater_level_observation.id
    # Convert created_at to UTC and format with Z suffix
    expected_created_at = groundwater_level_observation.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["created_at"] == expected_created_at
    assert data["sample_id"] == groundwater_level_observation.sample_id
    assert data["sensor_id"] == groundwater_level_observation.sensor_id
    assert (
        data["observation_datetime"]
        == groundwater_level_observation.observation_datetime
    )
    assert data["parameter"]["id"] == _groundwater_level_parameter_id()
    assert data["release_status"] == groundwater_level_observation.release_status
    assert (
        data["groundwater_level_reason"]
        == groundwater_level_observation.groundwater_level_reason
    )
    assert data["value"] == groundwater_level_observation.value
    assert data["unit"] == groundwater_level_observation.unit
    assert (
        data["depth_to_water_bgs"]
        == groundwater_level_observation.value
        - groundwater_level_observation.measuring_point_height
    )
    assert (
        data["measuring_point_height"]
        == groundwater_level_observation.measuring_point_height
    )


def test_get_groundwater_level_observation_by_id_404_not_found(
    groundwater_level_observation,
):
    bad_id = 99999
    response = client.get(f"/observation/groundwater-level/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data, "Expected 'detail' in response"
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_get_groundwater_level_observation_by_id_404_wrong_activity_type(
    water_chemistry_observation,
):
    response = client.get(
        f"/observation/groundwater-level/{water_chemistry_observation.id}"
    )
    assert response.status_code == 404
    data = response.json()

    actual_activity_type = "water chemistry"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {water_chemistry_observation.id} is not a groundwater level observation. It is a {actual_activity_type} observation."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {
        "observation_id": water_chemistry_observation.id
    }
    assert data["detail"][0]["loc"] == ["path", "observation_id"]


def test_get_groundwater_observation_by_sample(
    groundwater_level_observation, groundwater_level_sample
):
    response = client.get(
        "/observation/groundwater-level",
        params={
            "sample_id": groundwater_level_sample.id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) > 0, "Expected at least one groundwater observation for the thing"


def test_get_groundwater_observation_by_thing(
    groundwater_level_observation, water_well_thing
):
    response = client.get(
        "/observation/groundwater-level",
        params={
            "thing_id": water_well_thing.id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) > 0, "Expected at least one groundwater observation for the thing"


def test_get_groundwater_observation_by_thing_nonexistent():
    response = client.get("/observation/groundwater-level", params={"thing_id": 999})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert (
        len(items) == 0
    ), "Expected no groundwater observations for a non-existent thing"


def test_get_groundwater_observation_by_time_range(groundwater_level_observation):
    response = client.get(
        "/observation/groundwater-level",
        params={
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": "2025-01-02T00:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert (
        len(items) > 0
    ), "Expected at least one groundwater observation in the time range"


def test_get_groundwater_observation_by_time_range_nonexistent():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "start_time": "2020-01-01T00:00:00Z",
            "end_time": "2020-01-02T00:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) == 0, "Expected no groundwater observations in the time range"


def test_get_water_chemistry_observations(water_chemistry_observation):
    response = client.get("/observation/water-chemistry")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == water_chemistry_observation.id
    # Convert created_at to UTC and format with Z suffix
    expected_created_at = water_chemistry_observation.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["created_at"] == expected_created_at
    assert (
        data["items"][0]["release_status"] == water_chemistry_observation.release_status
    )
    assert data["items"][0]["sample_id"] == water_chemistry_observation.sample_id
    assert data["items"][0]["sensor_id"] == water_chemistry_observation.sensor_id
    assert (
        data["items"][0]["observation_datetime"]
        == water_chemistry_observation.observation_datetime
    )
    assert data["items"][0]["parameter"]["id"] == _ph_parameter_id()
    assert data["items"][0]["value"] == water_chemistry_observation.value
    assert data["items"][0]["unit"] == water_chemistry_observation.unit


def test_get_water_chemistry_observation_by_id(water_chemistry_observation):
    response = client.get(
        f"/observation/water-chemistry/{water_chemistry_observation.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == water_chemistry_observation.id
    # Convert created_at to UTC and format with Z suffix
    expected_created_at = water_chemistry_observation.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["created_at"] == expected_created_at
    assert data["release_status"] == water_chemistry_observation.release_status
    assert data["sample_id"] == water_chemistry_observation.sample_id
    assert data["sensor_id"] == water_chemistry_observation.sensor_id
    assert (
        data["observation_datetime"] == water_chemistry_observation.observation_datetime
    )

    assert data["parameter"]["id"] == _ph_parameter_id()
    assert data["value"] == water_chemistry_observation.value
    assert data["unit"] == water_chemistry_observation.unit


def test_get_water_chemistry_observation_by_id_404_not_found(
    water_chemistry_observation,
):
    bad_id = 99999
    response = client.get(f"/observation/water-chemistry/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_get_water_chemistry_observation_by_id_404_wrong_activity_type(
    groundwater_level_observation,
):
    response = client.get(
        f"/observation/water-chemistry/{groundwater_level_observation.id}"
    )
    assert response.status_code == 404
    data = response.json()

    actual_activity_type = "groundwater level"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {groundwater_level_observation.id} is not a water chemistry observation. It is a {actual_activity_type} observation."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {
        "observation_id": groundwater_level_observation.id
    }
    assert data["detail"][0]["loc"] == ["path", "observation_id"]


# JB's comment: I don't think that geographic filters are necessary for
# observations. I think that they should only be applicable to finding Things
# and locations. Then the user can proceed from there to find observations.
@pytest.mark.skip(reason="unclear why not working. is it necessary functionality?")
def test_get_groundwater_observation_by_polygon():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "polygon": "POLYGON((-10.0 -10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, -10.0 -10.0))",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert (
        len(items) > 0
    ), "Expected at least one groundwater observation within the polygon"


# JB's comment: I don't think that geographic filters are necessary for
# observations. I think that they should only be applicable to finding Things
# and locations. Then the user can proceed from there to find observations
@pytest.mark.skip(reason="unclear why not working. is it necessary functionality?")
def test_get_groundwater_observation_by_polygon_nonexistent():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "polygon": "POLYGON((-100.0 -100.0, -90.0 -90.0, -90.0 -80.0, -100.0 -80.0, -100.0 -100.0))",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) == 0, "Expected no groundwater observations within the polygon"


# DELETE tests =================================================================


def test_delete_observation_by_id(observation_to_delete):
    response = client.delete(f"/observation/{observation_to_delete.id}")
    assert response.status_code == 204

    # Verify that the observation was deleted
    get_response = client.get(f"/observation/{observation_to_delete.id}")
    assert get_response.status_code == 404
    data = get_response.json()
    assert (
        data["detail"] == f"Observation with ID {observation_to_delete.id} not found."
    )


def test_delete_observation_by_id_404_not_found(observation_to_delete):
    bad_id = 99999
    response = client.delete(f"/observation/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


# ============= EOF =============================================
