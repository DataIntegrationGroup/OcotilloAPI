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
# ============================================================================riochama.png===
from tests import client


def test_get_asset():
    response = client.get("/asset/1")
    assert response.status_code == 200


def test_add_asset():
    path = "tests/data/riochama.png"

    with open(path, "rb") as file:
        response = client.post(
            "/asset",
            files={"file": ("riochama.png", file, "image/png")},
            # data={'name': 'riochama.png',
            #       'file_type': 'image/png'}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "riochama.png"


# ============= EOF =============================================
