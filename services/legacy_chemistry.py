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
"""Legacy analyte symbols to the lexicon's parameter names.

The legacy NMA chemistry tables record analytes as symbols (`As`, `SO4`,
`pHf`). Every consumer that wants to say something about a result -- compare it
to a drinking water standard, group it, print it for a well owner -- needs the
name, because that is what the rest of the system keys on. Doing that mapping
per consumer means each one gets to be wrong on its own; doing it here means a
symbol resolves the same way everywhere.

An unrecognized symbol passes through unchanged rather than being dropped: the
result is still real and still worth printing, it just carries no name anything
can look up.

Deliberate omissions
--------------------
Ambiguous symbols are left unmapped so nothing downstream can act on a guess.
A parameter with no recognized name is reported without a standards comparison,
which is the safe outcome -- inventing a name is what would let a limit be
applied to the wrong quantity:

- ``NO3``/``NO2`` map to the as-NO3/as-NO2 names, not the as-N ones. The
  nitrate MCL is 10 mg/L *as N*, which is about 45 mg/L as NO3; mapping the
  wrong one flags every moderately nitrated well in the state. ``NO3(N)`` and
  ``NO2(N)`` are the as-N measurements and do map.
- ``CN6``, ``DO``, ``ORP``, ``C14_years``, ``CF``, ``CFC*``, ``GA``, ``GB``,
  ``Ra226``, ``Sr90``: no unambiguous lexicon term, so no mapping.
"""

# Symbol -> lexicon `parameter_name` term. Keys are matched case-sensitively
# first, then case-insensitively, since the legacy tables are inconsistent
# about capitalizing symbols.
LEGACY_ANALYTE_NAMES: dict[str, str] = {
    # --- Major ions and whole-water measures ---
    "Ca": "Calcium",
    "Ca(total)": "Calcium, total, unfiltered",
    "Mg": "Magnesium",
    "Mg(total)": "Magnesium, total, unfiltered",
    "Na": "Sodium",
    "Na(total)": "Sodium, total, unfiltered",
    "K": "Potassium",
    "K(total)": "Potassium, total, unfiltered",
    "HCO3": "Bicarbonate",
    "CO3": "Carbonate",
    "SO4": "Sulfate",
    "Cl": "Chloride",
    "F": "Fluoride",
    "Br": "Bromide",
    "TDS": "Total Dissolved Solids",
    "HRD": "Hardness (CaCO3)",
    "ALK": "Alkalinity, Total",
    "IONBAL": "Ion Balance",
    "TAn": "Total Anions",
    "TCat": "Total Cations",
    "PO4": "Phosphate",
    "NO3": "Nitrate (as NO3)",
    "NO3(N)": "Nitrate (as N)",
    "NO2": "Nitrite (as NO2)",
    "NO2(N)": "Nitrite (as N)",
    "NH4": "Ammonium",
    "H2S": "Hydrogen sulfide",
    "DOC": "Dissolved organic carbon",
    "TOC": "Total organic carbon",
    "TKN": "Total Kjeldahl nitrogen",
    "TN": "Total nitrogen",
    "SiO2": "Silica",
    "Si": "Silicon",
    "Si(total)": "Silicon, total, unfiltered",
    # --- Metals and trace elements ---
    "Ag": "Silver",
    "Ag(total)": "Silver, total, unfiltered",
    "Al": "Aluminum",
    "Al(total)": "Aluminum, total, unfiltered",
    "As": "Arsenic",
    "As(total)": "Arsenic, total, unfiltered",
    "B": "Boron",
    "B(total)": "Boron, total, unfiltered",
    "Ba": "Barium",
    "Ba(total)": "Barium, total, unfiltered",
    "Be": "Beryllium",
    "Be(total)": "Beryllium, total, unfiltered",
    "Cd": "Cadmium",
    "Cd(total)": "Cadmium, total, unfiltered",
    "Co": "Cobalt",
    "Co(total)": "Cobalt, total, unfiltered",
    "Cr": "Chromium",
    "Cr(total)": "Chromium, total, unfiltered",
    "Cu": "Copper",
    "Cu(total)": "Copper, total, unfiltered",
    "Fe": "Iron",
    "Fe(total)": "Iron, total, unfiltered",
    "Hg": "Mercury",
    "Hg(total)": "Mercury, total, unfiltered",
    "Li": "Lithium",
    "Li(total)": "Lithium, total, unfiltered",
    "Mn": "Manganese",
    "Mn(total)": "Manganese, total, unfiltered",
    "Mo": "Molybdenum",
    "Mo(total)": "Molybdenum, total, unfiltered",
    "Ni": "Nickel",
    "Ni(total)": "Nickel, total, unfiltered",
    "Pb": "Lead",
    "Pb(total)": "Lead, total, unfiltered",
    "Sb": "Antimony",
    "Sb(total)": "Antimony, total, unfiltered",
    "Se": "Selenium",
    "Se(total)": "Selenium, total, unfiltered",
    "Sn": "Tin",
    "Sn(total)": "Tin, total, unfiltered",
    "Sr": "Strontium",
    "Sr(total)": "Strontium, total, unfiltered",
    "Th": "Thorium",
    "Th(total)": "Thorium, total, unfiltered",
    "Ti": "Titanium",
    "Ti(total)": "Titanium, total, unfiltered",
    "Tl": "Thallium",
    "Tl(total)": "Thallium, total, unfiltered",
    # The uranium MCL (0.03 mg/L) is for total uranium; the lexicon spells the
    # measurement it belongs to with the method it is usually run by.
    "U": "Uranium (total, by ICP-MS)",
    "U(total)": "Uranium, total, unfiltered",
    "V": "Vanadium",
    "V(total)": "Vanadium, total, unfiltered",
    "Zn": "Zinc",
    "Zn(total)": "Zinc, total, unfiltered",
    # --- Field and laboratory measurements ---
    # Field and lab pH are the same quantity to the lexicon; which instrument
    # read it is carried by the source table, not by the parameter name.
    "pHf": "pH",
    "pHL": "pH",
    "T": "temperature",
    "CONDLAB": "Conductivity, laboratory",
    # --- Isotopes ---
    "3H": "Tritium",
    "H2r": "Deuterium:Hydrogen ratio",
    "O18r": "18O:16O ratio",
    "C13r": "13C:12C ratio",
    "C14": "14C content, pmc",
    "d18O-SO4": "delta O18 sulfate",
    "d34S-SO4": "Sulfate 34 isotope ratio",
}

_LEGACY_ANALYTE_NAMES_LOWER = {
    symbol.lower(): name for symbol, name in LEGACY_ANALYTE_NAMES.items()
}


def canonical_parameter_name(symbol: str | None) -> str | None:
    """The lexicon parameter name for a legacy analyte symbol.

    Returns the symbol unchanged when it is not one this module knows about.
    """
    if symbol is None:
        return None

    trimmed = symbol.strip()
    if not trimmed:
        return trimmed

    if trimmed in LEGACY_ANALYTE_NAMES:
        return LEGACY_ANALYTE_NAMES[trimmed]

    return _LEGACY_ANALYTE_NAMES_LOWER.get(trimmed.lower(), trimmed)


# The view's text ids are prefixed with the legacy table they came from. That
# prefix is the only record of whether a result was read in the field or by a
# lab, so it is translated into something a client can read rather than being
# left for each client to parse out of an id.
_RESULT_KINDS = {
    "maj": "major",
    "min": "minor",
    "rad": "radionuclide",
    "fld": "field",
}


def result_kind(result_id: str | None) -> str:
    """Which legacy chemistry table a view row came from."""
    if not result_id:
        return "unknown"

    prefix, _, remainder = result_id.partition("-")
    if not remainder:
        return "unknown"

    return _RESULT_KINDS.get(prefix, "unknown")


# ============= EOF =============================================
