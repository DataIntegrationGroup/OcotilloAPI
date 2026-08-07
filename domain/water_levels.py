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
"""
Water level rules used when importing measurement spreadsheets.

The importer resolves the well and its measuring point history from the database
and then hands the plain numbers to these functions. Messages are returned
without a row prefix; the caller adds ``Row N:`` so the same rule can be reported
from a per-row importer or from a single-record API call.
"""

MEASUREMENT_UNIT = "ft"
SAMPLE_MATRIX = "groundwater"
SAMPLE_QC_TYPE = "Normal"
GROUNDWATER_LEVEL_ACTIVITY_TYPE = "groundwater level"


def reconcile_measuring_point_height(
    csv_mp_height: float | None,
    existing_mp_height: float | int | None,
) -> tuple[float | int | None, float | int | None, bool]:
    """
    Decide which measuring point height applies to a measurement.

    Returns ``(resolved, existing, differs)``. A height given in the CSV wins over
    the well's recorded history, because the field crew measured it on the day of
    the reading; ``differs`` reports that the two disagreed so the caller can warn
    without rejecting the row.

    ``existing_mp_height`` arrives as whatever the database column yields, often a
    ``Decimal``, and is coerced to ``float`` so callers compare and render like
    values.
    """
    if existing_mp_height is not None:
        existing_mp_height = float(existing_mp_height)

    if csv_mp_height is not None:
        differs = existing_mp_height is not None and csv_mp_height != existing_mp_height
        return csv_mp_height, existing_mp_height, differs

    return existing_mp_height, existing_mp_height, False


def measuring_point_height_conflict_message(
    csv_mp_height: float | None,
    existing_mp_height: float | int | None,
) -> str:
    """Describe a CSV height that overrides a different recorded height."""
    return (
        f"CSV mp_height ({csv_mp_height}) differs from existing measuring point "
        f"height ({existing_mp_height}); CSV value will be used"
    )


def depth_to_water_error(
    depth_to_water_ft: float | None,
    resolved_mp_height: float | int | None,
    well_depth: float | int | None,
) -> str | None:
    """
    Reject a reading that puts the water table below the bottom of the well.

    ``depth_to_water_ft`` is measured from the measuring point, which sits above
    the ground surface, while ``well_depth`` is measured from the ground surface,
    so the two are only comparable after subtracting the measuring point height.

    Returns ``None`` when the check does not apply -- any of the three inputs may
    be missing, and an unknown well depth is not evidence of a bad reading.
    """
    if depth_to_water_ft is None or resolved_mp_height is None or well_depth is None:
        return None

    well_depth = float(well_depth)
    corrected_depth_to_water = depth_to_water_ft - resolved_mp_height
    if corrected_depth_to_water >= well_depth:
        return (
            f"depth_to_water_ft minus measuring point height "
            f"({corrected_depth_to_water}) must be less than well depth "
            f"({well_depth})"
        )

    return None


# ============= EOF =============================================
