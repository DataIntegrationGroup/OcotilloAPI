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
Van Essen mapping rules.

No database, no network -- these are the rules alone, which is the point of
keeping them in `domain/`.
"""

from datetime import datetime, timezone

import pytest

from domain.van_essen import (
    VanEssenMappingError,
    depth_to_water_ft,
    external_point_key,
    external_series_key,
    parse_reading_timestamp,
)


class TestTimestamps:
    def test_naive_is_read_as_utc(self):
        # The API documents UTC and does not always mark it. Reading naive as
        # local would shift every observation by the machine's offset, and shift
        # it differently on a laptop and in a container.
        assert parse_reading_timestamp("2024-10-30T20:00:00") == datetime(
            2024, 10, 30, 20, 0, tzinfo=timezone.utc
        )

    def test_explicit_utc_matches_naive(self):
        assert parse_reading_timestamp(
            "2024-10-30T20:00:00Z"
        ) == parse_reading_timestamp("2024-10-30T20:00:00")

    def test_offset_is_normalized_to_utc(self):
        assert parse_reading_timestamp("2024-10-30T14:00:00-06:00") == datetime(
            2024, 10, 30, 20, 0, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("value", ["", "   ", None, "not-a-date", "2024-13-45"])
    def test_unusable_timestamps_raise(self, value):
        with pytest.raises(VanEssenMappingError):
            parse_reading_timestamp(value)


class TestDepthConversion:
    def test_centimetres_become_feet(self):
        # SO-0125 on 2024-10-30: 471.518 cm below ground surface.
        assert depth_to_water_ft(471.518) == 15.469751

    def test_gap_passes_through(self):
        # The vendor reports gaps. A gap is not an error.
        assert depth_to_water_ft(None) is None

    def test_negative_depth_is_kept(self):
        # Depth below ground goes negative when water stands above ground, which
        # happens in these riparian wells at high flow. Clamping would erase
        # real data.
        assert depth_to_water_ft(-50.0) == pytest.approx(-1.64042, rel=1e-4)

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), "471.518", True])
    def test_unusable_values_raise(self, value):
        with pytest.raises(VanEssenMappingError):
            depth_to_water_ft(value)


class TestExternalKeys:
    def test_point_key_uses_the_numeric_id(self):
        # Names like SO-0125 are Bureau point ids and can be corrected; the
        # numeric id is what a re-run must resolve to the same record.
        assert external_point_key(40) == "sanacaciareach-40"

    def test_series_key_names_the_datum(self):
        # A point may later carry temperature or conductivity, both already in
        # the vendor's raw payload.
        assert external_series_key(40) == "sanacaciareach-40:dtw-gs"

    def test_keys_are_stable_across_calls(self):
        assert external_point_key(40) == external_point_key(40)

    @pytest.mark.parametrize("value", [0, -1, "40", None, True])
    def test_unusable_ids_raise(self, value):
        with pytest.raises(VanEssenMappingError):
            external_point_key(value)


# ============= EOF =============================================
