# ===============================================================================
# Copyright 2026 ross
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
"""Tests for the read-only regulatory limit routes.

The fixtures write their own parameters rather than leaning on the two the
lexicon seeds (`groundwater level` and `pH`): limits are a chemistry concept,
and the filter tests need two analytes to show that narrowing actually narrows.
Every lexicon-backed value used here is a real term -- parameter_name, matrix,
parameter_type, limit_source, limit_unit and limit_type are all foreign keys to
lexicon_term, so an invented value fails on insert rather than in an assertion.
"""

import pytest
from sqlalchemy import delete

from core.dependencies import viewer_function
from db.engine import session_ctx
from db.parameter import Parameter
from db.regulatory_limit import RegulatoryLimit
from main import app
from tests import client, override_authentication


@pytest.fixture(scope="module", autouse=True)
def override_dependencies_fixture():
    app.dependency_overrides[viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


@pytest.fixture()
def limited_parameters():
    """Two analytes, three limits: arsenic has both an MCL and a state
    standard, chloride has an SMCL."""
    with session_ctx() as session:
        arsenic = Parameter(
            parameter_name="Arsenic",
            matrix="water",
            parameter_type="Metal",
            default_unit="mg/L",
            release_status="public",
        )
        chloride = Parameter(
            parameter_name="Chloride",
            matrix="water",
            parameter_type="Major Element",
            default_unit="mg/L",
            release_status="public",
        )
        session.add_all([arsenic, chloride])
        session.commit()

        limits = [
            RegulatoryLimit(
                parameter_id=arsenic.id,
                limit_source="NMED",
                limit_value=0.01,
                limit_unit="mg/L",
                limit_type="MCL",
                release_status="public",
            ),
            RegulatoryLimit(
                parameter_id=arsenic.id,
                limit_source="NMED",
                limit_value=0.05,
                limit_unit="mg/L",
                limit_type="GWQS",
                release_status="public",
            ),
            RegulatoryLimit(
                parameter_id=chloride.id,
                limit_source="NMED",
                limit_value=250,
                limit_unit="mg/L",
                limit_type="SMCL",
                release_status="public",
            ),
        ]
        session.add_all(limits)
        session.commit()

        ids = {
            "arsenic_id": arsenic.id,
            "chloride_id": chloride.id,
            "limit_ids": [limit.id for limit in limits],
        }

        yield ids

        session.execute(
            delete(RegulatoryLimit).where(RegulatoryLimit.id.in_(ids["limit_ids"]))
        )
        session.execute(
            delete(Parameter).where(
                Parameter.id.in_([ids["arsenic_id"], ids["chloride_id"]])
            )
        )
        session.commit()


# ====== GET tests =============================================================


def test_get_regulatory_limits(limited_parameters):
    response = client.get("/regulatory_limit")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3

    items = {item["id"]: item for item in data["items"]}
    mcl = items[limited_parameters["limit_ids"][0]]
    assert mcl["limit_source"] == "NMED"
    assert mcl["limit_type"] == "MCL"
    assert mcl["limit_value"] == 0.01
    assert mcl["limit_unit"] == "mg/L"
    assert mcl["parameter_id"] == limited_parameters["arsenic_id"]
    # The nested parameter is the point of the route: a consumer holding a
    # chemistry result has the analyte name, not the id.
    assert mcl["parameter"]["parameter_name"] == "Arsenic"
    assert mcl["parameter"]["matrix"] == "water"


def test_get_regulatory_limit_by_id(limited_parameters):
    limit_id = limited_parameters["limit_ids"][2]
    response = client.get(f"/regulatory_limit/{limit_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == limit_id
    assert data["limit_type"] == "SMCL"
    assert data["limit_value"] == 250
    assert data["parameter"]["parameter_name"] == "Chloride"


def test_get_regulatory_limit_404_not_found():
    bad_limit_id = 99999
    response = client.get(f"/regulatory_limit/{bad_limit_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"RegulatoryLimit with ID {bad_limit_id} not found."


# ====== filter tests ==========================================================


def test_filter_by_parameter_id(limited_parameters):
    response = client.get(
        "/regulatory_limit",
        params={"parameter_id": limited_parameters["arsenic_id"]},
    )
    assert response.status_code == 200
    returned = {item["parameter_id"] for item in response.json()["items"]}
    assert returned == {limited_parameters["arsenic_id"]}


def test_filter_by_parameter_name(limited_parameters):
    """The filter a consumer of /chemistry/results can actually use: it holds a
    lexicon analyte name, never a parameter id."""
    response = client.get("/regulatory_limit", params={"parameter_name": "Arsenic"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 2
    assert {item["parameter"]["parameter_name"] for item in items} == {"Arsenic"}
    assert {item["limit_type"] for item in items} >= {"MCL", "GWQS"}


def test_filter_by_limit_type(limited_parameters):
    response = client.get("/regulatory_limit", params={"limit_type": "SMCL"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert limited_parameters["limit_ids"][2] in {item["id"] for item in items}
    assert {item["limit_type"] for item in items} == {"SMCL"}


def test_filter_by_limit_source(limited_parameters):
    response = client.get("/regulatory_limit", params={"limit_source": "NMED"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["limit_source"] for item in items} == {"NMED"}


def test_sort_by_limit_value(limited_parameters):
    response = client.get(
        "/regulatory_limit",
        params={
            "parameter_name": "Arsenic",
            "sort": "limit_value",
            "order": "desc",
        },
    )
    assert response.status_code == 200
    values = [item["limit_value"] for item in response.json()["items"]]
    assert values == sorted(values, reverse=True)


# ============= EOF =============================================
