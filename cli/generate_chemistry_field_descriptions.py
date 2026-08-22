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
"""Emit the chemistry blocks of ``core/ogc-field-descriptions.yml``.

``ogc_major_chemistry_results`` and ``ogc_minor_chemistry_wells`` publish one
column per analyte plus a paired units column -- 190 columns between them.
Hand-writing that is error-prone, so this script generates it and the output is
reviewed and committed. Run it again when the analyte lists change:

    uv run python -m cli.generate_chemistry_field_descriptions > /tmp/chem.yml

Source of truth is the analyte lists in the migration that builds the two
views, which are the column names themselves. (``core/parameter.json`` holds
only two field parameters, so the lexicon cannot supply this.)

Analytes needing more than a one-line gloss are spelled out in ANALYTE_PROSE;
anything absent falls back to a generated title and a stock description. Prose
here loses to a hand-written entry in the YAML, which wins on merge.
"""

import importlib.util
import sys
import textwrap
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/f4a5b6c7d8e9_apply_public_release_status_filter_to_ogc_views.py"
)

# Analyte key -> (title, description). Everything else gets a generated title
# and the stock "dissolved concentration" line.
ANALYTE_PROSE = {
    "tds": (
        "Total dissolved solids",
        "Total mass of dissolved mineral matter in the water -- in plain terms, "
        "how salty it is. Drinking-water guidance sits around 500 mg/L.",
    ),
    "ph": (
        "pH",
        "Acidity of the water on the 0-14 scale, where 7 is neutral. Unitless. "
        "Most New Mexico groundwater falls between 7 and 8.5.",
    ),
    "specific_conductance": (
        "Specific conductance",
        "How well the water conducts electricity, which rises with dissolved "
        "mineral content. Used as a fast field proxy for total dissolved solids.",
    ),
    "hardness": (
        "Hardness",
        "Combined calcium and magnesium content, reported as an equivalent mass "
        "of calcium carbonate. What determines whether water is 'hard'.",
    ),
    "alkalinity": (
        "Alkalinity",
        "The water's capacity to neutralise acid, reported as an equivalent mass "
        "of calcium carbonate. Mostly supplied by bicarbonate and carbonate.",
    ),
    "ion_balance": (
        "Ion balance",
        "Percentage difference between the total positive and total negative "
        "charge in the analysis. Charge must balance in reality, so a figure far "
        "from zero means the analysis is incomplete or in error.",
    ),
    "total_cations": (
        "Total cations",
        "Sum of the positively charged dissolved constituents in the analysis.",
    ),
    "total_anions": (
        "Total anions",
        "Sum of the negatively charged dissolved constituents in the analysis.",
    ),
    "sodium_plus_potassium": (
        "Sodium plus potassium",
        "Combined sodium and potassium concentration, reported together where the "
        "laboratory did not separate them.",
    ),
    "nitrate": (
        "Nitrate",
        "Dissolved nitrate concentration, usually from fertiliser, septic systems, "
        "or livestock. The drinking-water limit is 10 mg/L as nitrogen.",
    ),
    "nitrate_as_n": (
        "Nitrate as nitrogen",
        "Nitrate concentration expressed as the mass of nitrogen alone, which is "
        "how the 10 mg/L drinking-water limit is written. Roughly a quarter of the "
        "same sample reported as nitrate.",
    ),
    "nitrite": (
        "Nitrite",
        "Dissolved nitrite concentration, an intermediate stage in the breakdown of "
        "nitrogen compounds.",
    ),
    "silica": (
        "Silica",
        "Dissolved silica concentration, weathered out of silicate rock. Useful for "
        "estimating the temperature water last equilibrated at.",
    ),
    "arsenic": (
        "Arsenic",
        "Dissolved arsenic concentration. Naturally elevated in parts of New Mexico "
        "and regulated in drinking water at 0.010 mg/L.",
    ),
    "uranium": (
        "Uranium",
        "Dissolved uranium concentration. Naturally present near uranium-bearing "
        "rock and regulated in drinking water at 0.030 mg/L.",
    ),
    "fluoride": (
        "Fluoride",
        "Dissolved fluoride concentration. Beneficial in small amounts; the "
        "drinking-water limit is 4 mg/L.",
    ),
    "h2r": (
        "Deuterium ratio",
        "Ratio of heavy to ordinary hydrogen in the water, reported as per-mil "
        "difference from ocean water. Fingerprints where the water fell as "
        "precipitation.",
    ),
    "o18r": (
        "Oxygen-18 ratio",
        "Ratio of heavy to ordinary oxygen in the water, reported as per-mil "
        "difference from ocean water. Read with the deuterium ratio to trace the "
        "water's origin and evaporation history.",
    ),
    "c13r": (
        "Carbon-13 ratio",
        "Ratio of carbon-13 to carbon-12 in the water's dissolved carbon, reported "
        "as per-mil difference from a standard. Helps identify where the carbon "
        "came from, which is needed to correct a carbon-14 age.",
    ),
    "c14": (
        "Carbon-14",
        "Carbon-14 remaining in the water's dissolved carbon, as a percentage of "
        "the modern atmospheric level. The basis for dating groundwater up to "
        "roughly 40,000 years old.",
    ),
    "c14_years": (
        "Carbon-14 age",
        "Apparent age of the water in years, calculated from its carbon-14 content. "
        "Uncorrected for carbon picked up from rock, so treat it as an upper bound.",
    ),
    "bromide": (
        "Bromide",
        "Dissolved bromide concentration. Read against chloride, it distinguishes "
        "seawater-derived salinity from dissolved halite.",
    ),
}

# Elements whose column name is not the plain element name.
ELEMENT_NAMES = {
    "silicon": "silicon",
    "molybdenum": "molybdenum",
    "strontium": "strontium",
}

STOCK_DESCRIPTION = (
    "Dissolved {name} concentration in the most recent sample analysed for it."
)
TOTAL_DESCRIPTION = (
    "Total {name} concentration -- the unfiltered determination, which counts "
    "{name} bound to suspended particles as well as the dissolved fraction."
)
UNITS_DESCRIPTION = (
    "Units the {title_lower} value is reported in, as the laboratory recorded them."
)


def _load_analyte_lists():
    """Import the migration module by path and read its analyte column lists."""
    spec = importlib.util.spec_from_file_location("_ogc_filter_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        [key for key, _ in module.STATIC_ANALYTE_COLUMNS_MAJOR],
        [key for key, _ in module.STATIC_ANALYTE_COLUMNS_MINOR],
    )


def _entry(analyte_key: str):
    if analyte_key in ANALYTE_PROSE:
        return ANALYTE_PROSE[analyte_key]

    if analyte_key.endswith("_total"):
        base = analyte_key[: -len("_total")]
        name = ELEMENT_NAMES.get(base, base).replace("_", " ")
        title = f"{name.capitalize()} (total)"
        return title, TOTAL_DESCRIPTION.format(name=name)

    name = ELEMENT_NAMES.get(analyte_key, analyte_key).replace("_", " ")
    return name.capitalize(), STOCK_DESCRIPTION.format(name=name)


def _yaml_block(field: str, title: str, description: str) -> str:
    body = textwrap.fill(
        description,
        width=74,
        initial_indent=" " * 6,
        subsequent_indent=" " * 6,
        break_on_hyphens=False,
        break_long_words=False,
    )
    return f"  {field}:\n    title: {title}\n    description: >-\n{body}\n"


def render(table: str, analyte_keys) -> str:
    lines = [f"{table}:"]
    lines.append(
        _yaml_block(
            "location_id",
            "Location ID",
            "Identifier of the location record the well's coordinates came from.",
        )
    )
    lines.append(
        _yaml_block(
            "analyte_count",
            "Analyte count",
            "Number of distinct analytes with a value in this row. A low count "
            "means the well has only been analysed for part of the suite.",
        )
    )
    lines.append(
        _yaml_block(
            "latest_chemistry_date",
            "Latest analysis date",
            "Date of the most recent result in this row. Analytes are carried "
            "forward independently, so an individual value may be older than "
            "this date.",
        )
    )
    for key in analyte_keys:
        title, description = _entry(key)
        lines.append(_yaml_block(key, title, description))
        lines.append(
            _yaml_block(
                f"{key}_units",
                f"{title} units",
                UNITS_DESCRIPTION.format(title_lower=title.lower()),
            )
        )
    return "\n".join(lines)


def main() -> int:
    major, minor = _load_analyte_lists()
    print(
        "# Generated by cli/generate_chemistry_field_descriptions.py -- review before committing."
    )
    print(render("major_chemistry_results", major))
    print(render("minor_chemistry_wells", minor))
    return 0


if __name__ == "__main__":
    sys.exit(main())
