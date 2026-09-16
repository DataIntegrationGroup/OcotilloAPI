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
Seed the EPA drinking-water limits into `regulatory_limit`.

`core/regulatory_limit.json` holds the federal primary MCLs (40 CFR 141.62,
141.66) and secondary SMCLs (40 CFR 143.3) for every analyte that is already a
`parameter_name` lexicon term. `core.initializers.init_regulatory_limit` loads
it on a fresh seed; this migration exists because deploys run no seed.

A limit points at a `Parameter`, and deployed databases hold only the two field
parameters, so the groundwater parameters the limits need are added from
`core/parameter.json` first. Every limit value, source, type and unit is a
lexicon foreign key, and `EPA` reaches a database only through
`oco initialize-lexicon`, so any term the rows depend on that is missing is
inserted from `core/lexicon.json` with its categories.

Everything is add-if-missing: existing terms, parameters and limits -- a limit
is identified by parameter, source and type -- are left alone, so re-running is
a no-op and a hand-edited limit value survives.

Left out on purpose: the pH and aluminum SMCLs, which are ranges that the
single `limit_value` column cannot hold, and lead and copper's action levels,
which are treatment-technique triggers rather than MCLs.

No alembic revision accompanies this; `regulatory_limit` has existed since the
initial migration.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.initializers import add_regulatory_limits, load_regulatory_limits
from data_migrations.base import DataMigration
from db.lexicon import LexiconCategory, LexiconTerm, LexiconTermCategoryAssociation
from db.parameter import Parameter

CORE_DIR = Path(__file__).resolve().parents[2] / "core"

PARAMETER_TERM_FIELDS = ("parameter_name", "matrix", "parameter_type", "default_unit")
LIMIT_TERM_FIELDS = ("limit_source", "limit_type", "limit_unit")


def _load(name: str):
    with open(CORE_DIR / name) as f:
        return json.load(f)


def _needed_parameters(limits: list[dict]) -> list[dict]:
    keys = {(limit["parameter_name"], limit["matrix"]) for limit in limits}
    return [
        param
        for param in _load("parameter.json")
        if (param["parameter_name"], param["matrix"]) in keys
    ]


def _add_missing_terms(session: Session, values: set[str]) -> int:
    lexicon = _load("lexicon.json")
    seeded = {term["term"]: term for term in lexicon["terms"]}
    missing = values - set(
        session.scalars(select(LexiconTerm.term).where(LexiconTerm.term.in_(values)))
    )
    unknown = missing - seeded.keys()
    if unknown:
        raise ValueError(f"Terms not in core/lexicon.json: {sorted(unknown)}")

    category_ids = dict(
        session.execute(select(LexiconCategory.name, LexiconCategory.id))
    )
    for value in sorted(missing):
        term = LexiconTerm(term=value, definition=seeded[value]["definition"])
        session.add(term)
        session.flush()
        for category in seeded[value]["categories"]:
            if category in category_ids:
                session.add(
                    LexiconTermCategoryAssociation(
                        term_id=term.id, category_id=category_ids[category]
                    )
                )
    session.flush()
    return len(missing)


def _add_missing_parameters(session: Session, params: list[dict]) -> int:
    existing = set(session.execute(select(Parameter.parameter_name, Parameter.matrix)))
    added = 0
    for param in params:
        if (param["parameter_name"], param["matrix"]) in existing:
            continue
        session.add(
            Parameter(
                parameter_name=param["parameter_name"],
                matrix=param["matrix"],
                parameter_type=param["parameter_type"],
                cas_number=param["cas_number"],
                default_unit=param["default_unit"],
            )
        )
        added += 1
    session.flush()
    return added


def run(session: Session) -> None:
    limits = load_regulatory_limits()
    params = _needed_parameters(limits)

    values = {
        param[field]
        for param in params
        for field in PARAMETER_TERM_FIELDS
        if param[field]
    }
    values |= {limit[field] for limit in limits for field in LIMIT_TERM_FIELDS}

    terms = _add_missing_terms(session, values)
    parameters = _add_missing_parameters(session, params)
    added = add_regulatory_limits(session, limits)
    print(
        f"  added {terms} lexicon terms, {parameters} parameters, "
        f"{added} regulatory limits"
    )


MIGRATION = DataMigration(
    id="20260916_0001_seed_epa_regulatory_limits",
    alembic_revision="66ac1af4ba69",
    name="Seed EPA regulatory limits",
    description=(
        "Loads the EPA MCLs and SMCLs from core/regulatory_limit.json, adding "
        "the groundwater parameters and lexicon terms they depend on. Deploys "
        "run no seed, so regulatory_limit is otherwise empty."
    ),
    run=run,
    is_repeatable=False,
)


# ============= EOF =============================================
