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
from datetime import timezone
from unittest.mock import patch

import pytest

from api.asset import get_storage_bucket
from core.app import app
from core.dependencies import viewer_function, admin_function, editor_function
from db import Asset
from schemas import DT_FMT
from tests import (
    client,
    cleanup_post_test,
    override_authentication,
    cleanup_patch_test,
)


# CLASSES, FIXTURES, AND FUNCTIONS =============================================


class MockBlob:
    def upload_from_file(self, *args, **kwargs):
        pass

    def generate_signed_url(self, *args, **kwargs):
        return "https://storage.googleapis.com/mock-bucket/mock-asset"

    def delete(self, *args, **kwargs):
        pass


class MockStorageBucket:
    name = "mock-bucket"

    def blob(self, *args, **kwargs):
        return MockBlob()

    def get_blob(self, *args, **kwargs):
        return None


def mock_storage_bucket():
    return MockStorageBucket()


@pytest.fixture(scope="module", autouse=True)
def override_dependency_fixture():
    app.dependency_overrides = {
        get_storage_bucket: mock_storage_bucket,
    }

    app.dependency_overrides[viewer_function] = override_authentication()
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "test", "sub": "314159"}
    )
    app.dependency_overrides[editor_function] = override_authentication(
        default={"name": "test", "sub": "314159"}
    )

    yield

    app.dependency_overrides = {}


# POST & UPLOAD tests ==========================================================


def test_upload_asset():
    path = "tests/data/riochama.png"

    with open(path, "rb") as file:
        response = client.post(
            "/asset/upload",
            files={"file": ("riochama.png", file, "image/png")},
        )

        assert response.status_code == 201
        data = response.json()
        assert "storage_path" in data


def test_add_asset(water_well_thing):
    payload = {
        "release_status": "draft",
        "thing_id": water_well_thing.id,
        "name": "test_asset.png",
        "label": "Test Asset",
        "uri": "https://storage.googleapis.com/mock-bucket/mock-asset",
        "storage_service": "mock_service",
        "storage_path": "mock/path/to/asset/test_asset.png",
        "mime_type": "image/png",
        "size": 12345,
    }
    resp = client.post("/asset", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
    assert data["name"] == payload["name"]
    assert data["label"] == payload["label"]
    assert data["uri"] == payload["uri"]
    assert data["storage_service"] == "gcs"
    assert data["storage_path"] == payload["storage_path"]
    assert data["mime_type"] == payload["mime_type"]
    assert data["size"] == payload["size"]
    assert data["signed_url"] == None

    cleanup_post_test(Asset, data["id"])


def test_add_asset_409_bad_thing_id(water_well_thing):
    bad_thing_id = 99999
    payload = {
        "thing_id": bad_thing_id,
        "name": "test_asset.png",
        "label": "Test Asset",
        "uri": "https://storage.googleapis.com/mock-bucket/mock-asset",
        "storage_service": "mock_service",
        "storage_path": "mock/path/to/asset/test_asset.png",
        "mime_type": "image/png",
        "size": 12345,
        "release_status": "draft",
    }
    resp = client.post("/asset", json=payload)
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert data["detail"][0]["msg"] == f"Thing with ID {bad_thing_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": bad_thing_id}


# GET tests ====================================================================


def test_get_assets(asset, asset_with_associated_thing):
    response = client.get("/asset")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["items"][0]["id"] == asset.id
    assert data["items"][0]["created_at"] == asset.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["release_status"] == asset.release_status
    assert data["items"][0]["name"] == asset.name
    assert data["items"][0]["label"] == asset.label
    assert data["items"][0]["storage_path"] == asset.storage_path
    assert data["items"][0]["mime_type"] == asset.mime_type
    assert data["items"][0]["size"] == asset.size
    assert data["items"][0]["uri"] == asset.uri
    assert data["items"][0]["storage_service"] == asset.storage_service
    assert data["items"][0]["signed_url"] == None

    assert data["items"][1]["id"] == asset_with_associated_thing.id
    assert data["items"][1][
        "created_at"
    ] == asset_with_associated_thing.created_at.astimezone(timezone.utc).strftime(
        DT_FMT
    )
    assert (
        data["items"][1]["release_status"] == asset_with_associated_thing.release_status
    )
    assert data["items"][1]["name"] == asset_with_associated_thing.name
    assert data["items"][1]["label"] == asset_with_associated_thing.label
    assert data["items"][1]["storage_path"] == asset_with_associated_thing.storage_path
    assert data["items"][1]["mime_type"] == asset_with_associated_thing.mime_type
    assert data["items"][1]["size"] == asset_with_associated_thing.size
    assert data["items"][1]["uri"] == asset_with_associated_thing.uri
    assert (
        data["items"][1]["storage_service"]
        == asset_with_associated_thing.storage_service
    )
    assert data["items"][1]["signed_url"] == None


def test_get_assets_thing_id(asset_with_associated_thing, water_well_thing):
    with patch("api.asset.get_storage_bucket", return_value=MockStorageBucket()):
        query_parameters = {"thing_id": water_well_thing.id}
        response = client.get("/asset", params=query_parameters)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == asset_with_associated_thing.id
        assert (
            data["items"][0]["signed_url"]
            == mock_storage_bucket().blob().generate_signed_url()
        )


def test_get_asset_by_id(asset):
    response = client.get(f"/asset/{asset.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == asset.id
    assert data["created_at"] == asset.created_at.astimezone(timezone.utc).strftime(
        DT_FMT
    )
    assert data["release_status"] == asset.release_status
    assert data["name"] == asset.name
    assert data["label"] == asset.label
    assert data["storage_path"] == asset.storage_path
    assert data["mime_type"] == asset.mime_type
    assert data["size"] == asset.size
    assert data["uri"] == asset.uri
    assert data["storage_service"] == asset.storage_service
    assert data["signed_url"] == MockBlob().generate_signed_url()


def test_get_asset_by_id_404_not_found(asset):
    bad_id = 99999
    response = client.get(f"/asset/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Asset with ID {bad_id} not found."


# PATCH tests ==================================================================


def test_patch_asset(asset):
    payload = {
        "name": "patched name",
        "label": "patched label",
        "release_status": "public",
    }
    response = client.patch(f"/asset/{asset.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == asset.id
    assert data["name"] == payload["name"]
    assert data["label"] == payload["label"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(Asset, payload, asset)


def test_patch_asset_404_not_found(asset):
    bad_id = 99999
    payload = {"name": "patched name", "label": "patched label"}
    response = client.patch(f"/asset/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Asset with ID {bad_id} not found."


# DELETE tests =================================================================


def test_delete_asset(second_asset):
    response = client.delete(f"/asset/{second_asset.id}")
    assert response.status_code == 204

    # verify deletion
    response = client.get(f"/asset/{second_asset.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Asset with ID {second_asset.id} not found."


def test_delete_asset_404_not_found(second_asset):
    bad_id = 99999
    response = client.delete(f"/asset/{bad_id}/remove")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Asset with ID {bad_id} not found."


def test_remove_asset(second_asset):
    response = client.delete(f"/asset/{second_asset.id}/remove")
    assert response.status_code == 204


# ============= EOF =============================================
