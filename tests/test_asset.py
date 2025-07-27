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
from tests import client, thing
import pytest


class MockBlob:
    def upload_from_file(self, *args, **kwargs):
        pass

    def generate_signed_url(self, *args, **kwargs):
        return "https://storage.googleapis.com/mock-bucket/mock-asset"


class MockStorageBucket:
    def blob(self, *args, **kwargs):
        return MockBlob()


def mock_storage_bucket():
    return MockStorageBucket()


app.dependency_overrides = {
    get_storage_bucket: mock_storage_bucket,
}


def test_upload_asset():
    path = "tests/data/riochama.png"

    with open(path, "rb") as file:
        response = client.post(
            "/asset/upload",
            files={"file": ("riochama.png", file, "image/png")},
        )

        assert response.status_code == 201
        data = response.json()
        print(data)
        assert "url" in data
        # assert data["name"] == "riochama.png"
        # assert data["label"] == "riochama.png"
        # assert data["storage_service"] == "mock_service"
        # assert data["storage_path"] == "mock/path/to/asset"
        # assert data["mime_type"] == "image/png"
        # assert data["size"] == 12345
        # assert data["url"] == "https://storage.googleapis.com/mock-bucket/mock-asset"

def test_add_asset(thing):
    resp = client.post(
        "/asset",
        json={"thing_id": thing.id,
              "name": "riochama.png",
               "storage_service": "mock_service",
               "storage_path": "mock/path/to/asset",
               "mime_type": "image/png",
               "size": 12345},
    )

    print(resp.json())
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "riochama.png"
    # assert data["label"] == "Test Asset"
    # path = "tests/data/riochama.png"
    #
    # with open(path, "rb") as file:
    #     response = client.post(
    #         "/asset",
    #         params={"thing_id": thing.id},
    #         files={"file": ("riochama.png", file, "image/png")},
    #     )
    #
    #     data = response.json()
    #     assert response.status_code == 201
    #     assert data["name"] == "riochama.png"
    #     url = data["url"]
    #     assert url.startswith("https://storage.googleapis.com/")


def test_add_asset_with_label(thing):
    resp = client.post(
        "/asset",
        json={"thing_id": thing.id,
              "name": "test_asset.png",
              "label": "Test Asset",
              "storage_service": "mock_service",
              "storage_path": "mock/path/to/asset",
              "mime_type": "image/png",
              "size": 12345},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test_asset.png"
    assert data["label"] == "Test Asset"
    # path = "tests/data/riochama.png"
    #
    # with open(path, "rb") as file:
    #     response = client.post(
    #         "/asset",
    #         params={'label': 'test label'},
    #         files={"file": ("riochama.png", file, "image/png")},
    #     )
    #
    #     assert response.status_code == 201
    #     data = response.json()
    #     assert data["name"] == "riochama.png"
    #     assert data["label"] == "test label"


def test_get_asset():
    response = client.get("/asset/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "riochama.png"
    assert data["url"] == "https://storage.googleapis.com/mock-bucket/mock-asset"


def test_get_asset_not_found():
    response = client.get("/asset/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


# ============= EOF =============================================
