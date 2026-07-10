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
"""API contract for bulk submission of NM_Wells (NMW_) data.

This is the JSON contract for BDMS-960: the spreadsheet-based well submission
form is parsed (client side) into one ``NMWSubmission`` per well and posted as
a ``list[NMWSubmission]`` to ``POST /nmw/bulk-upload``.

DESIGN
------
The submitter never supplies the internal keys of the staging tables. The
server owns them:

* GUID primary keys (WellDataID, RecrdSetID, SamplSetID, BHTGUID, IntrvlGUID,
  DSTGUID, DSTInterval) are generated server side (uuid4).
* Integer ``OBJECTID`` primary keys are filled by database identity sequences
  (migration ``<id>_nmw_objectid_identity``).
* Foreign-key link columns are wired from the nesting, not from the payload.
* ``GlobalID`` columns are dropped (staging artifact); not accepted as input.

Every ``*In`` model therefore contains ONLY the domain columns of its mirror
table in ``db/nmw_legacy.py``. Field names match the ORM attribute names so the
service can build rows with ``Model(**payload.model_dump(...))``.

Fields are almost all optional: the source tables are overwhelmingly nullable
and this is a faithful staging load, not a curated model. Row-level and
cross-row requirements are enforced in ``services/nmw_submission.py`` so that a
single invalid well can abort the whole batch with a readable message (the
chemistry-LIMS behavior), rather than raising a 422 that hides which well/row
failed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.functional_validators import BeforeValidator


def _empty_str_to_none(value):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


OptionalText = Annotated[str | None, BeforeValidator(_empty_str_to_none)]
OptionalFloat = Annotated[float | None, BeforeValidator(_empty_str_to_none)]
OptionalInt = Annotated[int | None, BeforeValidator(_empty_str_to_none)]
OptionalDatetime = Annotated[datetime | None, BeforeValidator(_empty_str_to_none)]
OptionalUUID = Annotated[UUID | None, BeforeValidator(_empty_str_to_none)]


class _NMWInBase(BaseModel):
    """Shared config for every submission leaf model.

    ``extra="forbid"`` makes the contract strict: an unknown column name is a
    validation error rather than a silently dropped field, which is what you
    want for a form that maps to a fixed set of staging columns.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# =============================================================================
# Publication registry (standalone; joined by free-text SourceID)
# =============================================================================


class NMWSourceIn(_NMWInBase):
    """One row of ``NMW_Sources``. ``source_id`` is the text join key."""

    source_id: str
    first_auth: OptionalText = None
    pub_year: OptionalText = None
    title: OptionalText = None
    journal: OptionalText = None
    volume: OptionalText = None
    page_no: OptionalText = None
    report_no: OptionalText = None
    publisher: OptionalText = None
    city: OptionalText = None
    url: OptionalText = None
    comments: OptionalText = None


# =============================================================================
# Geothermal leaves (deepest first)
# =============================================================================


class NMWGtConductivityIn(_NMWInBase):
    """One row of ``NMW_GtConductivity`` (child of a ws_interval)."""

    cnductvity: OptionalFloat = None
    cnduct_unit: OptionalText = None
    comments: OptionalText = None


class NMWGtHeatFlowIn(_NMWInBase):
    """One row of ``NMW_GtHeatFlow`` (child of a ws_interval)."""

    gradient: OptionalFloat = None
    ka: OptionalFloat = None
    ka_unit: OptionalText = None
    pm: OptionalFloat = None
    kpr: OptionalFloat = None
    kpr_unit: OptionalText = None
    q: OptionalFloat = None
    q_unit: OptionalText = None
    comments: OptionalText = None


class NMWGtBhtDataIn(_NMWInBase):
    """One row of ``NMW_GtBhtData`` (BHT reading, child of a bht_header)."""

    depth: OptionalFloat = None
    bht: OptionalFloat = None
    temp_unit: OptionalText = None
    hrs_snce_cir: OptionalFloat = None
    date_measrd: OptionalDatetime = None
    comments: OptionalText = None


class NMWGtTempDepthIn(_NMWInBase):
    """One row of ``NMW_GtTempDepths`` (temp-vs-depth, child of a sample)."""

    depth: OptionalFloat = None
    temp: OptionalFloat = None
    temp_unit: OptionalText = None
    intrvl_grad: OptionalFloat = None
    comments: OptionalText = None


class NMWGtSumHeatFlowIn(_NMWInBase):
    """One row of ``NMW_GtSumHeatFlow`` (child of a sample; also linked to the
    parent record via RecrdSetID, wired by the service)."""

    lith_class: OptionalText = None
    unit_basis: OptionalText = None
    unit_name: OptionalText = None
    geo_id: OptionalText = None
    from_depth: OptionalFloat = None
    to_depth: OptionalFloat = None
    depth_unit: OptionalText = None
    from_elev: OptionalFloat = None
    to_elev: OptionalFloat = None
    therml_grad: OptionalFloat = None
    tg_error: OptionalFloat = None
    grad_unit: OptionalText = None
    tgrad_range: OptionalText = None
    sample_type: OptionalText = None
    num_samples: OptionalInt = None
    therml_cond: OptionalFloat = None
    tcond_error: OptionalFloat = None
    tcond_unit: OptionalText = None
    tcond_range: OptionalText = None
    heat_flow: OptionalFloat = None
    ht_flow_err: OptionalFloat = None
    ht_flow_unit: OptionalText = None
    ht_flow_est: OptionalFloat = None
    quality: OptionalText = None
    comments: OptionalText = None


class NMWGtBhtHeaderIn(_NMWInBase):
    """One row of ``NMW_GtBhtHeaders`` (child of a sample). Owns bht_data."""

    bore_dia: OptionalFloat = None
    bore_units: OptionalText = None
    drill_fluid: OptionalText = None
    temp_unit: OptionalText = None
    fld_salinity: OptionalFloat = None
    fld_rstvity: OptionalFloat = None
    fluid_ph: OptionalFloat = None
    fld_density: OptionalFloat = None
    fld_level: OptionalFloat = None
    fld_viscsty: OptionalFloat = None
    fluid_loss: OptionalText = None
    notes: OptionalText = None

    bht_data: list[NMWGtBhtDataIn] = []


class NMWWsIntervalIn(_NMWInBase):
    """One row of ``NMW_WsIntervals`` (child of a sample). Owns conductivity
    and heat_flow."""

    sample_id: OptionalText = None
    from_depth: OptionalFloat = None
    to_depth: OptionalFloat = None
    from_tvd: OptionalFloat = None
    to_tvd: OptionalFloat = None
    from_elev: OptionalFloat = None
    to_elev: OptionalFloat = None
    intv_notes: OptionalText = None

    conductivity: list[NMWGtConductivityIn] = []
    heat_flow: list[NMWGtHeatFlowIn] = []


# =============================================================================
# Drill Stem Test leaves
# =============================================================================


class NMWWsDstFlowHistoryIn(_NMWInBase):
    """One row of ``NMW_WsDstFlowHistory`` (child of a dst_interval)."""

    operation: OptionalText = None
    start_time: OptionalDatetime = None
    end_time: OptionalDatetime = None
    duration: OptionalFloat = None
    pressure: OptionalFloat = None
    temp: OptionalFloat = None
    recov_column: OptionalFloat = None
    recov_type: OptionalText = None
    notes: OptionalText = None


class NMWWsDstFluidPropertiesIn(_NMWInBase):
    """One row of ``NMW_WsDstFluidProperties`` (child of a dst_interval)."""

    source_loc: OptionalText = None
    resistivity: OptionalFloat = None
    temp: OptionalFloat = None
    chlorides: OptionalFloat = None
    notes: OptionalText = None


class NMWWsDstPressureIn(_NMWInBase):
    """One row of ``NMW_WsDstPressure`` (child of a dst_interval)."""

    prs_gage_dpt: OptionalFloat = None
    blanked_off: OptionalInt = None
    in_sht_in_min: OptionalFloat = None
    flw_prs_in_min: OptionalFloat = None
    prs_in_sht_in: OptionalFloat = None
    prs_init_clsd_in: OptionalFloat = None
    fn_sht_in_min: OptionalFloat = None
    flw_prs_fin_min: OptionalFloat = None
    prs_fn_sht_in: OptionalFloat = None
    sht_in_pr_mth: OptionalText = None
    hydrost_prs_in: OptionalFloat = None
    hyd_st_prs_fl: OptionalFloat = None
    hydst_pr_mth: OptionalText = None
    equil_press: OptionalFloat = None
    eql_prs_mth: OptionalText = None
    flow_prs_min: OptionalFloat = None
    flow_prs_max: OptionalFloat = None
    flow_prs_mth: OptionalText = None
    dst_fluid: OptionalText = None
    fm_temp: OptionalFloat = None
    temp_corrtn: OptionalFloat = None
    temp_flowng: OptionalFloat = None
    temp_unit: OptionalText = None
    notes: OptionalText = None


class NMWWsDstIntervalIn(_NMWInBase):
    """One row of ``NMW_WsDstIntervals`` (child of a dst_header). Owns
    flow_history, fluid_properties, pressure."""

    dst_name: OptionalText = None
    target_fm: OptionalText = None
    dst_date: OptionalDatetime = None
    dst_number: OptionalInt = None
    status: OptionalText = None
    status_date: OptionalDatetime = None
    packr_from: OptionalFloat = None
    packer_to: OptionalFloat = None
    srf_choke_sz: OptionalFloat = None
    bot_choke_sz: OptionalFloat = None
    pipe_dia: OptionalFloat = None
    pipe_length: OptionalFloat = None
    notes: OptionalText = None

    flow_history: list[NMWWsDstFlowHistoryIn] = []
    fluid_properties: list[NMWWsDstFluidPropertiesIn] = []
    pressure: list[NMWWsDstPressureIn] = []


class NMWWsDstHeaderIn(_NMWInBase):
    """One row of ``NMW_WsDstHeaders`` (child of a sample). Owns
    dst_intervals."""

    test_type: OptionalText = None
    dst_operator: OptionalText = None
    press_units: OptionalText = None
    temp_unit: OptionalText = None
    pipe_dia_unt: OptionalText = None
    pipe_len_unt: OptionalText = None
    choke_siz_un: OptionalText = None
    notes: OptionalText = None

    dst_intervals: list[NMWWsDstIntervalIn] = []


# =============================================================================
# Core well hierarchy
# =============================================================================


class NMWWellSampleIn(_NMWInBase):
    """One row of ``NMW_WellSamples`` (child of a record). Owns the geothermal
    and DST subtrees."""

    smp_set_name: OptionalText = None
    sampl_class: OptionalText = None
    sample_type: OptionalText = None
    sample_fm: OptionalText = None
    sample_loc: OptionalText = None
    sample_date: OptionalDatetime = None
    from_depth: OptionalFloat = None
    to_depth: OptionalFloat = None
    smp_dp_unt: OptionalText = None
    from_tvd: OptionalFloat = None
    to_tvd: OptionalFloat = None
    from_elev: OptionalFloat = None
    to_elev: OptionalFloat = None
    porosity: OptionalInt = None
    permeablty: OptionalInt = None
    density: OptionalInt = None
    dst_tests: OptionalInt = None
    thin_sect: OptionalInt = None
    geochron: OptionalInt = None
    geochem: OptionalInt = None
    geothermal: OptionalInt = None
    whole_rock: OptionalInt = None
    paleontlgy: OptionalInt = None
    entered_by: OptionalText = None
    entry_date: OptionalDatetime = None
    notes: OptionalText = None

    intervals: list[NMWWsIntervalIn] = []
    bht_headers: list[NMWGtBhtHeaderIn] = []
    temp_depths: list[NMWGtTempDepthIn] = []
    sum_heat_flow: list[NMWGtSumHeatFlowIn] = []
    dst_headers: list[NMWWsDstHeaderIn] = []


class NMWWellZDatumIn(_NMWInBase):
    """One row of ``NMW_WellZDatum`` (child of a record)."""

    elev_gl: OptionalFloat = None
    elev_df: OptionalFloat = None
    elev_kb: OptionalFloat = None
    elev_unspc: OptionalFloat = None
    datum_elev: OptionalFloat = None
    depth_datum: OptionalText = None
    depth_units: OptionalText = None
    z_datum: OptionalText = None
    z_units: OptionalText = None
    elev_source: OptionalText = None
    elv_acc_type: OptionalText = None
    elv_acc_meas: OptionalText = None
    elv_acc_val: OptionalFloat = None
    comments: OptionalText = None


class NMWWellRecordIn(_NMWInBase):
    """One row of ``NMW_WellRecords`` (child of a well header). Owns z_data and
    samples."""

    recrd_class: OptionalText = None
    source_id: OptionalText = None
    action_date: OptionalDatetime = None
    well_name: OptionalText = None
    well_number: OptionalText = None
    api_suffix: OptionalText = None
    entered_by: OptionalText = None
    entry_date: OptionalDatetime = None
    comments: OptionalText = None

    z_data: list[NMWWellZDatumIn] = []
    samples: list[NMWWellSampleIn] = []


class NMWWellLocationIn(_NMWInBase):
    """The single ``NMW_WellLocations`` row for a well."""

    well_id_legacy: OptionalText = None
    import_id: OptionalInt = None
    township: OptionalFloat = None
    nors_tdir: OptionalText = None
    range_: OptionalFloat = None
    eorw_rdir: OptionalText = None
    sectn: OptionalInt = None
    sectn_part: OptionalText = None
    unit_letter: OptionalText = None
    utm_zone: OptionalText = None
    state: OptionalText = None
    county: OptionalText = None
    basin: OptionalText = None
    footage_ns: OptionalFloat = None
    nors_fdir: OptionalText = None
    footage_ew: OptionalFloat = None
    eorw_fdir: OptionalText = None
    lat_min: OptionalInt = None
    lat_sec: OptionalFloat = None
    long_deg: OptionalInt = None
    long_min: OptionalInt = None
    long_sec: OptionalFloat = None
    lat_dd27: OptionalFloat = None
    long_dd27: OptionalFloat = None
    lat_dd83: OptionalFloat = None
    long_dd83: OptionalFloat = None
    source_id: OptionalText = None
    source_datum: OptionalText = None
    source_units: OptionalText = None
    loc_acc_type: OptionalText = None
    loc_acc_meas: OptionalText = None
    loc_acc_val: OptionalFloat = None
    duplicated: OptionalInt = None
    exclude: OptionalInt = None
    comments: OptionalText = None
    api: OptionalText = None


class NMWWellHeaderIn(_NMWInBase):
    """The single ``NMW_WellHeaders`` row for a well (the submission root
    attributes)."""

    well_spot_id: OptionalUUID = None
    api: OptionalText = None
    well_class: OptionalText = None
    well_type: OptionalText = None
    well_orient: OptionalText = None
    cur_well_nam: OptionalText = None
    cur_well_num: OptionalText = None
    cur_status: OptionalText = None
    prd_pool_cnt: OptionalInt = None
    cur_operatr: OptionalText = None
    cur_owner: OptionalText = None
    total_depth: OptionalFloat = None
    well_tvd: OptionalFloat = None
    fm_td: OptionalText = None
    age_td: OptionalText = None
    spud_date: OptionalDatetime = None
    compl_date: OptionalDatetime = None
    plug_date: OptionalDatetime = None
    plug_back: OptionalFloat = None
    bridge_plug: OptionalText = None
    scout_tickt: OptionalInt = None
    dwn_hole_sur: OptionalInt = None
    geol_log: OptionalInt = None
    geophys_log: OptionalInt = None
    gthrm_exist: OptionalInt = None
    petro_data: OptionalInt = None
    core_exists: OptionalInt = None
    cuttings: OptionalInt = None
    sample_data: OptionalInt = None
    comments: OptionalText = None
    import_id: OptionalText = None
    import_db: OptionalText = None


class NMWSubmission(_NMWInBase):
    """One well and everything attached to it.

    ``header`` is required (it becomes the root ``NMW_WellHeaders`` row). The
    service additionally requires the header to carry at least one identifier
    (``api`` or ``cur_well_nam``) so the well is addressable.
    """

    header: NMWWellHeaderIn
    location: NMWWellLocationIn | None = None
    records: list[NMWWellRecordIn] = []
    sources: list[NMWSourceIn] = []


# =============================================================================
# Response
# =============================================================================


class NMWBulkUploadSummary(BaseModel):
    total_submissions: int
    total_wells_imported: int
    total_rows_written: int
    validation_errors: int


class NMWBulkUploadWell(BaseModel):
    submission_index: int
    well_data_id: str
    api: str | None
    well_name: str | None
    rows_written: int


class NMWBulkUploadResponse(BaseModel):
    summary: NMWBulkUploadSummary
    wells: list[NMWBulkUploadWell]
    validation_errors: list[str]


# ============= EOF =============================================
