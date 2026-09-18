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
"""Unit conversion rules. No database, no fixtures."""

from domain.units import INCHES_PER_FOOT, convert_ft_to_in


def test_convert_ft_to_in():
    assert convert_ft_to_in(0) == 0.0
    assert convert_ft_to_in(1) == 12.0
    # The two casing diameters carried by the well inventory CSV fixtures.
    assert convert_ft_to_in(0.5) == 6.0
    assert convert_ft_to_in(0.75) == 9.0
    assert convert_ft_to_in(None) is None


def test_convert_ft_to_in_rounds_to_ndigits():
    assert convert_ft_to_in(1 / 3) == 4.0
    assert convert_ft_to_in(0.13579, ndigits=2) == 1.63


def test_inches_per_foot_is_exact():
    # Guards against the constant drifting into an approximation the way
    # METERS_TO_FEET necessarily is.
    assert INCHES_PER_FOOT == 12.0


# ============= EOF =============================================
