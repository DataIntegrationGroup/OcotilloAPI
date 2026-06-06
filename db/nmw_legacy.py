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
"""1:1 staging mirror of the legacy NM_Wells SQL Server database.

PURPOSE
-------
These models are a FAITHFUL, column-for-column copy of the NM_Wells source
tables. They are a *staging layer*: data lands here unchanged from the SQL
dump, then a later transform phase maps it into the Ocotillo data model
(Location / Thing / FieldEvent / FieldActivity / Sample / Observation, plus
status_history, measuring_point_history, contact, publication, etc.).

This file mirrors the convention of ``db/nma_legacy.py`` (the NM_Aquifer
mirror): ``NMW_`` table prefix, original source column names preserved via the
first positional arg to ``mapped_column``, snake_case Python attributes.

SOURCE
------
NM_Wells is delivered as a SQL dump. Physical source table names are
``tbl_well_*`` (snake_case). To feed the existing CSV->Pandas->ORM transfer
pipeline, export each source table to CSV (same flow as ``nma_csv_cache``).

SCOPE (this commit)
-------------------
Mirrors the five "Migrate First / Main" tables that have an authoritative
field-level mapping in the planning workbook
("NM_Wells + Subsurface library.xlsx", sheet 3):

    tbl_well_locations  -> NMW_WellLocations
    tbl_well_headers    -> NMW_WellHeaders
    tbl_well_records    -> NMW_WellRecords
    tbl_well_z_datum    -> NMW_WellZDatum
    tbl_well_samples    -> NMW_WellSamples

Also mirrors the Geothermal and Drill Stem Test "Migrate First" tables
(columns + lengths taken directly from the NM_Wells SQL dump DDL, so these are
more precise than the five Main tables above whose lengths the sheet omitted):

    Geothermal:
        tbl_gt_bht_headers  -> NMW_GtBhtHeaders     tbl_gt_bht_data    -> NMW_GtBhtData
        tbl_gt_conductivity -> NMW_GtConductivity   tbl_gt_heat_flow   -> NMW_GtHeatFlow
        tbl_gt_sum_heat_flow-> NMW_GtSumHeatFlow    tbl_gt_temp_depths -> NMW_GtTempDepths
        tbl_ws_intervals    -> NMW_WsIntervals
    Drill Stem Tests:
        tbl_ws_dst_headers  -> NMW_WsDstHeaders     tbl_ws_dst_intervals -> NMW_WsDstIntervals
        tbl_ws_dst_flow_history -> NMW_WsDstFlowHistory
        tbl_ws_dst_fluid_properties -> NMW_WsDstFluidProperties
        tbl_ws_dst_pressure -> NMW_WsDstPressure

Geothermal/DST relationship chains (kept as plain indexed GUID columns, NOT
enforced FKs, since this is staging):
    well_samples.SamplSetID <- gt_bht_headers / gt_temp_depths / gt_sum_heat_flow
                               / ws_intervals / ws_dst_headers (SamplSetID)
    gt_bht_headers.BHTGUID  <- gt_bht_data.BHTGUID
    ws_intervals.IntrvlGUID <- gt_conductivity / gt_heat_flow (IntrvlGUID)
    ws_dst_headers.DSTGUID  <- ws_dst_intervals.DSTGUID
    ws_dst_intervals.DSTInterval <- ws_dst_flow_history / ws_dst_fluid_properties
                                    / ws_dst_pressure (DSTInterval)
    well_records.RecrdSetID <- gt_sum_heat_flow.RecrdSetID

The transform of geothermal/DST into the Ocotillo model is not yet designed
(no field-level mapping in the workbook); see docs/nm_wells-migration.md.

TRANSFORM NOTES
---------------
Each column carries an inline note describing its eventual Ocotillo target
(from the mapping sheet). "Drop" = not carried into the Ocotillo model (kept
here only for staging fidelity / audit). See docs/nm_wells-migration.md for
the full plan and the cross-table relationship re-routing
(legacy RecrdSetID -> field_event).

TYPE MAPPING (SQL Server -> SQLAlchemy)
---------------------------------------
    uniqueidentifier -> postgresql UUID(as_uuid=True)
    int              -> Integer
    smallint         -> SmallInteger
    real / float     -> Float
    nvarchar         -> String      (source lengths not in the sheet; widened)
    datetime2        -> DateTime
    timestamp        -> LargeBinary (SQL Server rowversion; staging only)

TODO(verify): primary keys below are inferred from the mapping sheet /
relationship notes, not from source DDL. Confirm against the dump.
"""

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column

from db.base import Base


class NMW_WellLocations(Base):
    """1:1 mirror of NM_Wells ``tbl_well_locations`` (Main / Migrate First).

    Transform target: ``location`` (point from Lat/Long_dd83, state, county)
    plus a new ``NMW_Location`` table for the legacy PLSS/UTM attributes.
    """

    __tablename__ = "NMW_WellLocations"

    # TODO(verify PK): tbl has no clear GUID PK; OBJECTID is the identity col.
    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # Drop
    well_data_id = mapped_column(
        "WellDataID", UUID(as_uuid=True), index=True
    )  # -> NMW_Location.well_id (relates header/location/records)
    well_id_legacy = mapped_column("Well_ID", String)  # Drop
    import_id = mapped_column("Import_ID", Integer)  # Drop
    township = mapped_column("Township", Float)  # -> NMW_Location.township
    nors_tdir = mapped_column("NorS_TDir", String)  # -> NMW_Location.township_n_s
    range_ = mapped_column("Range", Float)  # -> NMW_Location.range
    eorw_rdir = mapped_column("EorW_RDir", String)  # -> NMW_Location.range_e_w
    sectn = mapped_column("Sectn", SmallInteger)  # -> NMW_Location.section
    sectn_part = mapped_column("SectnPart", String)  # -> NMW_Location.section_portion
    unit_letter = mapped_column("UnitLetter", String)  # -> NMW_Location.unit_letter
    utm_zone = mapped_column("UTM_zone", String)  # -> NMW_Location.utm_zone
    state = mapped_column("State", String)  # -> location.state
    county = mapped_column("County", String)  # -> location.county
    basin = mapped_column("Basin", String)  # -> NMW_Location.basin
    footage_ns = mapped_column("Footage_NS", Float)  # -> NMW_Location.footage_n_s
    nors_fdir = mapped_column("NorS_FDir", String)  # -> NMW_Location.direction_n_s
    footage_ew = mapped_column("Footage_EW", Float)  # -> NMW_Location.footage_e_w
    eorw_fdir = mapped_column("EorW_FDir", String)  # -> NMW_Location.direction_e_w
    lat_min = mapped_column("Lat_min", SmallInteger)  # Drop (mostly empty)
    lat_sec = mapped_column("Lat_sec", Float)  # Drop (mostly empty)
    long_deg = mapped_column("Long_deg", SmallInteger)  # Drop (mostly empty)
    long_min = mapped_column("Long_min", SmallInteger)  # Drop (mostly empty)
    long_sec = mapped_column("Long_sec", Float)  # Drop (mostly empty)
    lat_dd27 = mapped_column("Lat_dd27", Float)  # -> NMW_Location.latitutde_dd27
    long_dd27 = mapped_column("Long_dd27", Float)  # -> NMW_Location.longitude_dd27
    lat_dd83 = mapped_column("Lat_dd83", Float)  # -> location.point
    long_dd83 = mapped_column("Long_dd83", Float)  # -> location.point
    source_id = mapped_column("SourceID", String)  # -> publication.id
    source_datum = mapped_column("SourceDatum", String)  # -> NMW_Location.source_datum
    source_units = mapped_column("SourceUnits", String)  # -> NMW_Location.source_units
    loc_acc_type = mapped_column("LocAccType", String)  # Drop
    loc_acc_meas = mapped_column("LocAccMeas", String)  # Drop
    loc_acc_val = mapped_column("LocAccVal", Float)  # Drop
    duplicated = mapped_column("Duplicated", SmallInteger)  # Drop
    exclude = mapped_column("Exclude", SmallInteger)  # Drop
    comments = mapped_column("Comments", String)  # (unmapped)
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)
    api = mapped_column("API", String)  # Drop


class NMW_WellHeaders(Base):
    """1:1 mirror of NM_Wells ``tbl_well_headers`` (Main / Migrate First).

    Transform target: ``thing`` (name/type/well_depth/completion_date),
    ``status_history``, ``contact`` (operator + owner), ``publication``,
    ``thing_geologic_formation_association``, ``thing_id_link.alternate_id``,
    plus new ``well_detail`` and ``well_purpose`` tables.
    """

    __tablename__ = "NMW_WellHeaders"

    object_id = mapped_column("OBJECTID", Integer)  # Drop
    # WellDataID is the key relating header <-> location <-> records.
    well_data_id = mapped_column(
        "WellDataID", UUID(as_uuid=True), primary_key=True
    )  # Keep
    well_spot_id = mapped_column(
        "WellSpotID", UUID(as_uuid=True)
    )  # Drop (purpose unclear)
    api = mapped_column("API", String)  # -> thing_id_link.alternate_id
    well_class = mapped_column("WellClass", String)  # -> thing.type
    well_type = mapped_column("WellType", String)  # -> well_purpose.purpose
    well_orient = mapped_column("WellOrient", String)  # -> well_detail.well_orient
    cur_well_nam = mapped_column("CurWellNam", String)  # -> thing.name
    cur_well_num = mapped_column("CurWellNum", String)  # -> well_detail.well_number
    cur_status = mapped_column("CurStatus", String)  # -> status_history.status
    prd_pool_cnt = mapped_column("PrdPoolCnt", SmallInteger)  # Drop
    cur_operatr = mapped_column("CurOperatr", String)  # -> contact.name (type=operator)
    cur_owner = mapped_column("CurOwner", String)  # -> contact.name (type=owner)
    total_depth = mapped_column("TotalDepth", Float)  # -> thing.well_depth
    well_tvd = mapped_column("Well_TVD", Float)  # Drop
    fm_td = mapped_column("Fm_TD", String)  # -> thing_geologic_formation_association.id
    age_td = mapped_column("Age_TD", String)  # Drop
    spud_date = mapped_column("SpudDate", DateTime)  # Drop
    compl_date = mapped_column("ComplDate", DateTime)  # -> thing.well_completion_date
    plug_date = mapped_column("PlugDate", DateTime)  # Drop
    plug_back = mapped_column("PlugBack", Float)  # Drop
    bridge_plug = mapped_column("BridgePlug", String)  # Drop
    scout_tickt = mapped_column("ScoutTickt", SmallInteger)  # Drop
    dwn_hole_sur = mapped_column("DwnHoleSur", SmallInteger)  # Drop
    geol_log = mapped_column("GeolLog", SmallInteger)  # Drop
    geophys_log = mapped_column("Geophyslog", SmallInteger)  # Drop
    gthrm_exist = mapped_column("GthrmExist", SmallInteger)  # Drop
    petro_data = mapped_column("PetroData", SmallInteger)  # Drop
    core_exists = mapped_column("CoreExists", SmallInteger)  # Drop
    cuttings = mapped_column("Cuttings", SmallInteger)  # Drop
    sample_data = mapped_column("SampleData", SmallInteger)  # Drop
    comments = mapped_column("Comments", String)  # -> well_detail.comments
    import_id = mapped_column("Import_ID", String)  # Drop
    import_db = mapped_column("Import_DB", String)  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_WellRecords(Base):
    """1:1 mirror of NM_Wells ``tbl_well_records`` (Main / Migrate First).

    Transform target: ``field_event`` (+ ``field_activity``). The legacy
    wells -> records relationship (RecrdSetID) is re-routed to
    wells -> field_event during transform. RecrdClass tags which records are
    geothermal.
    """

    __tablename__ = "NMW_WellRecords"

    object_id = mapped_column("OBJECTID", Integer)  # Drop
    recrd_set_id = mapped_column(
        "RecrdSetID", UUID(as_uuid=True), primary_key=True
    )  # -> field_event.id
    well_data_id = mapped_column(
        "WellDataID", UUID(as_uuid=True), index=True
    )  # FK -> header/location WellDataID
    recrd_class = mapped_column("RecrdClass", String)  # -> field_activity.activity_type
    source_id = mapped_column(
        "SourceID", String
    )  # -> publication.id (text in source, not a real FK)
    action_date = mapped_column("ActionDate", DateTime)  # -> field_event.event_date
    well_name = mapped_column("WellName", String)  # Drop
    well_number = mapped_column("WellNumber", String)  # Drop
    api_suffix = mapped_column("API_suffix", String)  # Drop
    entered_by = mapped_column("EnteredBy", String)  # Drop
    entry_date = mapped_column("EntryDate", DateTime)  # Drop
    comments = mapped_column("Comments", String)  # -> field_event.notes


class NMW_WellZDatum(Base):
    """1:1 mirror of NM_Wells ``tbl_well_z_datum`` (Main / Migrate First).

    Transform target: ``measuring_point_history`` (elevation -> height,
    datum -> description, units/source -> new fields).
    """

    __tablename__ = "NMW_WellZDatum"

    object_id = mapped_column("OBJECTID", Integer)  # Drop
    recrdset_id = mapped_column(
        "RecrdsetID", UUID(as_uuid=True), index=True
    )  # FK -> records
    elev_gl = mapped_column(
        "Elev_GL", Float
    )  # -> measuring_point_history.measuring_point_height
    elev_df = mapped_column(
        "Elev_DF", Float
    )  # -> measuring_point_history.measuring_point_height
    elev_kb = mapped_column(
        "Elev_KB", Float
    )  # -> measuring_point_history.measuring_point_height
    elev_unspc = mapped_column(
        "Elev_unspc", Float
    )  # -> measuring_point_history.measuring_point_height
    datum_elev = mapped_column("DatumElev", Float)  # Drop (redundant)
    depth_datum = mapped_column(
        "DepthDatum", String
    )  # -> measuring_point_history.measuring_point_description
    depth_units = mapped_column(
        "DepthUnits", String
    )  # -> measuring_point_history.measuring_point_units [new field]
    z_datum = mapped_column("Z_datum", String)  # Drop (only 7 records)
    z_units = mapped_column("Z_units", String)  # Drop
    elev_source = mapped_column(
        "ElevSource", String
    )  # -> measuring_point_history.source [new field]
    elv_acc_type = mapped_column("ElvAccType", String)  # Drop
    elv_acc_meas = mapped_column("ElvAccMeas", String)  # Drop
    elv_acc_val = mapped_column("ElvAccVal", Float)  # Drop
    comments = mapped_column("Comments", String)  # Drop
    # TODO(verify PK): GlobalID assumed PK.
    global_id = mapped_column("GlobalID", UUID(as_uuid=True), primary_key=True)  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_WellSamples(Base):
    """1:1 mirror of NM_Wells ``tbl_well_samples`` (Main / Migrate First).

    Transform target: ``sample`` (date/notes/created_by) + ``observation``
    (depth units). The many boolean attribute flags (Porosity, Geothermal,
    etc.) are dropped (mostly empty in source).
    """

    __tablename__ = "NMW_WellSamples"

    object_id = mapped_column("OBJECTID", Integer)  # Drop
    sampl_set_id = mapped_column(
        "SamplSetID", UUID(as_uuid=True), primary_key=True
    )  # -> sample.id
    recrdset_id = mapped_column(
        "RecrdsetID", UUID(as_uuid=True), index=True
    )  # -> field_activity.id
    smp_set_name = mapped_column("SmpSetName", String)  # Drop
    sampl_class = mapped_column("SamplClass", String)  # Drop (mostly 'data')
    sample_type = mapped_column("SampleType", String)  # Drop (mostly empty)
    sample_fm = mapped_column("SampleFm", String)  # Drop (mostly empty)
    sample_loc = mapped_column("SampleLoc", String)  # Drop (no entries)
    sample_date = mapped_column("SampleDate", DateTime)  # -> sample.sample_date
    from_depth = mapped_column("From_Depth", Float)  # -> observation (depth)
    to_depth = mapped_column("To_Depth", Float)  # -> observation (depth)
    smp_dp_unt = mapped_column("SmpDpUnt", String)  # -> observation.unit
    from_tvd = mapped_column("From_TVD", Float)  # Drop
    to_tvd = mapped_column("To_TVD", Float)  # Drop
    from_elev = mapped_column("From_Elev", Float)  # Drop (empty)
    to_elev = mapped_column("To_Elev", Float)  # Drop (empty)
    porosity = mapped_column("Porosity", SmallInteger)  # Drop
    permeablty = mapped_column("Permeablty", SmallInteger)  # Drop
    density = mapped_column("Density", SmallInteger)  # Drop
    dst_tests = mapped_column("DST_Tests", SmallInteger)  # Drop
    thin_sect = mapped_column("ThinSect", SmallInteger)  # Drop
    geochron = mapped_column("Geochron", SmallInteger)  # Drop
    geochem = mapped_column("Geochem", SmallInteger)  # Drop
    geothermal = mapped_column("Geothermal", SmallInteger)  # Drop
    whole_rock = mapped_column("WholeRock", SmallInteger)  # Drop
    paleontlgy = mapped_column("Paleontlgy", SmallInteger)  # Drop
    entered_by = mapped_column("EnteredBy", String)  # -> sample.created_by_name
    entry_date = mapped_column("EntryDate", DateTime)  # -> sample.created_at
    notes = mapped_column("Notes", String)  # -> sample.notes
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


# =============================================================================
# GEOTHERMAL (Area=Geothermal, "Migrate First")
# =============================================================================


class NMW_GtBhtHeaders(Base):
    """1:1 mirror of NM_Wells ``tbl_gt_bht_headers`` (bottom-hole-temp header)."""

    __tablename__ = "NMW_GtBhtHeaders"

    object_id = mapped_column("OBJECTID", Integer)  # Drop (identity)
    bht_guid = mapped_column("BHTGUID", UUID(as_uuid=True), primary_key=True)
    sampl_set_id = mapped_column(
        "SamplSetID", UUID(as_uuid=True), index=True
    )  # FK -> well_samples.SamplSetID
    bore_dia = mapped_column("BoreDia", Float)
    bore_units = mapped_column("BoreUnits", String(16))
    drill_fluid = mapped_column("DrillFluid", String(16))
    temp_unit = mapped_column("TempUnit", String(1))
    fld_salinity = mapped_column("FldSalinity", Float)
    fld_rstvity = mapped_column("FldRstvity", Float)
    fluid_ph = mapped_column("Fluid_pH", Float)
    fld_density = mapped_column("FldDensity", Float)
    fld_level = mapped_column("FldLevel", Float)
    fld_viscsty = mapped_column("FldViscsty", Float)
    fluid_loss = mapped_column("FluidLoss", String(50))
    notes = mapped_column("Notes", String(255))
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_GtBhtData(Base):
    """1:1 mirror of NM_Wells ``tbl_gt_bht_data`` (BHT readings)."""

    __tablename__ = "NMW_GtBhtData"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    bht_guid = mapped_column(
        "BHTGUID", UUID(as_uuid=True), index=True
    )  # FK -> gt_bht_headers.BHTGUID
    depth = mapped_column("Depth", Float)
    bht = mapped_column("BHT", Float)
    temp_unit = mapped_column("TempUnit", String(5))
    hrs_snce_cir = mapped_column("HrsSnceCir", Float)
    date_measrd = mapped_column("DateMeasrd", DateTime)
    comments = mapped_column("Comments", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_WsIntervals(Base):
    """1:1 mirror of NM_Wells ``tbl_ws_intervals`` (sample depth intervals)."""

    __tablename__ = "NMW_WsIntervals"

    object_id = mapped_column("OBJECTID", Integer)  # Drop (identity)
    intrvl_guid = mapped_column("IntrvlGUID", UUID(as_uuid=True), primary_key=True)
    sampl_set_id = mapped_column(
        "SamplSetID", UUID(as_uuid=True), index=True
    )  # FK -> well_samples.SamplSetID
    sample_id = mapped_column("SampleID", String(128))
    from_depth = mapped_column("From_Depth", Float)
    to_depth = mapped_column("To_Depth", Float)
    from_tvd = mapped_column("From_TVD", Float)
    to_tvd = mapped_column("To_TVD", Float)
    from_elev = mapped_column("From_Elev", Float)
    to_elev = mapped_column("To_Elev", Float)
    intv_notes = mapped_column("Intv_Notes", String(255))
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_GtConductivity(Base):
    """1:1 mirror of NM_Wells ``tbl_gt_conductivity`` (thermal conductivity)."""

    __tablename__ = "NMW_GtConductivity"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    intrvl_guid = mapped_column(
        "IntrvlGUID", UUID(as_uuid=True), index=True
    )  # FK -> ws_intervals.IntrvlGUID
    cnductvity = mapped_column("Cnductvity", Float)
    cnduct_unit = mapped_column("CnductUnit", String(3))
    comments = mapped_column("Comments", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_GtHeatFlow(Base):
    """1:1 mirror of NM_Wells ``tbl_gt_heat_flow`` (per-interval heat flow)."""

    __tablename__ = "NMW_GtHeatFlow"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    intrvl_guid = mapped_column(
        "IntrvlGUID", UUID(as_uuid=True), index=True
    )  # FK -> ws_intervals.IntrvlGUID
    gradient = mapped_column("Gradient", Float)
    ka = mapped_column("Ka", Float)
    ka_unit = mapped_column("Ka_unit", String(3))
    pm = mapped_column("Pm", Float)
    kpr = mapped_column("Kpr", Float)
    kpr_unit = mapped_column("Kpr_unit", String(3))
    q = mapped_column("Q", Float)
    q_unit = mapped_column("Q_unit", String(3))
    comments = mapped_column("Comments", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_GtSumHeatFlow(Base):
    """1:1 mirror of NM_Wells ``tbl_gt_sum_heat_flow`` (summary heat flow)."""

    __tablename__ = "NMW_GtSumHeatFlow"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    recrd_set_id = mapped_column(
        "RecrdSetID", UUID(as_uuid=True), index=True
    )  # FK -> well_records.RecrdSetID
    sampl_set_id = mapped_column(
        "SamplSetID", UUID(as_uuid=True), index=True
    )  # FK -> well_samples.SamplSetID
    lith_class = mapped_column("LithClass", String(50))
    unit_basis = mapped_column("UnitBasis", String(16))
    unit_name = mapped_column("UnitName", String(128))
    geo_id = mapped_column("GeoID", String(16))
    from_depth = mapped_column("FromDepth", Float)
    to_depth = mapped_column("ToDepth", Float)
    depth_unit = mapped_column("DepthUnit", String(8))
    from_elev = mapped_column("From_Elev", Float)
    to_elev = mapped_column("To_Elev", Float)
    therml_grad = mapped_column("ThermlGrad", Float)
    tg_error = mapped_column("TGError", Float)
    grad_unit = mapped_column("GradUnit", String(3))
    tgrad_range = mapped_column("TGradRange", String(15))
    sample_type = mapped_column("SampleType", String(50))
    num_samples = mapped_column("NumSamples", SmallInteger)
    therml_cond = mapped_column("ThermlCond", Float)
    tcond_error = mapped_column("TCondError", Float)
    tcond_unit = mapped_column("TCondUnit", String(3))
    tcond_range = mapped_column("TCondRange", String(15))
    heat_flow = mapped_column("HeatFlow", Float)
    ht_flow_err = mapped_column("HtFlowErr", Float)
    ht_flow_unit = mapped_column("HtFlowUnit", String(3))
    ht_flow_est = mapped_column("HtFlowEst", Float)
    quality = mapped_column("Quality", String(50))
    comments = mapped_column("Comments", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_GtTempDepths(Base):
    """1:1 mirror of NM_Wells ``tbl_gt_temp_depths`` (temp-vs-depth profile)."""

    __tablename__ = "NMW_GtTempDepths"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    sampl_set_id = mapped_column(
        "SamplSetID", UUID(as_uuid=True), index=True
    )  # FK -> well_samples.SamplSetID
    depth = mapped_column("Depth", Float)
    temp = mapped_column("Temp", Float)
    temp_unit = mapped_column("TempUnit", String(1))
    intrvl_grad = mapped_column("IntrvlGrad", Float)
    comments = mapped_column("Comments", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


# =============================================================================
# DRILL STEM TESTS (Area=Drill Stem Tests, "Migrate First")
# =============================================================================


class NMW_WsDstHeaders(Base):
    """1:1 mirror of NM_Wells ``tbl_ws_dst_headers`` (DST header)."""

    __tablename__ = "NMW_WsDstHeaders"

    object_id = mapped_column("OBJECTID", Integer)  # Drop (identity)
    dst_guid = mapped_column("DSTGUID", UUID(as_uuid=True), primary_key=True)
    sampl_set_id = mapped_column(
        "SamplSetID", UUID(as_uuid=True), index=True
    )  # FK -> well_samples.SamplSetID
    test_type = mapped_column("TestType", String(50))
    dst_oprator = mapped_column("DSTOprator", String(50))
    press_units = mapped_column("PressUnits", String(8))
    temp_unit = mapped_column("TempUnit", String(1))
    pipe_dia_unt = mapped_column("PipeDiaUnt", String(8))
    pipe_len_unt = mapped_column("PipeLenUnt", String(8))
    choke_siz_un = mapped_column("ChokeSizUn", String(8))
    notes = mapped_column("Notes", String(255))


class NMW_WsDstIntervals(Base):
    """1:1 mirror of NM_Wells ``tbl_ws_dst_intervals`` (DST interval)."""

    __tablename__ = "NMW_WsDstIntervals"

    object_id = mapped_column("OBJECTID", Integer)  # Drop (identity)
    dst_interval = mapped_column("DSTInterval", UUID(as_uuid=True), primary_key=True)
    dst_guid = mapped_column(
        "DSTGUID", UUID(as_uuid=True), index=True
    )  # FK -> ws_dst_headers.DSTGUID
    dst_name = mapped_column("DSTName", String(128))
    target_fm = mapped_column("TargetFm", String(16))
    dst_date = mapped_column("DSTDate", DateTime)
    dst_number = mapped_column("DSTNumber", SmallInteger)
    status = mapped_column("Status", String(255))
    status_date = mapped_column("StatusDate", DateTime)
    packr_from = mapped_column("PackrFrom", Float)
    packer_to = mapped_column("PackerTo", Float)
    srf_choke_sz = mapped_column("SrfChokeSz", Float)
    bot_choke_sz = mapped_column("BotChokeSz", Float)
    pipe_dia = mapped_column("PipeDia", Float)
    pipe_length = mapped_column("PipeLength", Float)
    notes = mapped_column("Notes", String(255))
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_WsDstFlowHistory(Base):
    """1:1 mirror of NM_Wells ``tbl_ws_dst_flow_history`` (DST flow events)."""

    __tablename__ = "NMW_WsDstFlowHistory"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    dst_interval = mapped_column(
        "DSTInterval", UUID(as_uuid=True), index=True
    )  # FK -> ws_dst_intervals.DSTInterval
    operation = mapped_column("Operation", String(255))
    start_time = mapped_column("StartTime", DateTime)
    end_time = mapped_column("EndTime", DateTime)
    duration = mapped_column("Duration", Float)
    pressure = mapped_column("Pressure", Float)
    temp = mapped_column("Temp", Float)
    recov_colmn = mapped_column("RecovColmn", Float)
    recov_type = mapped_column("RecovType", String(255))
    notes = mapped_column("Notes", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_WsDstFluidProperties(Base):
    """1:1 mirror of NM_Wells ``tbl_ws_dst_fluid_properties`` (recovered fluid)."""

    __tablename__ = "NMW_WsDstFluidProperties"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    dst_interval = mapped_column(
        "DSTInterval", UUID(as_uuid=True), index=True
    )  # FK -> ws_dst_intervals.DSTInterval
    source_loc = mapped_column("SourceLoc", String(255))
    resistivty = mapped_column("Resistivty", Float)
    temp = mapped_column("Temp", Float)
    chlorides = mapped_column("Chlorides", Float)
    notes = mapped_column("Notes", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


class NMW_WsDstPressure(Base):
    """1:1 mirror of NM_Wells ``tbl_ws_dst_pressure`` (DST pressure readings)."""

    __tablename__ = "NMW_WsDstPressure"

    object_id = mapped_column("OBJECTID", Integer, primary_key=True)  # identity PK
    dst_interval = mapped_column(
        "DSTInterval", UUID(as_uuid=True), index=True
    )  # FK -> ws_dst_intervals.DSTInterval
    prs_gage_dpt = mapped_column("PrsGageDpt", Float)
    blanked_off = mapped_column("BlankedOff", SmallInteger)
    in_sht_in_min = mapped_column("InShtInMin", Float)
    flw_prs_in_min = mapped_column("FlwPrsInMin", Float)
    prs_in_sht_in = mapped_column("PrsInShtIn", Float)
    prs_init_clsd_in = mapped_column("PrsInitClsdIn", Float)
    fn_sht_in_min = mapped_column("FnShtInMin", Float)
    flw_prs_fin_min = mapped_column("FlwPrsFinMin", Float)
    prs_fn_sht_in = mapped_column("PrsFnShtIn", Float)
    sht_in_pr_mth = mapped_column("ShtInPrMth", String(255))
    hydrost_prs_in = mapped_column("HydrostPrsIn", Float)
    hyd_st_prs_fl = mapped_column("HydStPrsFl", Float)
    hydst_pr_mth = mapped_column("HydstPrMth", String(255))
    equil_press = mapped_column("EquilPress", Float)
    eql_prs_mth = mapped_column("EqlPrsMth", String(255))
    flow_prs_min = mapped_column("FlowPrsMin", Float)
    flow_prs_max = mapped_column("FlowPrsMax", Float)
    flow_prs_mth = mapped_column("FlowPrsMth", String(255))
    dst_fluid = mapped_column("DSTFluid", String(128))
    fm_temp = mapped_column("FmTemp", Float)
    temp_corrtn = mapped_column("TempCorrtn", Float)
    temp_flowng = mapped_column("TempFlowng", Float)
    temp_unit = mapped_column("TempUnit", String(5))
    notes = mapped_column("Notes", String(255))
    global_id = mapped_column("GlobalID", UUID(as_uuid=True))  # Drop
    ssma_timestamp = mapped_column("SSMA_TimeStamp", LargeBinary)  # Drop (rowversion)


# =============================================================================
# TODO(remaining "Migrate First" tables, no DDL/mapping yet)
# -----------------------------------------------------------------------------
#   Publications:  tbl_sources
#   Subsurface Library:  dst_scan, log_scanned, Well_Header, well_operators
# See docs/nm_wells-migration.md for the full inventory + recommendations.
# =============================================================================


# ============= EOF =============================================
