import uuid

import pandas as pd

from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer


def test_row_to_dict_includes_wclab_id():
    # Bypass __init__ so we can stub the cache without hitting the DB.
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
    assert row_dict["nma_WCLab_ID"] == "LAB-123"
    assert row_dict["nma_sample_point_id"] == "POINT-1"


def test_row_to_dict_missing_sample_point_id_returns_none_and_captures_error():
    # Bypass __init__ so we can stub the cache without hitting the DB.
    transfer = MinorTraceChemistryTransferer.__new__(MinorTraceChemistryTransferer)
    sample_pt_id = uuid.uuid4()
    transfer._sample_info_cache = {sample_pt_id: 1}
    transfer.flags = {}
    transfer.errors = []

    row = pd.Series(
        {
            "SamplePtID": str(sample_pt_id),
            "GlobalID": str(uuid.uuid4()),
            # SamplePointID intentionally missing
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
    assert row_dict is None
    assert len(transfer.errors) == 1
    error = transfer.errors[0]
    assert error["field"] == "SamplePointID"
    assert "Missing SamplePointID" in error["error"]
