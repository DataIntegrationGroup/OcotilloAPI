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
from copy import deepcopy

from db.engine import session_ctx
from db.sample import Sample
from tests import client


#  ============= Post tests for samples =============================================
def test_add_sample(thing):
    """
    Test adding a sample to the collaborative network.
    """
    response = client.post(
        "/sample",
        json={
            "thing_id": thing.id,
            "sample_date": "2025-01-01T00:00:00Z",
            "sample_method": "manual",
            "release_status": "draft",
            "sample_type": "groundwater",
            "sampler": "Test Sampler A",
            "field_sample_id": "FS-12345",
            "sampler_name": "Test Add Sampler",
        },
    )
    data = response.json()
    assert data["id"] == data["id"]
    assert data["thing_id"] == data["thing_id"]
    assert data["sample_type"] == data["sample_type"]
    assert data["field_sample_id"] == data["field_sample_id"]
    assert data["sample_date"] == data["sample_date"]
    assert data["release_status"] == data["release_status"]
    assert data["sampler_name"] == data["sampler_name"]
    assert data["qc_sample"] == data["qc_sample"]
    assert data["sensor_id"] == data["sensor_id"]
    assert data["sample_matrix"] == data["sample_matrix"]
    assert data["sample_method"] == data["sample_method"]
    assert data["duplicate_sample_number"] == data["duplicate_sample_number"]
    assert data["sample_top"] == data["sample_top"]
    assert data["sample_bottom"] == data["sample_bottom"]

    # cleanup after adding the sample
    with session_ctx() as session:
        session.query(Sample).where(Sample.id == data["id"]).delete()
        session.commit()


#  ============= Patch tests for samples =============================================
def test_patch_sample(sample):
    """
    Test updating a sample in the collaborative network.
    """
    original_sample = deepcopy(sample)

    sampler_name = "Test Sampler B"
    sample_method_patch = "continuous"
    sample_date_patch = "2025-01-02T00:00:00Z"
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "sampler_name": sampler_name,
            "sample_method": sample_method_patch,
            "sample_date": sample_date_patch,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == sample.id
    assert data["sampler_name"] == sampler_name
    assert data["sample_date"] == sample_date_patch[:-1]
    assert data["sample_method"] == sample_method_patch
    assert data["thing_id"] == sample.thing_id

    # cleanup after patching the sample
    with session_ctx() as session:
        updated_sample = session.query(Sample).filter(Sample.id == sample.id).one()
        updated_sample.sample_method = original_sample.sample_method
        updated_sample.sample_date = original_sample.sample_date
        updated_sample.sampler_name = original_sample.sampler_name
        session.commit()


def test_patch_sample_404_not_found(sample):
    """
    Test updating a sample that does not exist in the collaborative network.
    """
    sample_method_patch = "continuous"
    response = client.patch(
        "/sample/999",
        json={
            "sample_method": sample_method_patch,
        },
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


def test_patch_sample_422_thing_id_not_found(sample):
    """
    Test updating a sample with a thing_id that does not exist
    """
    bad_thing_id = 999
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "thing_id": bad_thing_id,
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) == 1
    error = data["detail"][0]
    assert error["type"] == "value_error"
    assert error["loc"] == ["body", "thing_id"]
    assert error["msg"] == f"Value error, Thing with ID {bad_thing_id} does not exist."
    assert error["input"] == bad_thing_id
    assert error["ctx"] == {"error": {}}


def test_patch_sample_422_invalid_timestamp(sample):
    """
    Test updating a sample with an invalid collection timestamp.
    """
    bad_sample_date = "3500-01-01T00:00:00Z"
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "sample_date": bad_sample_date,  # Invalid date
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    detail = data["detail"]
    assert isinstance(detail, list)
    assert len(detail) == 1
    assert detail[0]["type"] == "value_error"
    assert detail[0]["loc"] == ["body", "sample_date"]
    assert (
        detail[0]["msg"]
        == f"Value error, Sample date {bad_sample_date[:-1].replace("T", " ")}+00:00 cannot be in the future."
    )
    assert detail[0]["input"] == bad_sample_date
    assert detail[0]["ctx"] == {"error": {}}


# ============== Custom validations for samples =============================================

"""
Development notes:

Both POST and PATCH endpoints use the same custom validators, which is why 
they are being tested together here. For true unit testing, though, these can be separated
into different POST and PATCH validation tests.
"""


def test_validate_thing_id(sample):
    bad_thing_id = 999

    for method in ["post", "patch"]:
        if method == "post":
            response = client.post(
                "/sample",
                json={
                    "thing_id": bad_thing_id,
                    "sample_date": "2025-01-01T00:00:00Z",
                    "sample_method": "manual",
                    "release_status": "draft",
                    "sample_type": "groundwater",
                    "sampler_name": "Test Sampler",
                    "field_sample_id": "FS-12345",
                },
            )
        else:
            response = client.patch(
                f"/sample/{sample.id}",
                json={
                    "thing_id": bad_thing_id,
                },
            )

        data = response.json()
        assert response.status_code == 422

        assert isinstance(data["detail"], list)
        assert len(data["detail"]) == 1
        detail = data["detail"][0]
        assert detail["type"] == "value_error"
        assert detail["loc"] == ["body", "thing_id"]
        assert (
            detail["msg"]
            == f"Value error, Thing with ID {bad_thing_id} does not exist."
        )
        assert detail["input"] == bad_thing_id
        assert detail["ctx"] == {"error": {}}


def test_validate_sample_date(sample):
    bad_sample_date = "3500-01-01T00:00:00Z"
    bad_sample_date_dt = datetime.fromisoformat(bad_sample_date.replace("Z", "+00:00"))

    for method in ["post", "patch"]:
        if method == "post":
            response = client.post(
                "/sample",
                json={
                    "thing_id": sample.thing_id,
                    "sample_date": bad_sample_date,
                    "sample_method": "manual",
                    "release_status": "draft",
                    "sample_type": "groundwater",
                    "sampler_name": "Test Sampler",
                    "field_sample_id": "FS-12345",
                },
            )
        else:
            response = client.patch(
                f"/sample/{sample.id}",
                json={
                    "sample_date": bad_sample_date,
                },
            )

        data = response.json()
        assert response.status_code == 422
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) == 1
        detail = data["detail"][0]
        assert detail["type"] == "value_error"
        assert detail["loc"] == ["body", "sample_date"]
        assert (
            detail["msg"]
            == f"Value error, Sample date {bad_sample_date_dt} cannot be in the future."
        )
        assert detail["input"] == bad_sample_date
        assert detail["ctx"] == {"error": {}}


def test_validate_field_sample_id(sample):
    bad_field_sample_id = sample.field_sample_id

    for method in ["post", "patch"]:
        if method == "post":
            response = client.post(
                "/sample",
                json={
                    "thing_id": sample.thing_id,
                    "sample_date": "2025-01-01T00:00:00Z",
                    "sample_method": "manual",
                    "release_status": "draft",
                    "sample_type": "groundwater",
                    "sampler_name": "Test Sampler",
                    "field_sample_id": bad_field_sample_id,
                },
            )
        else:
            response = client.patch(
                f"/sample/{sample.id}",
                json={
                    "field_sample_id": bad_field_sample_id,
                },
            )
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) == 1
        detail = data["detail"][0]
        assert detail["type"] == "value_error"
        assert detail["loc"] == ["body", "field_sample_id"]
        assert (
            detail["msg"]
            == f"Value error, Field sample ID {bad_field_sample_id} already exists."
        )


def test_validate_sensor_id(sample):
    sensor_id = 999999999
    for method in ["post", "patch"]:
        if method == "post":
            response = client.post(
                "/sample",
                json={
                    "thing_id": sample.thing_id,
                    "sample_date": "2025-01-01T00:00:00Z",
                    "sample_method": "manual",
                    "release_status": "draft",
                    "sample_type": "groundwater",
                    "sampler_name": "Test Sampler",
                    "field_sample_id": "FS-12345",
                    "sensor_id": sensor_id,
                },
            )
        else:
            response = client.patch(
                f"/sample/{sample.id}",
                json={
                    "sensor_id": sensor_id,
                },
            )
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) == 1
        detail = data["detail"][0]
        assert detail["type"] == "value_error"
        assert detail["loc"] == ["body", "sensor_id"]
        assert (
            detail["msg"] == f"Value error, Sensor with ID {sensor_id} does not exist."
        )


def test_validate_sample_bottom(sample):
    sample_bottom = 10.0
    for method in ["post", "patch"]:
        if method == "post":
            response = client.post(
                "/sample",
                json={
                    "thing_id": sample.thing_id,
                    "sample_date": "2025-01-01T00:00:00Z",
                    "sample_method": "manual",
                    "release_status": "draft",
                    "sample_type": "groundwater",
                    "sampler_name": "Test Sampler",
                    "field_sample_id": "FS-12345",
                    "sample_bottom": sample_bottom,
                },
            )
        else:
            response = client.patch(
                f"/sample/{sample.id}",
                json={
                    "sample_bottom": sample_bottom,
                },
            )
        data = response.json()
        assert response.status_code == 422
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) == 1
        detail = data["detail"][0]
        assert detail["type"] == "value_error"
        assert detail["loc"] == ["body", "sample_bottom"]
        assert (
            detail["msg"]
            == "Value error, Sample top must be defined if sample bottom is defined."
        )


def test_validate_sample_top(sample):
    sample_top = 10.0
    for method in ["post", "patch"]:
        if method == "post":
            response = client.post(
                "/sample",
                json={
                    "thing_id": sample.thing_id,
                    "sample_date": "2025-01-01T00:00:00Z",
                    "sample_method": "manual",
                    "release_status": "draft",
                    "sample_type": "groundwater",
                    "sampler_name": "Test Sampler",
                    "field_sample_id": "FS-12345",
                    "sample_top": sample_top,
                },
            )
        else:
            response = client.patch(
                f"/sample/{sample.id}",
                json={
                    "sample_top": sample_top,
                },
            )
        data = response.json()
        assert response.status_code == 422
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) == 1
        detail = data["detail"][0]
        assert detail["type"] == "value_error"
        assert detail["loc"] == ["body", "sample_top"]
        assert (
            detail["msg"]
            == "Value error, Sample bottom must be defined if sample top is defined."
        )


#  ============= Get tests for samples =============================================
def test_get_samples(sample):
    """
    Test retrieving samples from the collaborative network.
    """
    response = client.get("/sample")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == sample.id
    assert data["items"][0]["thing_id"] == sample.thing_id
    assert data["items"][0]["sample_type"] == sample.sample_type
    assert data["items"][0]["field_sample_id"] == sample.field_sample_id
    assert data["items"][0]["sample_date"] == sample.sample_date
    assert data["items"][0]["release_status"] == sample.release_status
    assert data["items"][0]["sampler_name"] == sample.sampler_name
    assert data["items"][0]["qc_sample"] == sample.qc_sample
    assert data["items"][0]["sensor_id"] == sample.sensor_id
    assert data["items"][0]["sample_matrix"] == sample.sample_matrix
    assert data["items"][0]["sample_method"] == sample.sample_method
    assert data["items"][0]["duplicate_sample_number"] == sample.duplicate_sample_number
    assert data["items"][0]["sample_top"] == sample.sample_top
    assert data["items"][0]["sample_bottom"] == sample.sample_bottom


def test_get_sample_by_id(sample):
    """
    Test retrieving a sample from the collaborative network.
    """
    response = client.get(f"/sample/{sample.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample.id
    assert data["thing_id"] == sample.thing_id
    assert data["sample_type"] == sample.sample_type
    assert data["field_sample_id"] == sample.field_sample_id
    assert data["sample_date"] == sample.sample_date
    assert data["release_status"] == sample.release_status
    assert data["sampler_name"] == sample.sampler_name
    assert data["qc_sample"] == sample.qc_sample
    assert data["sensor_id"] == sample.sensor_id
    assert data["sample_matrix"] == sample.sample_matrix
    assert data["sample_method"] == sample.sample_method
    assert data["duplicate_sample_number"] == sample.duplicate_sample_number
    assert data["sample_top"] == sample.sample_top
    assert data["sample_bottom"] == sample.sample_bottom


def test_get_sample_by_id_404_not_found(sample):
    """
    Test retrieving a sample from the collaborative network.
    """
    response = client.get("/sample/999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


# ============= EOF =============================================
