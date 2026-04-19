# flake8: noqa: E501
"""
services.aem_parsers.common — Shared constants and coordinate helpers.

Used by all three parsers.  Keeps coordinate math in one place so
the CRS logic doesn't get duplicated (or subtly diverge).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pyproj import Transformer

logger = logging.getLogger(__name__)

# All surveys are delivered in UTM Zone 13N. GIP/SkyTEM and AGF deliver
# NAD83 (EPSG:26913). GeoTech/Seogi delivers WGS84 UTM 13N (EPSG:32613).
# The ~1 m datum shift still matters, so we normalize projected coordinates
# to 26913 in-memory before deriving the stored WGS84 geometry.
TARGET_EPSG = 26913

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


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def reproject_to_target(df: pd.DataFrame, source_epsg: int) -> pd.DataFrame:
    """Reproject easting/northing to TARGET_EPSG (26913) when needed.

    Used for Format B (Seogi) where source is EPSG:32613 (WGS84 UTM 13N).
    The difference between WGS84 and NAD83 is ~1 m — small but real.
    We record the original CRS in source_epsg for provenance.
    """
    if source_epsg == TARGET_EPSG:
        return df

    to_target = Transformer.from_crs(
        f"EPSG:{source_epsg}", f"EPSG:{TARGET_EPSG}", always_xy=True
    )
    new_e, new_n = to_target.transform(df["easting"].values, df["northing"].values)
    df["easting"] = new_e
    df["northing"] = new_n

    return df


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
