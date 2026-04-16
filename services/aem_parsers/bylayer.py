# flake8: noqa: E501
"""
services.aem_parsers.bylayer — Parser for Aarhus Workbench *_byLayer.xyz files.

Key conventions:
  - Space-delimited, header/comment lines start with '/'
  - Null value is '*' (asterisk) — SkyTEM/Aarhus convention, NOT NaN.
    If we don't pass na_values=['*'], pandas reads asterisks as strings
    and the entire resistivity column silently becomes object dtype.
  - Already in long format: one row per layer per sounding.
    No pivot needed — maps directly to PostGIS schema.
  - Source CRS: EPSG:26913 (NAD83 UTM Zone 13N) — no reprojection.
"""

from __future__ import annotations

import logging

import pandas as pd

from schemas.aem import validate_dataframe
from services.aem_parsers.common import add_latlon, ensure_canonical_columns

logger = logging.getLogger(__name__)


def parse_bylayer(filepath: str) -> pd.DataFrame:
    """Parse an Aarhus Workbench *_byLayer.xyz export to canonical schema.

    Returns:
        DataFrame with canonical column names, ready for PostGIS load.
    """
    logger.info("Parsing Format A (byLayer): %s", filepath)

    # Read the header to find column names.  Aarhus Workbench writes them
    # on a line starting with '/' followed by column names.
    col_names = None
    skip_rows = 0
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if line.startswith("/"):
                # Last header line before data has the column names.
                # Format: "/ UTMX  UTMY  ..." — strip the leading '/'
                candidate = line.lstrip("/").strip()
                if candidate:
                    col_names = candidate.split()
                skip_rows = i + 1
            else:
                break

    if col_names is None:
        raise ValueError(
            f"No header line starting with '/' found in {filepath}. "
            f"Expected Aarhus Workbench byLayer format."
        )

    logger.debug("byLayer columns detected: %s", col_names)

    df = pd.read_csv(
        filepath,
        sep=r"\s+",
        names=col_names,
        skiprows=skip_rows,
        na_values=["*"],  # Critical: SkyTEM null convention
        comment="/",
    )

    logger.info("byLayer raw rows: %d", len(df))

    # Validate expected source columns
    expected = {"ID", "LINE_NO", "LAYER_NO", "UTMX", "UTMY", "RESISTIVITY"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(
            f"byLayer file missing required columns: {missing}. "
            f"Found: {list(df.columns)}"
        )

    # Rename to canonical schema
    rename_map = {
        "LINE_NO": "line_id",
        "ID": "record_id",
        "LAYER_NO": "layer_no",
        "UTMX": "easting_m",
        "UTMY": "northing_m",
        "ELEVATION_CELL": "elevation_m",
        "DEPTH_TOP": "depth_top_m",
        "DEPTH_BOTTOM": "depth_bot_m",
        "THICKNESS": "thickness_m",
        "RESISTIVITY": "resistivity_ohmm",
        "RESISTIVITY_STD": "resistivity_std",
        "CONDUCTIVITY": "conductivity_sm",
        "DOI_CONSERVATIVE": "doi_conservative_m",
        "DOI_STANDARD": "doi_standard_m",
        "RESDATA": "resdata",
        "RESTOTAL": "restotal",
        "PLNI": "plni",
    }

    # Only rename columns that actually exist in the file
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # record_id must be TEXT (not integer) — it will carry flight prefixes
    # in Format B, and we keep the type consistent across all formats.
    df["record_id"] = df["record_id"].astype(str)
    df["line_id"] = df["line_id"].astype(str)
    df["layer_no"] = df["layer_no"].astype("Int16")

    df["source_epsg"] = 26913

    # Add lat/lon from UTM (no reprojection needed, same EPSG)
    df = add_latlon(df, source_epsg=26913)

    # Ensure all canonical columns exist (fill missing with NaN)
    df = ensure_canonical_columns(df)

    validate_dataframe(df, filepath)

    logger.info(
        "byLayer parsed: %d rows, %d unique soundings",
        len(df),
        df["record_id"].nunique(),
    )
    return df
