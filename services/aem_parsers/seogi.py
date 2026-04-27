# flake8: noqa: E501
"""
services.aem_parsers.seogi — Parser for Seogi Python rho CSV files.

Key conventions:
  - Wide format: 40 layers per sounding, columns like
    top_1_layer_m, bottom_1_layer_m, rho_1_layer_m (through 40).
  - The 'record' column resets to 1 in each flight subfolder.
    Without prefixing, a cross-flight query returns duplicate record
    numbers from different flights — the dataset becomes non-relational.
    We prefix with flight_id (e.g. F02_1, F02_3) to make record_id
    globally unique within a survey.
  - Source CRS: EPSG:32613 (WGS84 UTM Zone 13N).
    This is ~1 m different from NAD83 (26913).  Reproject at ingest.
  - No uncertainty, DOI, or conductivity columns — Seogi's Python
    inversion pipeline does not produce these.  They are NULL in PostGIS.
    This is meaningful: it means the pipeline didn't estimate uncertainty,
    not that the value is unknown.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from services.aem_parsers.common import copy_temporal_columns, finalize_parsed_dataframe
from services.aem_parsers.detect import extract_flight_id

logger = logging.getLogger(__name__)


def parse_seogi_rho(
    filepath: str,
    flight_id: Optional[str] = None,
    source_epsg: int = 32613,
) -> pd.DataFrame:
    """Parse a Seogi Python rho CSV to canonical long-format schema.

    Args:
        filepath: Path to the rho CSV file.
        flight_id: Flight identifier (e.g. 'F02').  If None, extracted
                   from the filename.
        source_epsg: Source CRS for Seogi projected coordinates.

    Returns:
        DataFrame with canonical column names, ready for PostGIS load.
    """
    logger.info("Parsing Format B (Seogi rho): %s", filepath)

    if flight_id is None:
        flight_id = extract_flight_id(filepath)
    logger.info("Flight ID: %s", flight_id)

    df = pd.read_csv(filepath)
    logger.info("Seogi raw rows (soundings): %d", len(df))

    # Validate expected wide-format columns
    expected_cols = {"record", "line_no", "utmx", "utmy", "elevation"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Seogi rho CSV missing required columns: {missing}. "
            f"Found: {list(df.columns)[:20]}..."
        )

    # Check that we have layer columns
    layer_cols = [c for c in df.columns if c.startswith("rho_") and "layer_m" in c]
    n_layers = len(layer_cols)
    if n_layers == 0:
        raise ValueError(
            f"No rho_*_layer_m columns found in {filepath}. "
            f"Expected Seogi wide-format rho CSV."
        )
    logger.info("Seogi layers detected: %d", n_layers)

    # Prefix record with flight ID to create globally unique record_id.
    # record=1 in F02 becomes "F02_1".  This is why record_id is TEXT.
    df["record_id"] = flight_id + "_" + df["record"].astype(str)
    # Preserve within-line source order so companion acquisition CSVs can
    # stamp timestamps onto soundings before STAC generation.
    df["_source_point_order"] = df.groupby("line_no", sort=False).cumcount() + 1

    # ---- Pivot wide → long ----
    rows = []
    for layer_idx in range(1, n_layers + 1):
        top_col = f"top_{layer_idx}_layer_m"
        bot_col = f"bottom_{layer_idx}_layer_m"
        rho_col = f"rho_{layer_idx}_layer_m"

        for col in [top_col, bot_col, rho_col]:
            if col not in df.columns:
                raise ValueError(
                    f"Expected column '{col}' not found. "
                    f"Layer {layer_idx} is incomplete."
                )

        layer_df = df[
            ["record_id", "line_no", "utmx", "utmy", "elevation", "_source_point_order"]
        ].copy()
        layer_df = copy_temporal_columns(df, layer_df)

        # Include plm if present (some Seogi outputs include it)
        if "plm" in df.columns:
            layer_df["plm"] = df["plm"]

        layer_df["layer_no"] = layer_idx
        layer_df["depth_top"] = df[top_col]
        layer_df["depth_bot"] = df[bot_col]
        layer_df["resistivity"] = df[rho_col]
        rows.append(layer_df)

    long_df = pd.concat(rows, ignore_index=True)
    logger.info("Seogi pivoted to long: %d rows", len(long_df))

    # Rename to canonical schema
    long_df = long_df.rename(
        columns={
            "line_no": "line_id",
            "utmx": "easting",
            "utmy": "northing",
            "elevation": "elevation",
            "plm": "plni",
        }
    )

    long_df = finalize_parsed_dataframe(long_df, filepath, source_epsg=source_epsg)

    # Store flight_id for metadata table
    long_df["_flight_id"] = flight_id

    logger.info(
        "Seogi parsed: %d rows, %d unique soundings",
        len(long_df),
        long_df["record_id"].nunique(),
    )
    return long_df
