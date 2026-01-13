"""
MajorChemistryAdmin view for NMSampleLocations.
"""

from admin.views.base import OcotilloModelView
from starlette_admin import ExportType, BaseField


class MajorChemistryAdmin(OcotilloModelView):
    """
    Admin view for MajorChemistry legacy model.

    export_fields, left undefined, defaults to None, which allows all fields
    to be exported by default
    """

    name = "Major Chemistry"
    label = "Major Chemistry"
    icon = "fa-solid fa-flask"

    fields = [
        BaseField("global_id", label="GlobalID"),
        BaseField("sample_pt_id", label="SamplePtID"),
        BaseField("sample_point_id", label="SamplePointID"),
        BaseField("analyte", label="Analyte"),
        BaseField("symbol", label="Symbol"),
        BaseField("sample_value", label="SampleValue"),
        BaseField("units", label="Units"),
        BaseField("uncertainty", label="Uncertainty"),
        BaseField("analysis_method", label="AnalysisMethod"),
        BaseField("analysis_date", label="AnalysisDate"),
        BaseField("notes", label="Notes"),
        BaseField("volume", label="Volume"),
        BaseField("object_id", label="OBJECTID"),
        BaseField("analyses_agency", label="AnalysesAgency"),
        BaseField("wc_lab_id", label="WCLab_ID"),
    ]

    sortable_fields = [
        "sample_point_id",
        "analyte",
        "symbol",
        "sample_value",
        "units",
        "uncertainty",
        "analysis_method",
        "analysis_date",
        "volume",
        "analyses_agency",
        "wc_lab_id",
    ]

    fields_default_sort = (("analysis_date", True),)

    searchable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "analyte",
        "symbol",
        "sample_value",
        "units",
        "uncertainty",
        "analysis_method",
        "analysis_date",
        "notes",
        "volume",
        "object_id",
        "analyses_agency",
        "wc_lab_id",
    ]

    exclude_fields_from_edit = [
        "global_id",
        "object_id",
        "sample_pt_id",
    ]

    export_types = [ExportType.CSV]

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False
