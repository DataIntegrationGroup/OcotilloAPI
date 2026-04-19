# flake8: noqa: E501
"""
services.aem_parsers.agf — Parser for AGF LCI CSV files.

Key conventions:
  - Wide format: 39 layers per sounding.  Columns use bracket indexing:
    RHO[0] through RHO[38], DEP_TOP_m[0] through DEP_TOP_m[38], etc.
  - Layer indices are 0-based in the source file.  We convert to 1-based
    for PostGIS consistency with Aarhus Workbench (which uses 1-based).
  - Full uncertainty available: RHO_STD (resistivity standard deviation),
    SIGMA (conductivity), DOI_UPPER_m and DOI_LOWER_m.
  - The Leapfrog borehole format would drop RHO_STD, SIGMA, and DOI
    columns — a concrete reason it was rejected as a standard.
  - Source CRS: EPSG:26913 — no reprojection needed.
  - Separate files per SkyTEM system (306HP, 312HP).  The system tag
    is stored in provenance for downstream filtering.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from schemas.aem import validate_dataframe, validate_dataframe_sample
from services.aem_parsers.common import ensure_canonical_columns, reproject_to_target

logger = logging.getLogger(__name__)


def parse_agf_lci(filepath: str, system: str) -> pd.DataFrame:
    """Parse an AGF LCI CSV to canonical long-format schema.

    Args:
        filepath: Path to the AGF LCI CSV file.
        system: SkyTEM system identifier, e.g. '306hp' or '312hp'.

    Returns:
        DataFrame with canonical column names, ready for PostGIS load.
    """
    logger.info("Parsing Format C (AGF LCI): %s  [system=%s]", filepath, system)

    df = pd.read_csv(filepath)
    logger.info("AGF raw rows (soundings): %d", len(df))

    # Validate expected columns
    expected = {"Line", "E_UTM13Nm", "N_UTM13Nm", "DEM_m", "RHO[0]"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(
            f"AGF LCI CSV missing required columns: {missing}. "
            f"Found: {list(df.columns)[:20]}..."
        )

    # Count layers from RHO[n] columns
    rho_cols = sorted(
        [c for c in df.columns if re.match(r"^RHO\[\d+\]$", c)],
        key=lambda c: int(re.search(r"\d+", c).group()),
    )
    n_layers = len(rho_cols)
    logger.info("AGF layers detected: %d", n_layers)

    # Assign record_id as row index (AGF files don't have a record column)
    df["record_id"] = df.index.astype(str)

    # ---- Pivot wide → long ----
    rows = []
    for src_idx in range(n_layers):
        # Source is 0-based; PostGIS layer_no is 1-based
        layer_no = src_idx + 1

        rho_col = f"RHO[{src_idx}]"
        dep_top_col = f"DEP_TOP_m[{src_idx}]"
        dep_bot_col = f"DEP_BOT_m[{src_idx}]"

        for col in [rho_col, dep_top_col, dep_bot_col]:
            if col not in df.columns:
                raise ValueError(f"Expected column '{col}' not found in AGF file.")

        layer_df = df[["record_id", "Line", "E_UTM13Nm", "N_UTM13Nm", "DEM_m"]].copy()

        # Sounding-level columns (constant across layers)
        if "ALTITUDE__m_" in df.columns:
            layer_df["sensor_alt"] = df["ALTITUDE__m_"]
        if "ALTITUDE_A_PRIORI__m_" in df.columns:
            layer_df["terrain_clear"] = df["ALTITUDE_A_PRIORI__m_"]
        if "RESDATA" in df.columns:
            layer_df["resdata"] = df["RESDATA"]
        if "RESTOTAL" in df.columns:
            layer_df["restotal"] = df["RESTOTAL"]
        if "DOI_UPPER_m" in df.columns:
            layer_df["doi_conservative"] = df["DOI_UPPER_m"]
        if "DOI_LOWER_m" in df.columns:
            layer_df["doi_standard"] = df["DOI_LOWER_m"]

        # Layer-level columns
        layer_df["layer_no"] = layer_no
        layer_df["depth_top"] = df[dep_top_col]
        layer_df["depth_bot"] = df[dep_bot_col]
        layer_df["resistivity"] = df[rho_col]

        # Optional layer-level uncertainty columns
        rho_std_col = f"RHO_STD[{src_idx}]"
        if rho_std_col in df.columns:
            layer_df["resistivity_std"] = df[rho_std_col]

        sigma_col = f"SIGMA[{src_idx}]"
        if sigma_col in df.columns:
            layer_df["conductivity"] = df[sigma_col]

        thk_col = f"THK_m[{src_idx}]"
        if thk_col in df.columns:
            layer_df["thickness"] = df[thk_col]

        rows.append(layer_df)

    long_df = pd.concat(rows, ignore_index=True)
    logger.info("AGF pivoted to long: %d rows", len(long_df))

    # Rename to canonical schema
    long_df = long_df.rename(
        columns={
            "Line": "line_id",
            "E_UTM13Nm": "easting",
            "N_UTM13Nm": "northing",
            "DEM_m": "elevation",
        }
    )

    long_df["line_id"] = long_df["line_id"].astype(str)
    long_df["layer_no"] = long_df["layer_no"].astype("Int16")
    long_df["source_epsg"] = 26913

    long_df = reproject_to_target(long_df, source_epsg=26913)

    # Ensure all canonical columns exist
    long_df = ensure_canonical_columns(long_df)

    # Store system tag for provenance
    long_df["_system"] = system

    validate_dataframe(long_df, filepath)
    validate_dataframe_sample(long_df, filepath)

    logger.info(
        "AGF parsed: %d rows, %d unique soundings",
        len(long_df),
        long_df["record_id"].nunique(),
    )
    return long_df
