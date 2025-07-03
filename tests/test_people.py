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
from tests import client


def test_phone_validation_fail():
    for phone in [
        "definitely not a phone",
        # "1234567890",
        # "123-456-7890",
        # "123-456-78901",
        # "123-4567-890",
        "123-456-789a",
        "123-456-7890x1234",
        "123.456.7890",
        "(123) 456-7890",
    ]:

        response = client.post(
            "/base/contact",
            json={
                "owner_id": 2,
                "name": "Test Contact 2",
                "email": "fasdfasdf@gmail.com",
                "phone": phone,
            },
        )
        assert response.status_code == 422


def test_email_validation_fail():

    for email in [
        "",
        "invalid-email",
        "invalid@domain",
        "invalid@domain.",
        "@domain.com",
    ]:
        response = client.post(
            "/base/contact",
            json={
                "owner_id": 1,
                "name": "Test Contact2",
                "email": email,
                "phone": "+12345678901",
            },
        )
        assert response.status_code == 422, f"Failed for email: {email}"


def test_phone_validation_success():
    response = client.post(
        "/base/contact",
        json={
            "owner_id": 2,
            "name": "Contact X",
            "email": "foobar@gmail.com",
            "phone": "+12345678901",
        },
    )
    assert response.status_code == 201


# ============= EOF =============================================
