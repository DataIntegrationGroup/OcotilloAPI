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
from api.asset import get_storage_bucket
from core.app import app
from core.dependencies import viewer_function, admin_function, editor_function
from db import Asset
from tests import client, cleanup_post_test, override_authentication

import pytest

# CLASSES, FIXTURES, AND FUNCTIONS =============================================


class MockBlob:
    def upload_from_file(self, *args, **kwargs):
        pass

    def generate_signed_url(self, *args, **kwargs):
        return "https://storage.googleapis.com/mock-bucket/mock-asset"


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


def test_add_asset(thing):
    payload = {
        "thing_id": thing.id,
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
    assert data["name"] == payload["name"]
    assert data["label"] == payload["label"]
    assert data["uri"] == payload["uri"]
    assert data["storage_service"] == "gcs"
    assert data["storage_path"] == payload["storage_path"]
    assert data["mime_type"] == payload["mime_type"]
    assert data["size"] == payload["size"]

    cleanup_post_test(Asset, data["id"])


def test_add_asset_409_bad_thing_id(thing):
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
    }
    resp = client.post("/asset", json=payload)
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert data["detail"][0]["msg"] == f"Thing with ID {bad_thing_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": bad_thing_id}


def test_get_asset(asset):
    response = client.get(f"/asset/{asset.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == asset.id
    assert data["name"] == asset.name
    assert data["uri"] == MockBlob().generate_signed_url()


def test_get_asset_not_found():
    response = client.get("/asset/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


# ============= EOF =============================================
