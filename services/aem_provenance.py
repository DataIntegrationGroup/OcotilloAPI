# flake8: noqa: E501
"""Survey- and file-level provenance helpers for AEM ingest."""

from __future__ import annotations

import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

INGESTIBLE_TYPES = {"seogi_rho", "aarhus_bylayer", "agf_lci_csv"}

PROVENANCE_MAP = {
    "seogi_rho": ("seogi_python", "GeoTech/Seogi"),
    "aarhus_bylayer": ("aarhus_sci", "GIP/Aarhus"),
    "agf_lci_csv": ("aarhus_lci", "AGF/Aarhus"),
}

PROVENANCE_OVERRIDES = {
    ("aarhus_bylayer", "santa_teresa"): ("aarhus_sci", "GIP/Aarhus"),
    ("aarhus_bylayer", "mrg_2025"): ("aarhus_sci", "GIP/Ramboll"),
}


def resolve_provenance(detected_type: str, survey_id: str) -> dict[str, str]:
    key = (detected_type, survey_id)
    if key in PROVENANCE_OVERRIDES:
        code, contractor = PROVENANCE_OVERRIDES[key]
    elif detected_type in PROVENANCE_MAP:
        code, contractor = PROVENANCE_MAP[detected_type]
    else:
        raise ValueError(
            f"No provenance mapping for detected_type='{detected_type}', "
            f"survey_id='{survey_id}'. Add it to PROVENANCE_MAP or PROVENANCE_OVERRIDES."
        )
    return {"inversion_code": code, "contractor": contractor}


def resolve_system(detected_type: str, filename: str) -> str | None:
    if detected_type != "agf_lci_csv":
        return None

    fname_lower = filename.lower()
    if "306" in fname_lower:
        return "306hp"
    if "312" in fname_lower:
        return "312hp"

    logger.warning(
        "Cannot determine SkyTEM system from AGF filename '%s'. Expected '306' or '312' in the name.",
        filename,
    )
    return None


def build_raw_file_list(df: pd.DataFrame, survey_id: str) -> list[dict]:
    raw_mask = (
        (df["survey_id"] == survey_id)
        & (df["detected_type"] == "geotech_raw_csv")
        & (df["action"] == "MOVE")
    )
    raw_df = df[raw_mask]
    raw_files = []

    for _, row in raw_df.iterrows():
        fname = row["file_name"]
        flight_id = None
        match = re.search(r"_F(\d+)", fname)
        if match:
            flight_id = f"F{match.group(1)}"

        raw_files.append(
            {
                "file": fname,
                "gcs_path": row["proposed_gcs_path"],
                "flight_id": flight_id,
                "size_bytes": int(row.get("size_bytes", 0)),
                "normalization_needed": row.get("normalization_needed", "N") == "Y",
            }
        )

    return raw_files
