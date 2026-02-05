import pytest

from transfers import thing_transfer as tt


@pytest.mark.parametrize(
    "func_name,site_code,thing_type",
    [
        ("transfer_rock_sample_locations", "R", "Rock sample location"),
        (
            "transfer_diversion_of_surface_water",
            "D",
            "Diversion of surface water, etc.",
        ),
        ("transfer_lake_pond_reservoir", "L", "Lake, pond or reservoir"),
        ("transfer_soil_gas_sample_locations", "S", "Soil gas sample location"),
        ("transfer_other_site_types", "OT", "Other"),
        (
            "transfer_outfall_wastewater_return_flow",
            "O",
            "Outfall of wastewater or return flow",
        ),
    ],
)
def test_transfer_new_site_types_calls_transfer_thing(
    monkeypatch, func_name, site_code, thing_type
):
    calls = []

    def fake_transfer_thing(session, site_type, make_payload, limit=None):
        class Row:
            PointID = "PT-1"
            PublicRelease = False

        payload = make_payload(Row)
        calls.append((site_type, payload, limit))

    monkeypatch.setattr(tt, "transfer_thing", fake_transfer_thing)

    getattr(tt, func_name)(session=None, limit=7)

    assert calls == [
        (
            site_code,
            {
                "name": "PT-1",
                "thing_type": thing_type,
                "release_status": "private",
            },
            7,
        )
    ]
