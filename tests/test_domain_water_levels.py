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
"""Water level and sample-naming rules. No database, no fixtures."""

from datetime import datetime
from decimal import Decimal

from domain.samples import water_level_sample_name
from domain.water_levels import (
    depth_to_water_error,
    measuring_point_height_conflict_message,
    reconcile_measuring_point_height,
)


# --------------------------------------------------------------------------
# reconcile_measuring_point_height
# --------------------------------------------------------------------------
def test_reconcile_prefers_the_csv_height_and_reports_the_difference():
    resolved, existing, differs = reconcile_measuring_point_height(4.0, 3.5)

    assert resolved == 4.0
    assert existing == 3.5
    assert differs is True


def test_reconcile_falls_back_to_the_recorded_height():
    resolved, existing, differs = reconcile_measuring_point_height(None, 3.5)

    assert resolved == 3.5
    assert existing == 3.5
    assert differs is False


def test_reconcile_coerces_a_decimal_history_value():
    resolved, existing, differs = reconcile_measuring_point_height(None, Decimal("3.5"))

    assert resolved == 3.5
    assert isinstance(existing, float)
    assert differs is False


def test_reconcile_allows_both_missing():
    assert reconcile_measuring_point_height(None, None) == (None, None, False)


def test_reconcile_does_not_flag_a_matching_height():
    _, _, differs = reconcile_measuring_point_height(3.5, Decimal("3.5"))

    assert differs is False


def test_reconcile_does_not_flag_a_csv_height_with_no_history():
    resolved, existing, differs = reconcile_measuring_point_height(4.0, None)

    assert resolved == 4.0
    assert existing is None
    assert differs is False


def test_measuring_point_height_conflict_message_names_both_values():
    assert measuring_point_height_conflict_message(1.5, 2.0) == (
        "CSV mp_height (1.5) differs from existing measuring point height (2.0); "
        "CSV value will be used"
    )


# --------------------------------------------------------------------------
# depth_to_water_error
# --------------------------------------------------------------------------
def test_depth_to_water_error_rejects_a_reading_below_the_well_bottom():
    assert depth_to_water_error(12.5, 1.0, 10.0) == (
        "depth_to_water_ft minus measuring point height (11.5) "
        "must be less than well depth (10.0)"
    )


def test_depth_to_water_error_accepts_a_reading_inside_the_well():
    assert depth_to_water_error(8.0, 1.0, 10.0) is None


def test_depth_to_water_error_rejects_water_exactly_at_the_bottom():
    # The corrected depth must be strictly less than the well depth.
    assert depth_to_water_error(11.0, 1.0, 10.0) is not None


def test_depth_to_water_error_subtracts_the_measuring_point_height():
    # Without the correction this reading would look like it was past the bottom.
    assert depth_to_water_error(10.5, 1.0, 10.0) is None


def test_depth_to_water_error_coerces_a_decimal_well_depth():
    assert depth_to_water_error(12.5, 1.0, Decimal("10.0")) == (
        "depth_to_water_ft minus measuring point height (11.5) "
        "must be less than well depth (10.0)"
    )


def test_depth_to_water_error_skips_when_an_input_is_missing():
    assert depth_to_water_error(None, 1.0, 10.0) is None
    assert depth_to_water_error(12.5, None, 10.0) is None
    assert depth_to_water_error(12.5, 1.0, None) is None


# --------------------------------------------------------------------------
# water_level_sample_name
# --------------------------------------------------------------------------
def test_water_level_sample_name_is_deterministic():
    measured_at = datetime(2026, 3, 4, 9, 5)

    assert water_level_sample_name("AR0001", measured_at) == "AR0001-WL-202603040905"


def test_water_level_sample_name_ignores_sub_minute_precision():
    # Both importers must agree on the name for re-import matching to work, so
    # seconds are deliberately not part of it.
    with_seconds = datetime(2026, 3, 4, 9, 5, 42)
    without_seconds = datetime(2026, 3, 4, 9, 5)

    assert water_level_sample_name("AR0001", with_seconds) == water_level_sample_name(
        "AR0001", without_seconds
    )


# ============= EOF =============================================
