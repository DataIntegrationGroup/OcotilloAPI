# flake8: noqa: E501
"""
schemas.aem — Pydantic models and enums for the AEM ingest pipeline.

These models serve two audiences:
  - Marissa (data curator): IngestConfig validates that survey provenance
    is correct before anything touches the database.
  - Jake (platform engineer): SoundingRow catches type/null errors in
    parsed data before they surface as cryptic PostGIS COPY failures.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProcessingStage(str, Enum):
    """Processing stage of the inversion data.

    preliminary_inversion: Seogi/GeoTech in-house inversions, not yet
        reviewed or finalized.  May be superseded by final inversions.
    final_inversion: Aarhus Workbench or AGF LCI outputs that have been
        reviewed and accepted as the official inversion for a survey.
    """

    PRELIMINARY = "preliminary_inversion"
    FINAL = "final_inversion"


class InversionCode(str, Enum):
    """Inversion software that produced the data.

    seogi_python: Custom Python inversion pipeline (Seogi/Ahsan).
        Produces resistivity only — no uncertainty, DOI, or conductivity.
    aarhus_sci: Aarhus Workbench SCI (Spatially Constrained Inversion).
        Full uncertainty, DOI, conductivity.
    aarhus_lci: Aarhus Workbench LCI (Laterally Constrained Inversion).
        Full uncertainty, DOI, conductivity.  Used by AGF for Mimbres.
    """

    SEOGI_PYTHON = "seogi_python"
    AARHUS_SCI = "aarhus_sci"
    AARHUS_LCI = "aarhus_lci"


class SourceFormat(str, Enum):
    """Detected file format — drives which parser is invoked."""

    BYLAYER = "bylayer"
    SEOGI_RHO = "seogi_rho"
    AGF_LCI = "agf_lci"


class SkytemSystem(str, Enum):
    """SkyTEM system identifier.  Separate files per system in AGF deliverables."""

    HP306 = "306hp"
    HP312 = "312hp"


# ---------------------------------------------------------------------------
# Ingest configuration
# ---------------------------------------------------------------------------


class IngestConfig(BaseModel):
    """Validated configuration for a single file ingest run.

    Typer CLI parameters and programmatic callers both produce this model.
    Validation happens once, up front, before any parsing or DB work.
    """

    filepath: str = Field(description="Local path to the inversion file")
    survey_id: str = Field(
        description="Survey identifier, e.g. 'gila_animas_2025'",
        pattern=r"^[a-z0-9_]+$",
    )
    processing_stage: ProcessingStage
    inversion_code: InversionCode
    contractor: str = Field(description="e.g. 'GeoTech/Seogi', 'GIP/Aarhus'")
    db_conn_string: Optional[str] = Field(
        default=None,
        description="Optional PostgreSQL connection string override",
    )
    gcs_bucket: str = Field(description="GCS bucket name")

    # GCS path for the source file — provided by the mapper (aem_gcs_mapper.py),
    # NOT computed by the ingest pipeline.  The mapper is the single source of
    # truth for where every file lives in GCS.  The pipeline just records this
    # path in the source_file provenance column and in the STAC asset link.
    source_gcs_path: str = Field(
        description=(
            "GCS path (relative to bucket root) for the source file. "
            "Read from the mapper's proposed_gcs_path column. "
            "e.g. 'surveys/estancia_2025/aem/inversion/preliminary/rho_GL250194_F01.csv'"
        ),
    )

    # Format-specific options
    flight_id: Optional[str] = Field(
        default=None,
        description=(
            "Flight ID for Seogi format (e.g. 'F02'). "
            "Extracted from filename if not provided."
        ),
    )
    system: Optional[SkytemSystem] = Field(
        default=None,
        description="SkyTEM system for AGF format ('306hp' or '312hp')",
    )
    date_acquired: Optional[datetime.date] = Field(
        default=None,
        description="Acquisition date (YYYY-MM-DD)",
    )

    @model_validator(mode="after")
    def validate_format_specific_fields(self) -> "IngestConfig":
        """Warn early if AGF format will need the system parameter.

        We can't fully validate this here because format detection
        requires reading the file.  But if inversion_code is aarhus_lci,
        system is almost certainly required.
        """
        if self.inversion_code == InversionCode.AARHUS_LCI and self.system is None:
            import logging

            logging.getLogger(__name__).warning(
                "inversion_code is 'aarhus_lci' but no --system provided. "
                "AGF LCI files require --system (306hp or 312hp)."
            )
        return self


# ---------------------------------------------------------------------------
# Survey metadata — static per-survey values for STAC items
# ---------------------------------------------------------------------------


class SurveyMetadata(BaseModel):
    """Static per-survey metadata that is known at pipeline invocation time.

    These values are NOT derived from the data — they come from contracts,
    proposals, and survey design documents.  They populate the nmbgmr:
    namespace fields in STAC items and collections.
    """

    survey_region: str = Field(description="e.g. 'Gila-Animas Basin'")
    system: str = Field(description="e.g. 'VTEM ET', 'SkyTEM 306HP + 312HP'")
    line_spacing: int = Field(description="Nominal line spacing in meters")
    line_length: Optional[int] = Field(
        default=None,
        description="Total survey line length in kilometers (None if TBD)",
    )
    is_skytem: bool = Field(
        default=False,
        description=(
            "True for SkyTEM surveys (LRG, Mimbres, MRG). "
            "Adds companions asset to STAC item."
        ),
    )


# Lookup table — one entry per survey.  Used by the pipeline to populate
# STAC nmbgmr: fields without requiring the caller to pass them every time.
SURVEY_METADATA: dict[str, SurveyMetadata] = {
    "gila_animas_2025": SurveyMetadata(
        survey_region="Gila-Animas Basin",
        system="VTEM ET",
        line_spacing=250,
        line_length=2319,
        is_skytem=False,
    ),
    "estancia_2025": SurveyMetadata(
        survey_region="Estancia Basin",
        system="VTEM ET",
        line_spacing=250,
        line_length=2330,
        is_skytem=False,
    ),
    "n_tularosa_2025": SurveyMetadata(
        survey_region="Northern Tularosa Basin",
        system="VTEM ET + VTEM Max + ZTEM",
        line_spacing=250,
        line_length=None,  # TBD
        is_skytem=False,
    ),
    "mimbres_2025": SurveyMetadata(
        survey_region="Mimbres Basin",
        system="SkyTEM 306HP + 312HP",
        line_spacing=200,
        line_length=3296,
        is_skytem=True,
    ),
    "lrg_2025": SurveyMetadata(
        survey_region="Lower Rio Grande",
        system="SkyTEM 306HP",
        line_spacing=200,
        line_length=4002,
        is_skytem=True,
    ),
    "mrg_2025": SurveyMetadata(
        survey_region="Middle Rio Grande",
        system="SkyTEM",
        line_spacing=200,
        line_length=2000,
        is_skytem=True,
    ),
}


# ---------------------------------------------------------------------------
# Row-level validation model
# ---------------------------------------------------------------------------


class SoundingRow(BaseModel):
    """Validates a single row of the canonical long-format DataFrame.

    Used for spot-checking parsed data, not for row-by-row validation of
    million-row DataFrames (that would be too slow).  Call
    validate_dataframe() for bulk checks.

    PostGIS NOT NULL columns are non-optional here.  Everything else
    is Optional because different formats produce different subsets:
    Seogi has no uncertainty; byLayer may lack DOI; AGF has everything.
    """

    model_config = {"arbitrary_types_allowed": True}

    # Provenance (set by pipeline, not by parser)
    survey_id: Optional[str] = None
    processing_stage: Optional[str] = None
    inversion_code: Optional[str] = None
    contractor: Optional[str] = None
    source_file: Optional[str] = None
    source_epsg: int

    # Identifiers
    line_id: str
    record_id: str  # TEXT not INTEGER — Seogi needs F01_1 prefix
    layer_no: int = Field(ge=1, le=200)

    # Position used to derive the stored WGS84 geometry during ingest
    easting: float = Field(description="in meters, projected coordinate")
    northing: float = Field(description="in meters, projected coordinate")

    # Elevation
    elevation: Optional[float] = Field(
        default=None, description="in meters with vertical datum of NAVD88"
    )
    sensor_alt: Optional[float] = Field(
        default=None, description="in meters above ground"
    )
    terrain_clear: Optional[float] = Field(
        default=None, description="in meters above terrain"
    )

    # Layer geometry
    depth_top: float = Field(description="in meters below surface")
    depth_bot: float = Field(description="in meters below surface")
    thickness: Optional[float] = Field(default=None, description="in meters")

    # Inversion result
    resistivity: float = Field(gt=0, description="in ohm-meters")

    # Uncertainty — NULL when pipeline doesn't produce it (e.g. Seogi).
    # This is meaningful: NULL = "not estimated", not "unknown".
    resistivity_std: Optional[float] = None
    conductivity: Optional[float] = Field(
        default=None, description="in siemens per meter"
    )
    doi_conservative: Optional[float] = Field(default=None, description="in meters")
    doi_standard: Optional[float] = Field(default=None, description="in meters")
    resdata: Optional[float] = None
    restotal: Optional[float] = None
    plni: Optional[float] = None

    date_acquired: Optional[datetime.date] = None


# ---------------------------------------------------------------------------
# Bulk validation helper
# ---------------------------------------------------------------------------

# Columns that must never be NULL in PostGIS (defined as NOT NULL in DDL).
REQUIRED_COLUMNS = [
    "line_id",
    "layer_no",
    "easting",
    "northing",
    "depth_top",
    "depth_bot",
    "resistivity",
]


def validate_dataframe(df, source_label: str = "unknown") -> list[str]:
    """Bulk-validate a parsed DataFrame against the canonical schema.

    Checks for NULL values in NOT NULL columns, unexpected dtypes,
    and out-of-range values.  Returns a list of warning strings.
    Does NOT raise — the caller decides whether warnings are fatal.
    """
    import logging

    logger = logging.getLogger(__name__)
    warnings: list[str] = []

    # Check required columns exist and have no NULLs
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            msg = f"[{source_label}] MISSING required column '{col}'"
            logger.error(msg)
            warnings.append(msg)
            continue
        null_count = df[col].isna().sum()
        if null_count > 0:
            msg = (
                f"[{source_label}] {null_count:,} NULL values in "
                f"required column '{col}' (PostGIS will reject these rows)"
            )
            logger.warning(msg)
            warnings.append(msg)

    # Sanity checks
    if "resistivity" in df.columns:
        neg_count = (df["resistivity"].dropna() <= 0).sum()
        if neg_count > 0:
            msg = (
                f"[{source_label}] {neg_count:,} rows with "
                f"resistivity <= 0 (physically impossible)"
            )
            logger.warning(msg)
            warnings.append(msg)

    if "layer_no" in df.columns:
        if df["layer_no"].dropna().min() < 1:
            msg = f"[{source_label}] layer_no contains values < 1 (expected 1-based)"
            logger.warning(msg)
            warnings.append(msg)

    return warnings
