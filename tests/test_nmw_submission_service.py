"""Service + endpoint tests for NMW_ bulk submission ingestion (BDMS-960)."""

import pytest
from sqlalchemy import select, text

from core.dependencies import amp_admin_function
from db import (
    NMW_GtBhtData,
    NMW_GtBhtHeaders,
    NMW_GtSumHeatFlow,
    NMW_WellHeaders,
    NMW_WellLocations,
    NMW_WellRecords,
    NMW_WellSamples,
    NMW_WsDstFlowHistory,
    NMW_WsDstHeaders,
    NMW_WsDstIntervals,
)
from db.engine import session_ctx
from main import app
from schemas.nmw_submission import NMWSubmission
from services.nmw_submission import bulk_upload_nmw
from tests import client, override_authentication


def _clear_nmw():
    with session_ctx() as session:
        names = (
            session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_name LIKE 'NMW%'"
                )
            )
            .scalars()
            .all()
        )
        if names:
            targets = ", ".join(f'"{n}"' for n in names)
            session.execute(text(f"TRUNCATE {targets} RESTART IDENTITY CASCADE"))
        session.commit()


@pytest.fixture(autouse=True)
def clean_nmw_tables():
    _clear_nmw()
    yield
    _clear_nmw()


@pytest.fixture(scope="module", autouse=True)
def override_auth():
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "tester", "sub": "1"}
    )
    yield
    app.dependency_overrides = {}


def _full_well(api="30-001-00001", name="Deep Well"):
    return {
        "header": {"api": api, "cur_well_nam": name, "total_depth": 5000.0},
        "location": {"lat_dd83": 34.1, "long_dd83": -106.2, "state": "NM"},
        "records": [
            {
                "recrd_class": "geothermal",
                "z_data": [{"elev_gl": 5000.0}],
                "samples": [
                    {
                        "sample_date": "2020-01-01T00:00:00",
                        "bht_headers": [
                            {
                                "temp_unit": "F",
                                "bht_data": [{"depth": 100, "bht": 98.6}],
                            }
                        ],
                        "sum_heat_flow": [{"heat_flow": 60.0}],
                        "dst_headers": [
                            {
                                "test_type": "DST",
                                "dst_intervals": [
                                    {
                                        "dst_number": 1,
                                        "flow_history": [{"operation": "flow"}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "sources": [{"source_id": "SRC1", "title": "A report"}],
    }


# --- service-level ----------------------------------------------------------


def test_bulk_upload_persists_full_tree():
    result = bulk_upload_nmw([NMWSubmission(**_full_well())])
    assert result.exit_code == 0, result.stderr
    assert result.payload["summary"]["total_wells_imported"] == 1

    with session_ctx() as session:
        header = session.execute(
            select(NMW_WellHeaders).where(NMW_WellHeaders.api == "30-001-00001")
        ).scalar_one()
        wid = header.well_data_id

        loc = session.execute(
            select(NMW_WellLocations).where(NMW_WellLocations.well_data_id == wid)
        ).scalar_one()
        # OBJECTID identity self-assigned (no OBJECTID supplied in payload).
        assert loc.object_id is not None

        record = session.execute(
            select(NMW_WellRecords).where(NMW_WellRecords.well_data_id == wid)
        ).scalar_one()
        sample = session.execute(
            select(NMW_WellSamples).where(
                NMW_WellSamples.recrdset_id == record.recrd_set_id
            )
        ).scalar_one()

        bht = session.execute(
            select(NMW_GtBhtHeaders).where(
                NMW_GtBhtHeaders.sampl_set_id == sample.sampl_set_id
            )
        ).scalar_one()
        bht_data = session.execute(
            select(NMW_GtBhtData).where(NMW_GtBhtData.bht_guid == bht.bht_guid)
        ).scalar_one()
        assert bht_data.bht == 98.6

        # sum_heat_flow is wired to BOTH the record and the sample.
        shf = session.execute(
            select(NMW_GtSumHeatFlow).where(
                NMW_GtSumHeatFlow.sampl_set_id == sample.sampl_set_id
            )
        ).scalar_one()
        assert shf.recrd_set_id == record.recrd_set_id

        dst = session.execute(
            select(NMW_WsDstHeaders).where(
                NMW_WsDstHeaders.sampl_set_id == sample.sampl_set_id
            )
        ).scalar_one()
        interval = session.execute(
            select(NMW_WsDstIntervals).where(
                NMW_WsDstIntervals.dst_guid == dst.dst_guid
            )
        ).scalar_one()
        flow = session.execute(
            select(NMW_WsDstFlowHistory).where(
                NMW_WsDstFlowHistory.dst_interval == interval.dst_interval
            )
        ).scalar_one()
        assert flow.operation == "flow"


def test_missing_identifier_aborts_whole_batch():
    good = _full_well(api="30-001-00002", name="Good")
    bad = _full_well(api=None, name=None)
    bad["header"] = {"total_depth": 10.0}  # no api, no name
    result = bulk_upload_nmw([NMWSubmission(**good), NMWSubmission(**bad)])

    assert result.exit_code == 1
    assert any(
        "Well 1" in e and "api" in e for e in result.payload["validation_errors"]
    )
    # Nothing written, including the otherwise-valid well 0.
    with session_ctx() as session:
        count = session.execute(select(NMW_WellHeaders)).all()
        assert count == []


def test_duplicate_api_in_batch_rejected():
    a = _full_well(api="30-001-00003")
    b = _full_well(api="30-001-00003")
    result = bulk_upload_nmw([NMWSubmission(**a), NMWSubmission(**b)])
    assert result.exit_code == 1
    assert any("duplicate api" in e for e in result.payload["validation_errors"])


def test_existing_api_rejected():
    bulk_upload_nmw([NMWSubmission(**_full_well(api="30-001-00004"))])
    result = bulk_upload_nmw([NMWSubmission(**_full_well(api="30-001-00004"))])
    assert result.exit_code == 1
    assert any("already exists" in e for e in result.payload["validation_errors"])


# --- endpoint-level ---------------------------------------------------------


def test_endpoint_success_returns_200():
    response = client.post("/nmw/bulk-upload", json=[_full_well(api="30-001-00005")])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total_wells_imported"] == 1
    assert body["wells"][0]["api"] == "30-001-00005"


def test_endpoint_validation_error_returns_400_with_payload():
    bad = _full_well(api="30-001-00006")
    bad["header"] = {"total_depth": 1.0}
    response = client.post("/nmw/bulk-upload", json=[bad])
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["summary"]["validation_errors"] >= 1


def test_endpoint_empty_body_rejected():
    response = client.post("/nmw/bulk-upload", json=[])
    assert response.status_code == 422


def test_endpoint_unknown_field_rejected():
    payload = _full_well(api="30-001-00007")
    payload["header"]["bogus_column"] = 1
    response = client.post("/nmw/bulk-upload", json=[payload])
    assert response.status_code == 422
