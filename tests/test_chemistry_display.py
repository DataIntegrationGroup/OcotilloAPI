from datetime import date, datetime

from sqlalchemy import delete

from db.engine import session_ctx
from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_FieldParameters,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
)
from tests import client


def _add_sample(
    session,
    thing_id,
    point_id,
    collection_date,
    public_release=True,
):
    sample = NMA_Chemistry_SampleInfo(
        thing_id=thing_id,
        nma_sample_point_id=point_id,
        nma_wclab_id=f"LAB-{point_id}",
        collection_date=collection_date,
        collection_method="grab sample",
        collected_by="TA",
        analyses_agency="Bureau lab",
        sample_type="normal",
        water_type="groundwater",
        data_source="test",
        data_quality=True,
        public_release=public_release,
        sample_notes=f"notes for {point_id}",
    )
    session.add(sample)
    session.flush()
    return sample


def test_chemistry_display_returns_tabs_and_standards(water_well_thing):
    with session_ctx() as session:
        old_sample = _add_sample(
            session,
            water_well_thing.id,
            "WL-0001A",
            datetime(2024, 1, 12),
        )
        selected_sample = _add_sample(
            session,
            water_well_thing.id,
            "WL-0001B",
            datetime(2025, 5, 15),
        )
        private_sample = _add_sample(
            session,
            water_well_thing.id,
            "WL-0001C",
            datetime(2026, 5, 15),
            public_release=False,
        )

        session.add_all(
            [
                NMA_MajorChemistry(
                    chemistry_sample_info_id=old_sample.id,
                    nma_sample_point_id="WL-0001A",
                    analyte="Arsenic",
                    symbol="As",
                    sample_value=0.005,
                    units="mg/L",
                    analysis_date=datetime(2024, 2, 1),
                ),
                NMA_MajorChemistry(
                    chemistry_sample_info_id=selected_sample.id,
                    nma_sample_point_id="WL-0001B",
                    analyte="Arsenic",
                    symbol="As",
                    sample_value=0.012,
                    units="mg/L",
                    analysis_date=datetime(2025, 6, 2),
                ),
                NMA_MajorChemistry(
                    chemistry_sample_info_id=private_sample.id,
                    nma_sample_point_id="WL-0001C",
                    analyte="Arsenic",
                    symbol="As",
                    sample_value=9.0,
                    units="mg/L",
                ),
                NMA_MinorTraceChemistry(
                    chemistry_sample_info_id=selected_sample.id,
                    nma_sample_point_id="WL-0001B",
                    analyte="Tritium",
                    symbol="3H",
                    sample_value=0.9,
                    units="TU",
                    analysis_date=date(2025, 6, 3),
                ),
                NMA_MinorTraceChemistry(
                    chemistry_sample_info_id=selected_sample.id,
                    nma_sample_point_id="WL-0001B",
                    analyte="Barium",
                    symbol="Ba",
                    sample_value=0.2,
                    units="mg/L",
                ),
                NMA_FieldParameters(
                    chemistry_sample_info_id=selected_sample.id,
                    nma_sample_point_id="WL-0001B",
                    nma_object_id=2001,
                    field_parameter="pHf",
                    sample_value=7.4,
                    units="S.U.",
                    notes="stabilized",
                ),
            ]
        )
        old_sample_id = old_sample.id
        selected_sample_id = selected_sample.id
        private_sample_id = private_sample.id
        sample_ids = [old_sample_id, selected_sample_id, private_sample_id]
        session.commit()

    try:
        response = client.get(
            "/chemistry/display", params={"thing_id": water_well_thing.id}
        )
        assert response.status_code == 200
        data = response.json()

        assert data["thing_id"] == water_well_thing.id
        assert data["selected_sample_info_id"] == selected_sample_id
        assert [sample["id"] for sample in data["samples"]] == [
            selected_sample_id,
            old_sample_id,
        ]
        assert data["sample_note"] == "notes for WL-0001B"

        general = data["tabs"]["general_chemistry"]
        assert general["current_results"][0]["parameter_name"] == "Arsenic"
        standard = general["current_results"][0]["standard"]
        assert standard["status"] == "above_mcl"
        assert general["standards_summary"]["above_mcl_count"] == 1
        assert general["standards_summary"]["compared_parameter_count"] == 1
        assert len(general["crosstab"]["rows"]) == 2

        field = data["tabs"]["field_parameters"]
        assert field["current_results"][0]["parameter_name"] == "pH"
        assert field["current_results"][0]["notes"] == "stabilized"

        tracers = data["tabs"]["environmental_tracers"]
        assert tracers["current_results"][0]["parameter_name"] == "Tritium"

        additional = data["tabs"]["additional_analyses"]
        assert additional["current_results"][0]["parameter_name"] == "Barium"

        result_ids = str(data)
        assert "WL-0001C" not in result_ids
        assert "9.0" not in result_ids
    finally:
        with session_ctx() as session:
            session.execute(
                delete(NMA_Chemistry_SampleInfo).where(
                    NMA_Chemistry_SampleInfo.id.in_(sample_ids)
                )
            )
            session.commit()


def test_chemistry_display_honors_sample_and_date_filters(water_well_thing):
    with session_ctx() as session:
        old_sample = _add_sample(
            session,
            water_well_thing.id,
            "WL-0002A",
            datetime(2024, 1, 12),
        )
        new_sample = _add_sample(
            session,
            water_well_thing.id,
            "WL-0002B",
            datetime(2025, 5, 15),
        )
        session.add_all(
            [
                NMA_MajorChemistry(
                    chemistry_sample_info_id=old_sample.id,
                    nma_sample_point_id="WL-0002A",
                    analyte="Calcium",
                    symbol="Ca",
                    sample_value=10,
                    units="mg/L",
                ),
                NMA_MajorChemistry(
                    chemistry_sample_info_id=new_sample.id,
                    nma_sample_point_id="WL-0002B",
                    analyte="Calcium",
                    symbol="Ca",
                    sample_value=20,
                    units="mg/L",
                ),
            ]
        )
        old_sample_id = old_sample.id
        new_sample_id = new_sample.id
        sample_ids = [old_sample_id, new_sample_id]
        session.commit()

    try:
        response = client.get(
            "/chemistry/display",
            params={
                "thing_id": water_well_thing.id,
                "sample_info_id": old_sample_id,
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2025-01-01T00:00:00",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["selected_sample_info_id"] == old_sample_id
        assert [sample["id"] for sample in data["samples"]] == [old_sample_id]
        current_results = data["tabs"]["general_chemistry"]["current_results"]
        assert current_results[0]["value"] == 10

        missing_selected = client.get(
            "/chemistry/display",
            params={
                "thing_id": water_well_thing.id,
                "sample_info_id": new_sample_id,
                "end_time": "2025-01-01T00:00:00",
            },
        )
        assert missing_selected.status_code == 404
    finally:
        with session_ctx() as session:
            session.execute(
                delete(NMA_Chemistry_SampleInfo).where(
                    NMA_Chemistry_SampleInfo.id.in_(sample_ids)
                )
            )
            session.commit()


def test_chemistry_display_returns_404_for_no_released_samples(
    water_well_thing,
):
    response = client.get(
        "/chemistry/display", params={"thing_id": water_well_thing.id}
    )
    assert response.status_code == 404
