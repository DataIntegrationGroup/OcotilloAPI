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
from __future__ import annotations

from types import SimpleNamespace
import uuid

from transfers.chemistry_sampleinfo import ChemistrySampleInfoTransferer
from transfers.hydraulicsdata import HydraulicsDataTransferer
from transfers.major_chemistry import MajorChemistryTransferer
from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer
from transfers.radionuclides import RadionuclidesTransferer
from transfers.surface_water_data import SurfaceWaterDataTransferer
from transfers.weather_data import WeatherDataTransferer


def _make_transferer(cls, **attrs):
    transferer = cls.__new__(cls)
    transferer.errors = []
    transferer.flags = {}
    transferer.source_table = getattr(cls, "source_table", "Test")
    for key, value in attrs.items():
        setattr(transferer, key, value)
    return transferer


def test_major_chemistry_preserves_empty_strings():
    transferer = _make_transferer(MajorChemistryTransferer)
    sample_pt_id = uuid.uuid4()
    global_id = uuid.uuid4()
    row = {
        "SamplePtID": sample_pt_id,
        "GlobalID": global_id,
        "SamplePointID": "",
        "Analyte": "",
        "Symbol": "",
        "Units": "",
        "Notes": "",
    }

    result = transferer._row_dict(row)

    assert result["SamplePointID"] == ""
    assert result["Analyte"] == ""
    assert result["Symbol"] == ""
    assert result["Units"] == ""
    assert result["Notes"] == ""


def test_minor_trace_chemistry_preserves_empty_strings():
    sample_pt_id = uuid.uuid4()
    global_id = uuid.uuid4()
    transferer = _make_transferer(
        MinorTraceChemistryTransferer, _sample_pt_ids={sample_pt_id}
    )
    row = SimpleNamespace(
        SamplePtID=sample_pt_id,
        GlobalID=global_id,
        Analyte="",
        Units="",
        Symbol="",
        AnalysisMethod="",
        Notes="",
        AnalysesAgency="",
        VolumeUnit="",
    )

    result = transferer._row_to_dict(row)

    assert result["analyte"] == ""
    assert result["units"] == ""
    assert result["symbol"] == ""
    assert result["analysis_method"] == ""
    assert result["notes"] == ""
    assert result["analyses_agency"] == ""
    assert result["volume_unit"] == ""


def test_radionuclides_preserves_empty_strings():
    transferer = _make_transferer(RadionuclidesTransferer, _thing_id_by_sample_pt_id={})
    sample_pt_id = uuid.uuid4()
    global_id = uuid.uuid4()
    row = {
        "SamplePtID": sample_pt_id,
        "GlobalID": global_id,
        "SamplePointID": "",
        "Analyte": "",
        "Symbol": "",
        "Units": "",
        "AnalysesAgency": "",
        "WCLab_ID": "",
    }

    result = transferer._row_dict(row)

    assert result["SamplePointID"] == ""
    assert result["Analyte"] == ""
    assert result["Symbol"] == ""
    assert result["Units"] == ""
    assert result["AnalysesAgency"] == ""
    assert result["WCLab_ID"] == ""


def test_weather_data_preserves_empty_strings():
    transferer = _make_transferer(WeatherDataTransferer)
    row = {
        "LocationId": None,
        "PointID": "",
        "WeatherID": None,
        "OBJECTID": 1,
    }

    result = transferer._row_dict(row)

    assert result["PointID"] == ""


def test_surface_water_data_preserves_empty_strings():
    transferer = _make_transferer(SurfaceWaterDataTransferer)
    row = {
        "SurfaceID": uuid.uuid4(),
        "PointID": "",
        "OBJECTID": 1,
        "Discharge": "",
        "DischargeMethod": "",
        "DischargeUnits": "",
        "DischargeSource": "",
        "SiteNotes": "",
        "FieldMethodNotes": "",
        "FormationZone": "",
        "AqClass": "",
        "SourceNotes": "",
        "DataSource": "",
    }

    result = transferer._row_dict(row)

    assert result["Discharge"] == ""
    assert result["DischargeMethod"] == ""
    assert result["DischargeUnits"] == ""
    assert result["DischargeSource"] == ""
    assert result["SiteNotes"] == ""
    assert result["FieldMethodNotes"] == ""
    assert result["FormationZone"] == ""
    assert result["AqClass"] == ""
    assert result["SourceNotes"] == ""
    assert result["DataSource"] == ""


def test_hydraulics_preserves_empty_strings():
    transferer = _make_transferer(HydraulicsDataTransferer, _thing_id_cache={"TEST": 1})
    row = {
        "GlobalID": uuid.uuid4(),
        "WellID": uuid.uuid4(),
        "PointID": "TEST",
        "HydraulicUnit": "",
        "HydraulicUnitType": "",
        "Hydraulic Remarks": "",
        "Data Source": "",
        "TestTop": 1,
        "TestBottom": 2,
    }

    result = transferer._row_dict(row)

    assert result["HydraulicUnit"] == ""
    assert result["HydraulicUnitType"] == ""
    assert result["Hydraulic Remarks"] == ""
    assert result["Data Source"] == ""


def test_chemistry_sampleinfo_preserves_empty_strings():
    transferer = _make_transferer(
        ChemistrySampleInfoTransferer, _thing_id_cache={"TEST": 1}
    )
    row = {
        "SamplePtID": uuid.uuid4(),
        "SamplePointID": "TEST",
        "WCLab_ID": "",
        "CollectionMethod": "",
        "CollectedBy": "",
        "AnalysesAgency": "",
        "SampleType": "",
        "SampleMaterialNotH2O": "",
        "WaterType": "",
        "StudySample": "",
        "DataSource": "",
        "SampleNotes": "",
        "LocationId": uuid.uuid4(),
        "OBJECTID": 1,
    }

    result = transferer._row_dict(row)

    assert result["WCLab_ID"] == ""
    assert result["CollectionMethod"] == ""
    assert result["CollectedBy"] == ""
    assert result["AnalysesAgency"] == ""
    assert result["SampleType"] == ""
    assert result["SampleMaterialNotH2O"] == ""
    assert result["WaterType"] == ""
    assert result["StudySample"] == ""
    assert result["DataSource"] == ""
    assert result["SampleNotes"] == ""
