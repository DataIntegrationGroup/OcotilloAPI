# flake8: noqa: E501
"""
services.aem_parsers.common — Shared constants and coordinate helpers.

Used by all three parsers.  Keeps coordinate math in one place so
the CRS logic doesn't get duplicated (or subtly diverge).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from schemas.aem import validate_dataframe, validate_dataframe_sample
from services.util import reproject_to_target

# All surveys are delivered in UTM Zone 13N. GIP/SkyTEM and AGF deliver
# NAD83 (EPSG:26913). GeoTech/Seogi delivers WGS84 UTM 13N (EPSG:32613).
# The ~1 m datum shift still matters, so we normalize projected coordinates
# to 26913 in-memory before deriving the stored WGS84 geometry.
TARGET_EPSG = 26913

TEMPORAL_DATETIME_ALIASES = {
    "acquisition_datetime": [
        "acquisition_datetime",
        "datetime_acquired",
        "acquired_at",
        "timestamp",
        "datetime_utc",
        "utc_datetime",
        "datetime",
        "date_time",
        "date_time_utc",
        "acq_datetime",
        "acq_date_time",
        "flight_datetime",
        "flight_date_time",
    ]
}
TEMPORAL_DATE_ALIASES = {
    "date_acquired": [
        "date_acquired",
        "acquisition_date",
        "acq_date",
        "flight_date",
        "date",
    ]
}
TEMPORAL_TIME_ALIASES = {
    "acquisition_time": [
        "acquisition_time",
        "time_acquired",
        "time_utc",
        "utc_time",
        "time",
        "gtime",
        "g_time",
        "gps_time",
        "acq_time",
        "flight_time",
    ]
}

TEMPORAL_DATETIME_COLUMNS = [
    "acquisition_datetime",
    "datetime_acquired",
    "acquired_at",
    "timestamp",
    "datetime_utc",
    "utc_datetime",
]
TEMPORAL_TIME_COLUMNS = [
    "acquisition_time",
    "time_acquired",
    "time_utc",
    "utc_time",
]

# Canonical column names for the parser/Parquet contract.
# The database only persists the non-coordinate fields plus a WGS84 geometry.
CANONICAL_COLUMNS = [
    "survey_id",
    "processing_stage",
    "inversion_code",
    "contractor",
    "source_file",
    "source_epsg",
    "line_id",
    "record_id",
    "layer_no",
    "easting",
    "northing",
    "elevation",
    "sensor_alt",
    "terrain_clear",
    "depth_top",
    "depth_bot",
    "thickness",
    "resistivity",
    "resistivity_std",
    "conductivity",
    "doi_conservative",
    "doi_standard",
    "resdata",
    "restotal",
    "plni",
    "date_acquired",
]


def ensure_canonical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add any missing canonical columns as NaN/None.

    Different formats produce different subsets of the canonical schema.
    Seogi has no uncertainty; byLayer may lack DOI; AGF has everything.
    This ensures every canonical column exists so downstream code can
    safely reference any column without KeyError.
    """
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _resolve_temporal_aliases(
    df: pd.DataFrame, aliases: dict[str, list[str]]
) -> pd.DataFrame:
    lowered = {col.lower(): col for col in df.columns}
    for target, candidates in aliases.items():
        if target in df.columns:
            continue
        for candidate in candidates:
            source = lowered.get(candidate.lower())
            if source is not None:
                df[target] = df[source]
                break
    return df


def normalize_temporal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map common raw source timestamp/date/time headers into canonical names."""
    df = _resolve_temporal_aliases(df, TEMPORAL_DATETIME_ALIASES)
    df = _resolve_temporal_aliases(df, TEMPORAL_DATE_ALIASES)
    df = _resolve_temporal_aliases(df, TEMPORAL_TIME_ALIASES)
    return df


def copy_temporal_columns(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
) -> pd.DataFrame:
    """Preserve likely acquisition timestamp columns through parser reshaping."""
    candidate_columns = (
        TEMPORAL_DATETIME_COLUMNS
        + TEMPORAL_TIME_COLUMNS
        + [alias for aliases in TEMPORAL_DATETIME_ALIASES.values() for alias in aliases]
        + [alias for aliases in TEMPORAL_DATE_ALIASES.values() for alias in aliases]
        + [alias for aliases in TEMPORAL_TIME_ALIASES.values() for alias in aliases]
    )
    for col in candidate_columns:
        if col in source_df.columns and col not in target_df.columns:
            target_df[col] = source_df[col]
    return target_df


def finalize_parsed_dataframe(
    df: pd.DataFrame,
    source_label: str,
    source_epsg: int,
) -> pd.DataFrame:
    """Apply the shared post-parse normalization and smoke checks."""
    df = normalize_temporal_columns(df)
    df["line_id"] = df["line_id"].astype(str)
    df["layer_no"] = df["layer_no"].astype("Int16")
    df["source_epsg"] = source_epsg

    df = reproject_to_target(df, source_epsg, TARGET_EPSG)
    df["source_epsg"] = TARGET_EPSG
    df = ensure_canonical_columns(df)

    validate_dataframe(df, source_label)
    validate_dataframe_sample(df, source_label)
    return df
