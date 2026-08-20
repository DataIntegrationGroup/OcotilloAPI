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

"""1:1 staging mirror of the McLemore critical-minerals chemistry workbook.

PURPOSE
-------
These models are a FAITHFUL copy of the Earth MRI "Database of chemical
analyses of critical minerals deposits in New Mexico" workbook
(``McLemoreMasterChem``, compiled by V.T. McLemore et al., NMBGMR). They are a
*staging layer*: workbook cells land here unchanged, then a later transform
phase maps them into the Ocotillo data model (Location / Thing / FieldEvent /
FieldActivity / Sample / Observation).

Mirrors the convention of ``db/nma_legacy.py`` and ``db/nmw_legacy.py``:
``CM_`` table prefix, one table per source sheet, no enforced foreign keys
between mirror tables, no interpretation of values.

SOURCE SHEETS
-------------
    ChemicalData    -> CM_ChemicalData (source_sheet='ChemicalData')
    GIS             -> CM_ChemicalData (source_sheet='GIS')
    QAQC            -> CM_ChemicalData (source_sheet='QAQC')
    DetectionLimits -> CM_DetectionLimits
    References      -> CM_References
    MineralSystems  -> CM_MineralSystems
    world           -> CM_WorldComparisons
    world_ref       -> CM_WorldReferences
    General Information / MetaData / DefinitionOfFields -> CM_WorkbookMetadata

THREE SHEETS, ONE TABLE
-----------------------
``ChemicalData``, ``GIS`` and ``QAQC`` are mirrored into a single table keyed by
a ``source_sheet`` discriminator because they carry the SAME columns:
``ChemicalData`` and ``GIS`` are byte-identical in header text and order (118
columns each); ``QAQC`` is those columns minus ``MapSymbol``/``Pd``/``Pt``, with
``latitude``/``longitude`` capitalized. Only the layout differs -- ``GIS`` has a
single header row while ``ChemicalData`` has a title banner (row 1), a header
(row 2) and a units row (row 3).

RECONCILIATION IS DEFERRED (READ THIS BEFORE QUERYING)
------------------------------------------------------
``GIS`` is NOT ``ChemicalData`` plus location data, and it is not a clean
subset. It is a stale, hand-maintained fork. As of the 2025-09-17 revision,
every ``GIS`` sample name exists in ``ChemicalData``, but 1704 of the 4848
shared rows disagree cell-for-cell, in BOTH directions:

    GIS has values ChemicalData lacks:  533 Chem Lab File No., 485 Laboratory,
                                        85 FeO, 85 Fe2O3
    ChemicalData has values GIS lacks:  633 Total, 184 Area, 11 TREE,
                                        4 Date analyzed
    Outright disagreement:              16 rows on Area ('ZuniMountains'/'Zuni')
    Broken formulas:                    12 '#VALUE!' Totals in GIS (1 in CD)

``ChemicalData`` also holds 18 sample rows appended after ``GIS`` was last
synced (BP*, CR1, JP*, SA*, SL*). Neither sheet is authoritative, so BOTH are
mirrored in full and reconciliation is deliberately left to a later phase, to
be ruled on per column by V.T. McLemore. Do not treat any single
``source_sheet`` as complete, and do not de-duplicate across sheets here.

EVERY COLUMN IS A STRING
------------------------
Analyte columns hold censored values as text (``<0.1``, ``<10``, ``<0.06``),
Excel error text (``#VALUE!``), and blanks; date columns mix real dates with
free text. Parsing value-plus-qualifier and casting dates belongs to the
transform phase, cross-checked against ``CM_DetectionLimits``. Storing
everything as ``String`` keeps the mirror loadable without dropping cells.

COLUMN NAMING
-------------
Sheet headers are spreadsheet labels, not SQL identifiers ("Chem Lab File No.",
"Depth/legnth (ft)", "H2O+"), so unlike the NMA/NMW mirrors the source name
cannot be reused verbatim. Names here are derived mechanically:

* snake_case, lowercased, non-alphanumerics collapsed to ``_``;
* ``+`` -> ``_plus``, ``*`` -> ``_star``, ``%`` -> ``_pct``;
* analyte columns carry the unit the workbook declares for them in its units
  row (``sio2_pct``, ``au_ppb``, ``as_ppm``), which also keeps ``As`` and
  ``In`` from colliding with the Python/SQL keywords ``as`` and ``in``;
* the source typo in "Depth/legnth (ft)" is preserved as ``depth_legnth_ft`` so
  the mapping back to the sheet stays mechanical.

``SOURCE_HEADER_BY_COLUMN`` records the exact source header for every column, and
``ANALYTE_UNITS`` records the workbook-declared unit for every analyte, so the
units row is not lost.

ROW IDENTITY
------------
Sample names are NOT unique in the source (``S1``, ``S10``, ``S100`` and ~340
others repeat), so mirror rows are keyed on ``(source_sheet, source_row)``,
where ``source_row`` is the 1-based Excel row number. That makes every mirror
row traceable to a cell range in the delivered workbook, and makes a reload
idempotent per sheet.

KNOWN JUNK IN THE DATA RANGE
----------------------------
The first data row of ``ChemicalData`` is not a sample: its SAMPLE cell holds
"NOTE: SEE THE ORIGINAL CITATION FOR INFORMATION ON METHODS OF ANALYSES,
QA/QC, DETECTION LIMITS, ETC.". It is mirrored like any other row (fidelity)
and must be excluded by the transform.
"""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import mapped_column

from db.base import Base

# Source sheets mirrored into CM_ChemicalData.
CM_SHEET_CHEMICAL_DATA = "ChemicalData"
CM_SHEET_GIS = "GIS"
CM_SHEET_QAQC = "QAQC"
CM_CHEMISTRY_SOURCE_SHEETS = (
    CM_SHEET_CHEMICAL_DATA,
    CM_SHEET_GIS,
    CM_SHEET_QAQC,
)

# Columns absent from the QAQC sheet; always NULL for source_sheet='QAQC'.
QAQC_MISSING_COLUMNS = ("map_symbol", "pd_ppm", "pt_ppm")


# Unit the workbook's units row (ChemicalData row 3) declares for each analyte
# column. Recorded here because the units row is schema-level, not row-level.
ANALYTE_UNITS: dict[str, str] = {
    "sio2_pct": "%",
    "tio2_pct": "%",
    "al2o3_pct": "%",
    "fe2o3t_pct": "%",
    "mno_pct": "%",
    "mgo_pct": "%",
    "cao_pct": "%",
    "na2o_pct": "%",
    "k2o_pct": "%",
    "p2o5_pct": "%",
    "loi_pct": "%",
    "f_pct": "%",
    "s_pct": "%",
    "so3_pct": "%",
    "so4_pct": "%",
    "c_pct": "%",
    "co2_pct": "%",
    "total_pct": "%",
    "feo_pct": "%",
    "fe2o3_pct": "%",
    "feo_star_pct": "%",
    "h2o_plus_pct": "%",
    "h2o_minus_pct": "%",
    "au_ppb": "ppb",
    "ag_ppm": "ppm",
    "as_ppm": "ppm",
    "b_ppm": "ppm",
    "ba_ppm": "ppm",
    "be_ppm": "ppm",
    "bi_ppm": "ppm",
    "br_ppm": "ppm",
    "cd_ppm": "ppm",
    "cl_ppm": "ppm",
    "co_ppm": "ppm",
    "cr_ppm": "ppm",
    "cs_ppm": "ppm",
    "cu_ppm": "ppm",
    "ga_ppm": "ppm",
    "ge_ppm": "ppm",
    "hf_ppm": "ppm",
    "hg_ppm": "ppm",
    "in_ppm": "ppm",
    "li_ppm": "ppm",
    "mo_ppm": "ppm",
    "nb_ppm": "ppm",
    "ni_ppm": "ppm",
    "pd_ppm": "ppm",
    "pb_ppm": "ppm",
    "pt_ppm": "ppm",
    "rb_ppm": "ppm",
    "re_ppm": "ppm",
    "sb_ppm": "ppm",
    "sc_ppm": "ppm",
    "se_ppm": "ppm",
    "sn_ppm": "ppm",
    "sr_ppm": "ppm",
    "ta_ppm": "ppm",
    "te_ppm": "ppm",
    "th_ppm": "ppm",
    "tl_ppm": "ppm",
    "u_ppm": "ppm",
    "v_ppm": "ppm",
    "w_ppm": "ppm",
    "y_ppm": "ppm",
    "zn_ppm": "ppm",
    "zr_ppm": "ppm",
    "la_ppm": "ppm",
    "ce_ppm": "ppm",
    "pr_ppm": "ppm",
    "nd_ppm": "ppm",
    "sm_ppm": "ppm",
    "eu_ppm": "ppm",
    "gd_ppm": "ppm",
    "tb_ppm": "ppm",
    "dy_ppm": "ppm",
    "ho_ppm": "ppm",
    "er_ppm": "ppm",
    "tm_ppm": "ppm",
    "yb_ppm": "ppm",
    "lu_ppm": "ppm",
    "tree_ppm": "ppm",
    "mn_pct": "%",
    "fe_pct": "%",
    "al_pct": "%",
    "ca_pct": "%",
    "na_pct": "%",
    "k_pct": "%",
    "mg_pct": "%",
    "p_pct": "%",
    "si_pct": "%",
    "ti_pct": "%",
}


# Exact source header for every mirrored column, per table. The mirror column
# names are derived (see COLUMN NAMING above); this is the round trip back to
# the delivered workbook.
SOURCE_HEADER_BY_COLUMN: dict[str, dict[str, str]] = {
    "CM_ChemicalData": {
        "sample": "SAMPLE",
        "project": "Project",
        "area": "Area",
        "reference": "Reference",
        "date_collected": "Date collected",
        "date_analyzed": "Date analyzed",
        "chem_lab_file_no": "Chem Lab File No.",
        "laboratory": "Laboratory",
        "latitude": "latitude",
        "longitude": "longitude",
        "coordinate_system": "Coordinate system",
        "county": "County",
        "state": "State",
        "lithology": "lithology",
        "mineral_system": "Mineral system",
        "deposit_types": "Deposit type(s) (from Mineral Systems table)",
        "map_symbol": "MapSymbol",
        "method_collected": "method collected",
        "sample_source": "sample source",
        "mineralogy_deposit_type": "MineralogyDepositType",
        "depth_legnth_ft": "Depth/legnth (ft)",
        "mine_id": "Mine ID",
        "location_notes": "LocationNotes",
        "comments": "Comments",
        "paste_ph": "paste pH",
        "paste_conductivity": "paste conductivity",
        "tds_mg_l": "TDS (mg/l)",
        "sio2_pct": "SiO2",
        "tio2_pct": "TiO2",
        "al2o3_pct": "Al2O3",
        "fe2o3t_pct": "Fe2O3T",
        "mno_pct": "MnO",
        "mgo_pct": "MgO",
        "cao_pct": "CaO",
        "na2o_pct": "Na2O",
        "k2o_pct": "K2O",
        "p2o5_pct": "P2O5",
        "loi_pct": "LOI",
        "f_pct": "F",
        "s_pct": "S",
        "so3_pct": "SO3",
        "so4_pct": "SO4",
        "c_pct": "C",
        "co2_pct": "CO2",
        "total_pct": "Total",
        "feo_pct": "FeO",
        "fe2o3_pct": "Fe2O3",
        "feo_star_pct": "FeO*",
        "h2o_plus_pct": "H2O+",
        "h2o_minus_pct": "H2O-",
        "au_ppb": "Au",
        "ag_ppm": "Ag",
        "as_ppm": "As",
        "b_ppm": "B",
        "ba_ppm": "Ba",
        "be_ppm": "Be",
        "bi_ppm": "Bi",
        "br_ppm": "Br",
        "cd_ppm": "Cd",
        "cl_ppm": "Cl",
        "co_ppm": "Co",
        "cr_ppm": "Cr",
        "cs_ppm": "Cs",
        "cu_ppm": "Cu",
        "ga_ppm": "Ga",
        "ge_ppm": "Ge",
        "hf_ppm": "Hf",
        "hg_ppm": "Hg",
        "in_ppm": "In",
        "li_ppm": "Li",
        "mo_ppm": "Mo",
        "nb_ppm": "Nb",
        "ni_ppm": "Ni",
        "pd_ppm": "Pd",
        "pb_ppm": "Pb",
        "pt_ppm": "Pt",
        "rb_ppm": "Rb",
        "re_ppm": "Re",
        "sb_ppm": "Sb",
        "sc_ppm": "Sc",
        "se_ppm": "Se",
        "sn_ppm": "Sn",
        "sr_ppm": "Sr",
        "ta_ppm": "Ta",
        "te_ppm": "Te",
        "th_ppm": "Th",
        "tl_ppm": "Tl",
        "u_ppm": "U",
        "v_ppm": "V",
        "w_ppm": "W",
        "y_ppm": "Y",
        "zn_ppm": "Zn",
        "zr_ppm": "Zr",
        "la_ppm": "La",
        "ce_ppm": "Ce",
        "pr_ppm": "Pr",
        "nd_ppm": "Nd",
        "sm_ppm": "Sm",
        "eu_ppm": "Eu",
        "gd_ppm": "Gd",
        "tb_ppm": "Tb",
        "dy_ppm": "Dy",
        "ho_ppm": "Ho",
        "er_ppm": "Er",
        "tm_ppm": "Tm",
        "yb_ppm": "Yb",
        "lu_ppm": "Lu",
        "tree_ppm": "TREE",
        "mn_pct": "Mn",
        "fe_pct": "Fe",
        "al_pct": "Al",
        "ca_pct": "Ca",
        "na_pct": "Na",
        "k_pct": "K",
        "mg_pct": "Mg",
        "p_pct": "P",
        "si_pct": "Si",
        "ti_pct": "Ti",
    },
    "CM_WorldComparisons": {
        "area": "area",
        "deposit": "deposit",
        "reference": "reference",
        "la": "La",
        "ce": "Ce",
        "pr": "Pr",
        "nd": "Nd",
        "sm": "Sm",
        "eu": "Eu",
        "gd": "Gd",
        "tb": "Tb",
        "dy": "Dy",
        "ho": "Ho",
        "er": "Er",
        "tm": "Tm",
        "yb": "Yb",
        "lu": "Lu",
        "tree": "TREE",
        "sc": "Sc",
        "y": "Y",
        "metric_tons": "metric tons",
        "grade_pct": "grade %",
        "total_ree": "total REE",
        "cutoff_grade_pct": "cutoff grade %",
        "la2o3": "La2O3",
        "ce2o3": "Ce2O3",
        "pr6o11": "Pr6O11",
        "nd2o3": "Nd2O3",
        "sm2o3": "Sm2O3",
        "eu2o3": "Eu2O3",
        "gd2o3": "Gd2O3",
        "tb4o7": "Tb4O7",
        "dy2o3": "Dy2O3",
        "ho2o3": "Ho2O3",
        "er2o3": "Er2O3",
        "tm2o3": "Tm2O3",
        "yb2o3": "Yb2O3",
        "lu2o3": "Lu2O3",
        "y2o3": "Y2O3",
    },
    "CM_DetectionLimits": {
        "method": "Method (block title, DetectionLimits row 1)",
        "element": "Element",
        "lower_reporting_limit": "Lower Reporting Limit",
        "unit": "Unit",
    },
    "CM_MineralSystems": {
        "system_name": "System Name",
        "synopsis": "Synopsis",
        "deposit_types": "Deposit types",
        "principal_commodities": "Principal commodities",
        "critical_minerals": "Critical minerals",
        "references": "References",
        "phase_2": "Phase 2",
        "phase_3": "Phase 3",
        "phase_4": "Phase 4",
    },
}


class CM_ChemicalData(Base):
    """Mirror of the ChemicalData, GIS and QAQC sheets.

    One row per source spreadsheet row, keyed on (source_sheet, source_row).
    See RECONCILIATION IS DEFERRED in the module docstring: the three sheets
    disagree and none of them is authoritative.
    """

    __tablename__ = "CM_ChemicalData"
    __table_args__ = (
        UniqueConstraint(
            "source_sheet", "source_row", name="uq_cm_chemical_data_source_row"
        ),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Provenance of the cell range this row came from.
    source_sheet = mapped_column(String, nullable=False, index=True)
    source_row = mapped_column(Integer, nullable=False)

    # SAMPLE block: sample identity, location and field context.
    sample = mapped_column(String, index=True)  # SAMPLE
    project = mapped_column(String)  # Project
    area = mapped_column(String, index=True)  # Area
    reference = mapped_column(String)  # Reference
    date_collected = mapped_column(String)  # Date collected
    date_analyzed = mapped_column(String)  # Date analyzed
    chem_lab_file_no = mapped_column(String)  # Chem Lab File No.
    laboratory = mapped_column(String)  # Laboratory
    latitude = mapped_column(String)
    longitude = mapped_column(String)
    coordinate_system = mapped_column(String)  # Coordinate system
    county = mapped_column(String)  # County
    state = mapped_column(String)  # State
    lithology = mapped_column(String)
    mineral_system = mapped_column(String)  # Mineral system
    deposit_types = mapped_column(
        String
    )  # Deposit type(s) (from Mineral Systems table)
    map_symbol = mapped_column(String)  # MapSymbol
    method_collected = mapped_column(String)  # method collected
    sample_source = mapped_column(String)  # sample source
    mineralogy_deposit_type = mapped_column(String)  # MineralogyDepositType
    depth_legnth_ft = mapped_column(String)  # Depth/legnth (ft)
    mine_id = mapped_column(String)  # Mine ID
    location_notes = mapped_column(String)  # LocationNotes
    comments = mapped_column(String)  # Comments
    paste_ph = mapped_column(String)  # paste pH
    paste_conductivity = mapped_column(String)  # paste conductivity
    tds_mg_l = mapped_column(String)  # TDS (mg/l)

    # Major-element oxides and volatiles, as declared in the units row (%)
    sio2_pct = mapped_column(String)  # SiO2
    tio2_pct = mapped_column(String)  # TiO2
    al2o3_pct = mapped_column(String)  # Al2O3
    fe2o3t_pct = mapped_column(String)  # Fe2O3T
    mno_pct = mapped_column(String)  # MnO
    mgo_pct = mapped_column(String)  # MgO
    cao_pct = mapped_column(String)  # CaO
    na2o_pct = mapped_column(String)  # Na2O
    k2o_pct = mapped_column(String)  # K2O
    p2o5_pct = mapped_column(String)  # P2O5
    loi_pct = mapped_column(String)  # LOI
    f_pct = mapped_column(String)  # F
    s_pct = mapped_column(String)  # S
    so3_pct = mapped_column(String)  # SO3
    so4_pct = mapped_column(String)  # SO4
    c_pct = mapped_column(String)  # C
    co2_pct = mapped_column(String)  # CO2
    total_pct = mapped_column(String)  # Total
    feo_pct = mapped_column(String)  # FeO
    fe2o3_pct = mapped_column(String)  # Fe2O3
    feo_star_pct = mapped_column(String)  # FeO*
    h2o_plus_pct = mapped_column(String)  # H2O+
    h2o_minus_pct = mapped_column(String)  # H2O-

    # Precious metals and trace elements (Au in ppb, the rest ppm)
    au_ppb = mapped_column(String)  # Au
    ag_ppm = mapped_column(String)  # Ag
    as_ppm = mapped_column(String)  # As
    b_ppm = mapped_column(String)  # B
    ba_ppm = mapped_column(String)  # Ba
    be_ppm = mapped_column(String)  # Be
    bi_ppm = mapped_column(String)  # Bi
    br_ppm = mapped_column(String)  # Br
    cd_ppm = mapped_column(String)  # Cd
    cl_ppm = mapped_column(String)  # Cl
    co_ppm = mapped_column(String)  # Co
    cr_ppm = mapped_column(String)  # Cr
    cs_ppm = mapped_column(String)  # Cs
    cu_ppm = mapped_column(String)  # Cu
    ga_ppm = mapped_column(String)  # Ga
    ge_ppm = mapped_column(String)  # Ge
    hf_ppm = mapped_column(String)  # Hf
    hg_ppm = mapped_column(String)  # Hg
    in_ppm = mapped_column(String)  # In
    li_ppm = mapped_column(String)  # Li
    mo_ppm = mapped_column(String)  # Mo
    nb_ppm = mapped_column(String)  # Nb
    ni_ppm = mapped_column(String)  # Ni
    pd_ppm = mapped_column(String)  # Pd
    pb_ppm = mapped_column(String)  # Pb
    pt_ppm = mapped_column(String)  # Pt
    rb_ppm = mapped_column(String)  # Rb
    re_ppm = mapped_column(String)  # Re
    sb_ppm = mapped_column(String)  # Sb
    sc_ppm = mapped_column(String)  # Sc
    se_ppm = mapped_column(String)  # Se
    sn_ppm = mapped_column(String)  # Sn
    sr_ppm = mapped_column(String)  # Sr
    ta_ppm = mapped_column(String)  # Ta
    te_ppm = mapped_column(String)  # Te
    th_ppm = mapped_column(String)  # Th
    tl_ppm = mapped_column(String)  # Tl
    u_ppm = mapped_column(String)  # U
    v_ppm = mapped_column(String)  # V
    w_ppm = mapped_column(String)  # W
    y_ppm = mapped_column(String)  # Y
    zn_ppm = mapped_column(String)  # Zn
    zr_ppm = mapped_column(String)  # Zr

    # Rare earth elements and total REE (ppm)
    la_ppm = mapped_column(String)  # La
    ce_ppm = mapped_column(String)  # Ce
    pr_ppm = mapped_column(String)  # Pr
    nd_ppm = mapped_column(String)  # Nd
    sm_ppm = mapped_column(String)  # Sm
    eu_ppm = mapped_column(String)  # Eu
    gd_ppm = mapped_column(String)  # Gd
    tb_ppm = mapped_column(String)  # Tb
    dy_ppm = mapped_column(String)  # Dy
    ho_ppm = mapped_column(String)  # Ho
    er_ppm = mapped_column(String)  # Er
    tm_ppm = mapped_column(String)  # Tm
    yb_ppm = mapped_column(String)  # Yb
    lu_ppm = mapped_column(String)  # Lu
    tree_ppm = mapped_column(String)  # TREE

    # Whole-rock elemental analyses (%), reported alongside the oxides
    mn_pct = mapped_column(String)  # Mn
    fe_pct = mapped_column(String)  # Fe
    al_pct = mapped_column(String)  # Al
    ca_pct = mapped_column(String)  # Ca
    na_pct = mapped_column(String)  # Na
    k_pct = mapped_column(String)  # K
    mg_pct = mapped_column(String)  # Mg
    p_pct = mapped_column(String)  # P
    si_pct = mapped_column(String)  # Si
    ti_pct = mapped_column(String)  # Ti


class CM_DetectionLimits(Base):
    """Mirror of the DetectionLimits sheet (lower reporting limits by element).

    The sheet is a single block whose title row names the analytical method
    ("Method C_ICPOES_MS-61"); that title is carried on every row as ``method``
    so the block structure survives without a separate header table.
    """

    __tablename__ = "CM_DetectionLimits"
    __table_args__ = (
        UniqueConstraint("source_row", name="uq_cm_detection_limits_source_row"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_row = mapped_column(Integer, nullable=False)
    method = mapped_column(String)
    element = mapped_column(String, index=True)
    lower_reporting_limit = mapped_column(String)
    unit = mapped_column(String)


class CM_References(Base):
    """Mirror of the References sheet: one full citation per row, no header.

    ``CM_ChemicalData.reference`` holds the short form ("McLemore et al.
    (2025b)") that keys into these citations, but the sheet provides no
    explicit key column, so the join is left to the transform phase.
    """

    __tablename__ = "CM_References"
    __table_args__ = (
        UniqueConstraint("source_row", name="uq_cm_references_source_row"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_row = mapped_column(Integer, nullable=False)
    citation = mapped_column(String)


class CM_MineralSystems(Base):
    """Mirror of the MineralSystems sheet (Hofstra and Kreiner, 2020).

    The sheet is irregular: columns 1-6 are the systems table proper, while
    columns 7-9 hold three independent lists of critical minerals by USGS
    phase, and several rows are table notes rather than systems. Cells are
    mirrored positionally, notes included; sorting that out is transform work.
    """

    __tablename__ = "CM_MineralSystems"
    __table_args__ = (
        UniqueConstraint("source_row", name="uq_cm_mineral_systems_source_row"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_row = mapped_column(Integer, nullable=False)
    system_name = mapped_column(String)
    synopsis = mapped_column(String)
    deposit_types = mapped_column(String)
    principal_commodities = mapped_column(String)
    critical_minerals = mapped_column(String)
    references = mapped_column(String)
    phase_2 = mapped_column(String)
    phase_3 = mapped_column(String)
    phase_4 = mapped_column(String)


class CM_WorldComparisons(Base):
    """Mirror of the world sheet: world-class REE deposits used as comparanda.

    Not New Mexico data and not sample data -- published averages for other
    deposits plus crustal abundance, carried for context. Citations are in
    CM_WorldReferences. The sheet declares no units row.
    """

    __tablename__ = "CM_WorldComparisons"
    __table_args__ = (
        UniqueConstraint("source_row", name="uq_cm_world_comparisons_source_row"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_row = mapped_column(Integer, nullable=False)

    area = mapped_column(String)
    deposit = mapped_column(String)
    reference = mapped_column(String)
    la = mapped_column(String)  # La
    ce = mapped_column(String)  # Ce
    pr = mapped_column(String)  # Pr
    nd = mapped_column(String)  # Nd
    sm = mapped_column(String)  # Sm
    eu = mapped_column(String)  # Eu
    gd = mapped_column(String)  # Gd
    tb = mapped_column(String)  # Tb
    dy = mapped_column(String)  # Dy
    ho = mapped_column(String)  # Ho
    er = mapped_column(String)  # Er
    tm = mapped_column(String)  # Tm
    yb = mapped_column(String)  # Yb
    lu = mapped_column(String)  # Lu
    tree = mapped_column(String)  # TREE
    sc = mapped_column(String)  # Sc
    y = mapped_column(String)  # Y
    metric_tons = mapped_column(String)  # metric tons
    grade_pct = mapped_column(String)  # grade %
    total_ree = mapped_column(String)  # total REE
    cutoff_grade_pct = mapped_column(String)  # cutoff grade %
    la2o3 = mapped_column(String)  # La2O3
    ce2o3 = mapped_column(String)  # Ce2O3
    pr6o11 = mapped_column(String)  # Pr6O11
    nd2o3 = mapped_column(String)  # Nd2O3
    sm2o3 = mapped_column(String)  # Sm2O3
    eu2o3 = mapped_column(String)  # Eu2O3
    gd2o3 = mapped_column(String)  # Gd2O3
    tb4o7 = mapped_column(String)  # Tb4O7
    dy2o3 = mapped_column(String)  # Dy2O3
    ho2o3 = mapped_column(String)  # Ho2O3
    er2o3 = mapped_column(String)  # Er2O3
    tm2o3 = mapped_column(String)  # Tm2O3
    yb2o3 = mapped_column(String)  # Yb2O3
    lu2o3 = mapped_column(String)  # Lu2O3
    y2o3 = mapped_column(String)  # Y2O3


class CM_WorldReferences(Base):
    """Mirror of the world_ref sheet: citations for CM_WorldComparisons."""

    __tablename__ = "CM_WorldReferences"
    __table_args__ = (
        UniqueConstraint("source_row", name="uq_cm_world_references_source_row"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_row = mapped_column(Integer, nullable=False)
    citation = mapped_column(String)


class CM_WorkbookMetadata(Base):
    """Mirror of the workbook's label/value provenance sheets.

    Flattens "General Information", "MetaData" and "DefinitionOfFields" into
    (source_sheet, label, value) triples: title, abstract, compilers, original
    and revised dates, online resources, and the sheet's own definitions of the
    SAMPLE-block fields. Kept so the mirror carries its own provenance rather
    than relying on the workbook file staying around.
    """

    __tablename__ = "CM_WorkbookMetadata"
    __table_args__ = (
        UniqueConstraint(
            "source_sheet", "source_row", name="uq_cm_workbook_metadata_source_row"
        ),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_sheet = mapped_column(String, nullable=False)
    source_row = mapped_column(Integer, nullable=False)
    label = mapped_column(String)
    value = mapped_column(String)
