from db import Observation, FieldEvent, FieldActivity, Sample
from db.engine import session_ctx
from transfers.well_transfer import WellTransferer
from transfers.waterlevels_transfer import WaterLevelTransferer


def test_water_level_with_unknown_data_quality():
    pointids = ["MG-020"]
    wt = WellTransferer(pointids=pointids)
    wt.transfer()

    wlt = WaterLevelTransferer()
    input_df, cleaned_df = wlt._get_dfs()
    wlt.input_df = input_df
    wlt.cleaned_df = cleaned_df
    wlt.cleaned_df.at[wlt.cleaned_df.index[0], "DataQuality"] = "faux"

    with session_ctx() as session:
        wlt._transfer_hook(session)

        assert len(wlt.errors) == 1
        error = wlt.errors[0]
        assert error["pointid"] == "MG-020"
        assert error["table"] == "WaterLevels"
        assert error["field"] == "DataQuality"
        assert error["error"] == "Unknown DataQuality value: faux"

        assert session.query(FieldEvent).count() == 2
        assert session.query(FieldActivity).count() == 2
        assert session.query(Sample).count() == 2
        assert session.query(Observation).count() == 2

        session.query(Observation).delete()
        session.query(Sample).delete()
        session.query(FieldActivity).delete()
        session.query(FieldEvent).delete()
        session.commit()
