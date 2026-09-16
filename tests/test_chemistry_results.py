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
"""GET /chemistry/results keys results on when the water was collected.

A lab runs one sample's analytes over days or weeks. Keying results on the
analysis date turned one visit into several points in time, so the owner
report for AR-0102 counted eight samples in 2019 where there was one.
"""

import pytest
from sqlalchemy import text

from core.dependencies import amp_viewer_function
from db.engine import session_ctx
from main import app
from tests import client, override_authentication


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[amp_viewer_function] = override_authentication()
    yield
    app.dependency_overrides = {}


def _refresh_views(session):
    session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_chemistry"))
    session.execute(text("REFRESH MATERIALIZED VIEW ogc_internal_water_chemistry"))
    session.commit()


def _add_sample(session, thing_id, collected_on, point_id):
    return session.execute(
        text(
            'INSERT INTO "NMA_Chemistry_SampleInfo" '
            '(thing_id, "CollectionDate", "PublicRelease", "nma_SamplePointID") '
            "VALUES (:tid, :collected, true, :point) RETURNING id"
        ),
        {"tid": thing_id, "collected": collected_on, "point": point_id},
    ).scalar()


def _add_major(session, sample_id, symbol, value, analysed_on):
    session.execute(
        text(
            'INSERT INTO "NMA_MajorChemistry" '
            '(chemistry_sample_info_id, "Symbol", "SampleValue", "Units", '
            "\"AnalysisDate\") VALUES (:sid, :symbol, :val, 'mg/L', :analysed)"
        ),
        {"sid": sample_id, "symbol": symbol, "val": value, "analysed": analysed_on},
    )


def _add_minor(session, sample_id, point_id, symbol, value, analysed_on):
    session.execute(
        text(
            'INSERT INTO "NMA_MinorTraceChemistry" '
            '(chemistry_sample_info_id, "nma_SamplePointID", symbol, '
            "sample_value, units, analysis_date) "
            "VALUES (:sid, :point, :symbol, :val, 'mg/L', :analysed)"
        ),
        {
            "sid": sample_id,
            "point": point_id,
            "symbol": symbol,
            "val": value,
            "analysed": analysed_on,
        },
    )


def _add_field(session, sample_id, parameter, value):
    session.execute(
        text(
            'INSERT INTO "NMA_FieldParameters" '
            '(chemistry_sample_info_id, "FieldParameter", "SampleValue", "Units") '
            "VALUES (:sid, :parameter, :val, 'std units')"
        ),
        {"sid": sample_id, "parameter": parameter, "val": value},
    )


@pytest.fixture
def two_samples(water_well_thing):
    """One sample collected Apr 09 2019 and analysed across three dates, and
    one collected Dec 20 2018 whose lab work ran into January 2019."""
    with session_ctx() as session:
        original_status = session.execute(
            text("SELECT release_status FROM thing WHERE id = :tid"),
            {"tid": water_well_thing.id},
        ).scalar()
        session.execute(
            text("UPDATE thing SET release_status = 'public' WHERE id = :tid"),
            {"tid": water_well_thing.id},
        )

        april = _add_sample(session, water_well_thing.id, "2019-04-09", "RES-APR")
        _add_field(session, april, "pH", 7.4)
        _add_major(session, april, "Cl", 12.0, "2019-04-16")
        _add_major(session, april, "Ca", 40.0, "2019-04-22")
        _add_minor(session, april, "RES-APR", "As", 0.012, "2019-05-24")

        december = _add_sample(session, water_well_thing.id, "2018-12-20", "RES-DEC")
        _add_major(session, december, "SO4", 80.0, "2019-01-07")
        session.commit()
        _refresh_views(session)

        yield {"april": april, "december": december, "thing_id": water_well_thing.id}

        for table in (
            "NMA_MajorChemistry",
            "NMA_MinorTraceChemistry",
            "NMA_FieldParameters",
        ):
            session.execute(
                text(
                    f'DELETE FROM "{table}" '
                    "WHERE chemistry_sample_info_id IN (:a, :d)"
                ),
                {"a": april, "d": december},
            )
        session.execute(
            text('DELETE FROM "NMA_Chemistry_SampleInfo" WHERE id IN (:a, :d)'),
            {"a": april, "d": december},
        )
        session.execute(
            text("UPDATE thing SET release_status = :status WHERE id = :tid"),
            {"status": original_status, "tid": water_well_thing.id},
        )
        session.commit()
        _refresh_views(session)


def _results(thing_id, year):
    response = client.get(
        "/chemistry/results",
        params={
            "thing_id": thing_id,
            "start_time": f"{year}-01-01T00:00:00",
            "end_time": f"{year + 1}-01-01T00:00:00",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_every_result_in_a_sample_carries_its_collection_date(two_samples):
    items = _results(two_samples["thing_id"], 2019)

    april = [item for item in items if item["sample_id"] == two_samples["april"]]
    assert len(april) == 4
    assert {item["observation_datetime"] for item in april} == {"2019-04-09T00:00:00Z"}


def test_analysis_date_is_reported_separately(two_samples):
    items = _results(two_samples["thing_id"], 2019)
    by_kind = {item["result_kind"]: item for item in items}

    assert by_kind["field"]["analysis_date"] is None
    assert by_kind["minor"]["analysis_date"] == "2019-05-24T00:00:00Z"
    assert {
        item["analysis_date"] for item in items if item["result_kind"] == "major"
    } == {"2019-04-16T00:00:00Z", "2019-04-22T00:00:00Z"}


def test_year_window_follows_collection_not_analysis(two_samples):
    """A December sample analysed in January belongs to the year it was drawn."""
    in_2019 = {item["sample_id"] for item in _results(two_samples["thing_id"], 2019)}
    in_2018 = {item["sample_id"] for item in _results(two_samples["thing_id"], 2018)}

    assert in_2019 == {two_samples["april"]}
    assert in_2018 == {two_samples["december"]}


# ============= EOF =============================================
