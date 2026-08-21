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
"""Legacy analyte symbol to lexicon parameter name mapping."""

import pytest

from services.legacy_chemistry import canonical_parameter_name


@pytest.mark.parametrize(
    "symbol, expected",
    [
        ("As", "Arsenic"),
        ("Pb", "Lead"),
        ("SO4", "Sulfate"),
        ("TDS", "Total Dissolved Solids"),
        ("HRD", "Hardness (CaCO3)"),
        ("pHf", "pH"),
        ("pHL", "pH"),
        ("As(total)", "Arsenic, total, unfiltered"),
        ("H2r", "Deuterium:Hydrogen ratio"),
    ],
)
def test_maps_legacy_symbols_to_lexicon_names(symbol, expected):
    assert canonical_parameter_name(symbol) == expected


def test_distinguishes_nitrate_as_n_from_nitrate_as_no3():
    """The nitrate MCL is 10 mg/L *as N*, roughly 45 mg/L as NO3.

    Collapsing the two would apply the as-N limit to an as-NO3 number and flag
    wells that are nowhere near it, so only the as-N measurement gets the name
    the standard is keyed to.
    """
    assert canonical_parameter_name("NO3(N)") == "Nitrate (as N)"
    assert canonical_parameter_name("NO3") == "Nitrate (as NO3)"
    assert canonical_parameter_name("NO2(N)") == "Nitrite (as N)"
    assert canonical_parameter_name("NO2") == "Nitrite (as NO2)"


@pytest.mark.parametrize("symbol", ["CN6", "DO", "ORP", "C14_years", "GA", "Ra226"])
def test_leaves_ambiguous_symbols_alone(symbol):
    """An unmapped symbol is reported as-is and compared to nothing.

    Guessing a name is what would let a limit be applied to the wrong quantity.
    """
    assert canonical_parameter_name(symbol) == symbol


def test_tolerates_legacy_capitalization_and_padding():
    assert canonical_parameter_name(" as ") == "Arsenic"
    assert canonical_parameter_name("TDS ") == "Total Dissolved Solids"


def test_passes_through_unknown_and_empty_values():
    assert canonical_parameter_name("NotAnAnalyte") == "NotAnAnalyte"
    assert canonical_parameter_name("") == ""
    assert canonical_parameter_name(None) is None


# ============= EOF =============================================
