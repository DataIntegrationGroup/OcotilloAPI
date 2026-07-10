"""Schema-level tests for the NMW_ submission contract (no database)."""

import pytest
from pydantic import ValidationError

from schemas.nmw_submission import (
    NMWSourceIn,
    NMWSubmission,
    NMWWellLocationIn,
)


def test_minimal_submission_parses():
    sub = NMWSubmission(header={"api": "30-001-00001"})
    assert sub.header.api == "30-001-00001"
    assert sub.location is None
    assert sub.records == []
    assert sub.sources == []


def test_full_nesting_parses():
    sub = NMWSubmission(
        header={"cur_well_nam": "Deep Well"},
        location={"lat_dd83": 34.1, "long_dd83": -106.2, "state": "NM"},
        records=[
            {
                "recrd_class": "geothermal",
                "z_data": [{"elev_gl": 5000.0}],
                "samples": [
                    {
                        "sample_date": "2020-01-01T00:00:00",
                        "intervals": [
                            {
                                "from_depth": 0,
                                "to_depth": 100,
                                "conductivity": [{"cnductvity": 2.5}],
                                "heat_flow": [{"q": 60.0}],
                            }
                        ],
                        "bht_headers": [
                            {
                                "temp_unit": "F",
                                "bht_data": [{"depth": 100, "bht": 98.6}],
                            }
                        ],
                        "temp_depths": [{"depth": 50, "temp": 70}],
                        "sum_heat_flow": [{"heat_flow": 60.0}],
                        "dst_headers": [
                            {
                                "test_type": "DST",
                                "dst_intervals": [
                                    {
                                        "dst_number": 1,
                                        "flow_history": [{"operation": "flow"}],
                                        "fluid_properties": [{"chlorides": 10.0}],
                                        "pressure": [{"equil_press": 2000.0}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        sources=[{"source_id": "SRC1", "title": "A report"}],
    )
    sample = sub.records[0].samples[0]
    assert sample.intervals[0].conductivity[0].cnductvity == 2.5
    assert sample.bht_headers[0].bht_data[0].bht == 98.6
    assert sample.dst_headers[0].dst_intervals[0].pressure[0].equil_press == 2000.0


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NMWSubmission(header={"api": "x", "not_a_real_column": 1})


def test_server_managed_keys_are_rejected():
    # well_data_id / object_id / global_id are owned by the server, never input.
    with pytest.raises(ValidationError):
        NMWSubmission(header={"api": "x"}, location={"object_id": 5})
    with pytest.raises(ValidationError):
        NMWSubmission(header={"api": "x", "well_data_id": "abc"})


def test_source_requires_source_id():
    with pytest.raises(ValidationError, match="source_id"):
        NMWSourceIn(title="no id")


def test_empty_string_coerced_to_none():
    loc = NMWWellLocationIn(state="  ", county="Bernalillo")
    assert loc.state is None
    assert loc.county == "Bernalillo"


def test_range_alias_field_dumps_to_orm_attr():
    # The ORM attribute for the "Range" column is ``range_``; the schema field
    # must dump under that name so the service can splat it into the model.
    loc = NMWWellLocationIn(range_=12.0)
    assert loc.model_dump()["range_"] == 12.0
