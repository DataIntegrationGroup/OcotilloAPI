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
import re
from datetime import datetime

from pandas import isna
from sqlalchemy.orm import Session

from db import GeologicFormation, Location, LocationThingAssociation, Thing
from transfers.transferer import Transferer
from services.gcs_helper import get_storage_bucket
from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)
from transfers.logger import logger
from transfers.util import download_blob_json, upload_blob_json

NMA_MONITORING_FREQUENCY = {
    "6": "Biannual",
    "A": "Annual",
    "B": "Bimonthly",
    "L": "Decadal",
    "M": "Monthly",
    "R": "Bimonthly reported",
    "N": "Biannual",
}

PUMP_PATTERN = re.compile(
    r"\b(?P<term>jet|hand|submersible)\b|\b(?P<phrase>line[-\s]+shaft)\b", re.IGNORECASE
)


def get_first_visit_date(row) -> datetime | None:
    first_visit_date = None

    def _extract_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f").date()

    if row.DateCreated and row.SiteDate:
        date_created = _extract_date(row.DateCreated)
        site_date = _extract_date(row.SiteDate)

        if date_created < site_date:
            first_visit_date = date_created
        else:
            first_visit_date = site_date
    elif row.DateCreated and not row.SiteDate:
        first_visit_date = _extract_date(row.DateCreated)
    elif not row.DateCreated and row.SiteDate:
        first_visit_date = _extract_date(row.SiteDate)

    return first_visit_date


def extract_casing_materials(row) -> list[str]:
    materials = []
    if "pvc" in row.CasingDescription.lower():
        materials.append("PVC")

    if "steel" in row.CasingDescription.lower():
        materials.append("Steel")

    if "concrete" in row.CasingDescription.lower():
        materials.append("Concrete")
    return materials


def first_matched_term(text: str):
    m = PUMP_PATTERN.search(text)
    if not m:
        return None
    return m.group("term") or m.group("phrase")


def extract_well_pump_type(row) -> str | None:
    if isna(row.ConstructionNotes):
        return None
    construction_notes = row.ConstructionNotes.lower()
    pump = first_matched_term(construction_notes)
    if pump:
        return pump.capitalize()
    else:
        return None


def extract_aquifer_type_codes(aquifer_code: str) -> list[str]:
    """
    Parse aquifer type codes that may contain multiple values.

    Args:
        aquifer_code: Raw code from AquiferType field

    Returns:
        List of individual codes
    """
    if not aquifer_code:
        return []
    # clean the code
    code = aquifer_code.strip().upper()
    # split into individual characters. This handles cases like "FC" -> ["F", "C"]
    individual_codes = list(code)
    return individual_codes


def get_or_create_geologic_formation(
    session: Session, formation_code: str
) -> GeologicFormation | None:
    """
    Get existing geologic formation or create new one if it doesn't exist.

    Args:
        session: Database session
        formation_code: The formation code from FormationZone field

    Returns:
        GeologicFormation object or None if creation fails
    """
    # Try to find existing formation
    formation = (
        session.query(GeologicFormation)
        .filter(GeologicFormation.formation_code == formation_code)
        .first()
    )

    if formation:
        return formation

    # If not found, create new formation
    try:
        logger.info(f"Creating new geologic formation: {formation_code}")
        formation = GeologicFormation(
            formation_code=formation_code,
            description=None,
            lithology=None,
        )
        session.add(formation)
        session.flush()
        return formation
    except Exception as e:
        logger.critical(f"Error creating formation {formation_code}: {e}")
        return None


def get_cached_elevations() -> dict:
    bucket = get_storage_bucket()
    log_filename = "transfer_data/cached_elevations.json"
    blob = bucket.blob(log_filename)
    return download_blob_json(blob, default={})


def dump_cached_elevations(lut: dict):
    bucket = get_storage_bucket()
    log_filename = "transfer_data/cached_elevations.json"
    blob = bucket.blob(log_filename)
    upload_blob_json(blob, lut)


def cleanup_locations(session, pointids: list[str] | None = None):
    normalized_pointids = Transferer._normalize_pointids(pointids)

    location_query = session.query(Location)
    if normalized_pointids:
        location_query = (
            location_query.join(
                LocationThingAssociation,
                LocationThingAssociation.location_id == Location.id,
            )
            .join(Thing, Thing.id == LocationThingAssociation.thing_id)
            .filter(Thing.name.in_(normalized_pointids))
            .distinct()
        )

    locations = location_query.all()
    n = len(locations)
    lut = {}

    if normalized_pointids:
        logger.info(
            "Scoped location cleanup active for PointIDs %s (%s Location records)",
            normalized_pointids,
            n,
        )

    bucket = get_storage_bucket()
    log_filename = "transfer_data/location_cleanup.json"
    blob = bucket.blob(log_filename)
    if blob.exists():
        lut = download_blob_json(blob, default={})

    updates = []
    for i, location in enumerate(locations):
        if i and not i % 100:
            logger.info(f"Processing row {i} of {n}. dumping lut to {log_filename}")
            upload_blob_json(blob, lut)
            session.bulk_update_mappings(Location, updates)
            session.commit()
            updates = []

        y, x = location.latlon
        xykey = f"{y},{x}"
        if xykey in lut:
            state, county, quad_name = lut[xykey]
        else:
            state = location.state
            county = location.county
            quad_name = location.quad_name
            if not state:
                state = get_state_from_point(x, y)

            if not county:
                county = get_county_from_point(x, y)

            if not quad_name:
                quad_name = get_quad_name_from_point(x, y)

            lut[xykey] = [state, county, quad_name]

        updates.append(
            {
                "id": location.id,
                "state": state,
                "county": county,
                "quad_name": quad_name,
            }
        )

        logger.info(
            f"{i}/{n} lat: {y} lon: {x} state={state}, county={county}, quad"
            f"={quad_name}"
        )

    upload_blob_json(blob, lut)
    if updates:
        session.bulk_update_mappings(Location, updates)
        session.commit()


# ============= EOF =============================================
