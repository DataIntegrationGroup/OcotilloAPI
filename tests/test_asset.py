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
import shutil

from api.asset import get_storage_bucket
from core.app import app
from tests import client
import pytest
import os
import glob


# @pytest.fixture(scope="module", autouse=True)
# def cleanup():
#     """
#     Fixture to clean up after tests.
#     This can be used to delete any assets created during the tests.
#     """
#     yield
#     depot = DepotManager.get()
#     for asset in depot.list():
#         depot.delete(asset)
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


def test_add_asset():
    path = "tests/data/riochama.png"

    with open(path, "rb") as file:
        response = client.post(
            "/asset",
            files={"file": ("riochama.png", file, "image/png")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "riochama.png"
        url = data["url"]
        assert url.startswith("https://storage.googleapis.com/")


def test_get_asset():
    response = client.get("/asset/1")
    assert response.status_code == 200
    data  = response.json()
    assert data["id"] == 1
    assert data["filename"] == "riochama.png"
    assert data["url"] == "https://storage.googleapis.com/mock-bucket/mock-asset"


def test_get_asset_not_found():
    response = client.get("/asset/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}
# ============= EOF =============================================
