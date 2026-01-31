import uuid

import pandas as pd

from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer


def test_row_to_dict_includes_wclab_id():
    transfer = MinorTraceChemistryTransferer.__new__(MinorTraceChemistryTransferer)
    sample_pt_id = uuid.uuid4()
    transfer._sample_pt_ids = {sample_pt_id}
    transfer._sample_info_cache = {sample_pt_id: 1}
    transfer.flags = {}
    transfer.errors = []

    row = pd.Series(
        {
            "SamplePtID": str(sample_pt_id),
            "GlobalID": str(uuid.uuid4()),
            "SamplePointID": "POINT-1",
            "Analyte": "Ca",
            "SampleValue": 10.5,
            "Units": "mg/L",
            "Symbol": None,
            "AnalysisMethod": "ICP",
            "AnalysisDate": "2024-01-01 00:00:00.000",
            "Notes": "note",
            "AnalysesAgency": "Lab",
            "Uncertainty": 0.1,
            "Volume": "2",
            "VolumeUnit": "L",
            "WCLab_ID": "LAB-123",
        }
    )

    row_dict = transfer._row_to_dict(row)
    assert row_dict["WCLab_ID"] == "LAB-123"
