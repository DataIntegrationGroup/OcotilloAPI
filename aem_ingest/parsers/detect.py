"""
aem_ingest.parsers.detect — Format detection and flight ID extraction.

Detection logic:
  1. Filename contains '_byLayer' or ends with '.xyz' → bylayer
  2. Filename starts with 'rho_GL'                    → seogi_rho
  3. File header contains 'RHO[0]'                    → agf_lci
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from aem_ingest.schemas import SourceFormat

logger = logging.getLogger(__name__)


def detect_format(filepath: str) -> SourceFormat:
    """Detect which of the three AEM inversion formats a file uses.

    Returns:
        SourceFormat enum member.

    Raises:
        ValueError: if format cannot be determined.
    """
    name = Path(filepath).name

    # Format A — Aarhus Workbench byLayer export
    if "_byLayer" in name or name.lower().endswith(".xyz"):
        logger.info("Detected Format A (Aarhus byLayer) from filename: %s", name)
        return SourceFormat.BYLAYER

    # Format B — Seogi Python rho CSV
    # Pattern: rho_GL{proposal}_F{flight}.csv  or  rho_GL{proposal}_F01-F02.csv
    if name.startswith("rho_GL") and name.endswith(".csv"):
        logger.info("Detected Format B (Seogi rho CSV) from filename: %s", name)
        return SourceFormat.SEOGI_RHO

    # Format C — AGF LCI CSV: bracket-indexed columns like RHO[0], DEP_TOP_m[0].
    # This is the AGF convention; Seogi uses underscore-delimited names.
    try:
        with open(filepath, "r") as f:
            header = f.readline()
        if "RHO[0]" in header or "DEP_TOP_m[0]" in header:
            logger.info("Detected Format C (AGF LCI CSV) from header: %s", name)
            return SourceFormat.AGF_LCI
    except Exception as exc:
        logger.warning("Could not read header of %s for detection: %s", name, exc)

    raise ValueError(
        f"Cannot detect AEM format for '{name}'. Expected *_byLayer.xyz, "
        f"rho_GL*.csv, or CSV with RHO[0] columns."
    )


def extract_flight_id(filepath: str) -> str:
    """Extract the flight ID from a Seogi rho CSV filename.

    Naming patterns:
      rho_GL250193_F02.csv         → 'F02'
      rho_GL250259_F01-F02.csv     → 'F01-F02'  (N. Tularosa multi-flight)

    The flight ID is everything between the last '_' and '.csv'.
    """
    name = Path(filepath).stem  # e.g. "rho_GL250193_F02"
    match = re.search(r"_(F[\d]+([-]F[\d]+)*)$", name)
    if match:
        return match.group(1)

    # Fallback: last segment after underscore
    parts = name.split("_")
    flight_id = parts[-1] if len(parts) >= 3 else "F00"
    logger.warning(
        "Could not parse flight ID from '%s', using fallback: %s",
        name, flight_id,
    )
    return flight_id
