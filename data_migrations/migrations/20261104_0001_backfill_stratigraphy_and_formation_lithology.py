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
Backfill the stratigraphy intervals and formation lithology that the
2026-02-27 transfer left out, so ``NGWMN_Lithology`` has data (BDMS-1551).

The stratigraphy transfer ran with a well limit (``TRANSFER_LIMIT // 10`` =
1000 wells, in PointID order) and stopped there. ``NMA_Stratigraphy`` holds
every legacy interval (4,265 on staging), but only the first 1,000 wells became
``thing_geologic_formation_association`` rows (993 on staging). Formation
lithology is set as a side effect of that transfer, so it reached only two
formations: ``110ALVM`` (Gravel) and ``120SRVB`` (Basalt). The view joins on
``geologic_formation.lithology IS NOT NULL``, so those were the only two
values it could show.

This migration reads ``NMA_Stratigraphy`` and:

* Inserts an association for every legacy interval the transfer would have
  accepted and that is not there yet. The transfer's rules are kept: the
  ``UnitIdentifier`` must match an existing ``geologic_formation``, the top
  must not be negative, and the top must be above the bottom unless both are
  zero. An interval counts as present when the same well, formation, top and
  bottom already exist, so the rows from the partial transfer are left alone.
* Sets ``geologic_formation.lithology`` on formations that have none, to the
  formation's most common legacy lithology code (ties broken by term name).
  A lithology already set is not overwritten.

Lithology is still one value per formation. Eight formations carry more than
one legacy code (``211DKOT`` is mostly Sandstone but also Sandstone and
shale), and every interval in them reports the majority value. Storing
lithology per interval needs a schema change and is tracked separately.

Codes are matched case-insensitively, because the legacy data has ``Sand`` and
``Coal`` next to ``SAND``/``COAL`` in ``LU_Lithology``. ``LU_LITHOLOGY`` is a
copy of ``LU_Lithology`` (ABBREVIATION -> TERM); the CSV only exists in the
transfer bucket, not in the database. A term not in ``lexicon_term`` is
skipped, because ``geologic_formation.lithology`` is a foreign key to it.

``GeologicFormation`` is SQLAlchemy-Continuum versioned, so lithology is set by
attribute assignment to get ``geologic_formation_version`` rows. Associations
are not versioned and are bulk-inserted. New associations take the model
default release status, matching the transferred ones; the view is gated on the
well's release status.

Safe to re-run: a second run finds nothing missing and changes nothing.
"""

from collections import Counter, defaultdict

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.geologic_formation import GeologicFormation
from db.lexicon import LexiconTerm
from db.nma_legacy import NMA_Stratigraphy
from db.thing_geologic_formation_association import (
    ThingGeologicFormationAssociation,
)

LU_LITHOLOGY = {
    "ALVM": "Alluvium",
    "ANDR": "Anhydrite",
    "ANDS": "Andesite",
    "ARKS": "Arkose",
    "BLDR": "Boulders",
    "BLSC": "Boulders, silt and clay",
    "BLSD": "Boulders and sand",
    "BNTN": "Bentonite",
    "BRCC": "Breccia",
    "BSLT": "Basalt",
    "CGLM": "Conglomerate",
    "CHLK": "Chalk",
    "CHRT": "Chert",
    "CLAY": "Clay",
    "CLCH": "Caliche",
    "CLCT": "Calcite",
    "CLRD": "Clay, red",
    "CLSD": "Clay, some sand",
    "CLSN": "Claystone",
    "CLYE": "Clay, yellow",
    "COAL": "Coal",
    "COBB": "Cobbles",
    "COSC": "Cobbles, silt and clay",
    "COSD": "Cobbles and sand",
    "DLMT": "Dolomite",
    "DLSH": "Dolomite and shale",
    "EVPR": "Evaporite",
    "GNSS": "Gneiss",
    "GPSM": "Gypsum",
    "GRBL": "Gravel and boulders",
    "GRCK": "Graywacke",
    "GRCL": "Gravel and clay",
    "GRCM": "Gravel, cemented",
    "GRDS": "Gravel, sand and silt",
    "GRGN": "Granite, gneiss",
    "GRNT": "Granite",
    "GRSC": "Gravel, silt and clay",
    "GRVL": "Gravel",
    "IGIN": "Ignesous, intrusive, undifferentiated",
    "IGNS": "Igneous undifferentiated",
    "LGNT": "Lignite",
    "LMDM": "Limestone and dolomite",
    "LMSD": "Limestone and sandstone, interbedded",
    "LMSH": "Limestone and shale",
    "LMSN": "Limestone",
    "LMSS": "Limestone, sandstone and shale",
    "MARL": "Marl",
    "MDSN": "Mudstone",
    "MMPC": "Metamorphic undifferentiated",
    "MRLS": "Marlstone",
    "NR": "No Recovery",
    "PEAT": "Peat",
    "QRTZ": "Quartzite",
    "RYLT": "Rhyolite",
    "SAND": "Sand",
    "SCST": "Schist",
    "SDCL": "Sand and clay",
    "SDCS": "Sand, silt and clay",
    "SDGL": "Sand and gravel",
    "SDSL": "Sandstone and shale",
    "SDST": "Sand and silt",
    "SGSC": "Sand, gravel, silt and clay",
    "SGVC": "Sand, gravel and clay",
    "SHLE": "Shale",
    "SILT": "Silt",
    "SLSH": "Siltstone and shale",
    "SLSN": "Siltstone",
    "SLTE": "Slate",
    "SNCL": "Sand, some clay",
    "SNDS": "Sandstone",
    "SSTG": "Sand, silt and gravel",
    "STCL": "Silt and clay",
    "SUSE": "Surficial sediment",
    "TRVR": "Travertine",
    "TUFF": "Tuff",
    "VLCC": "Volcanic undifferentiated",
}


def _accepted(top, bottom) -> bool:
    """The stratigraphy transfer's depth checks."""
    if top < 0:
        return False
    if (top or bottom) and top >= bottom:
        return False
    return True


def _plan(session: Session) -> dict:
    """Work out what is missing without writing anything."""
    formations = {
        f.formation_code: f for f in session.scalars(select(GeologicFormation))
    }
    lexicon = set(session.scalars(select(LexiconTerm.term)))

    existing = set(
        session.execute(
            select(
                ThingGeologicFormationAssociation.thing_id,
                ThingGeologicFormationAssociation.geologic_formation_id,
                ThingGeologicFormationAssociation.top_depth,
                ThingGeologicFormationAssociation.bottom_depth,
            )
        ).all()
    )

    legacy = session.execute(
        select(
            NMA_Stratigraphy.thing_id,
            NMA_Stratigraphy.unit_identifier,
            NMA_Stratigraphy.strat_top,
            NMA_Stratigraphy.strat_bottom,
            NMA_Stratigraphy.lithology,
        ).order_by(NMA_Stratigraphy.id)
    ).all()

    new_rows = []
    seen = set(existing)
    codes = defaultdict(Counter)
    unmapped = Counter()
    for thing_id, unit, top, bottom, code in legacy:
        formation = formations.get((unit or "").strip())
        if formation is None:
            continue

        if code and code.strip():
            term = LU_LITHOLOGY.get(code.strip().upper())
            if term and term in lexicon:
                codes[formation.formation_code][term] += 1
            else:
                unmapped[code] += 1

        if not _accepted(top, bottom):
            continue
        key = (thing_id, formation.id, float(top), float(bottom))
        if key in seen:
            continue
        seen.add(key)
        new_rows.append(
            {
                "thing_id": thing_id,
                "geologic_formation_id": formation.id,
                "top_depth": float(top),
                "bottom_depth": float(bottom),
            }
        )

    lithology = {}
    for formation_code, counts in sorted(codes.items()):
        if formations[formation_code].lithology:
            continue
        # Most common term; ties go to the alphabetically first term.
        term = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        lithology[formation_code] = term

    return {
        "formations": formations,
        "new_associations": new_rows,
        "lithology": lithology,
        "unmapped_codes": dict(unmapped),
    }


def dry_run(session: Session) -> dict:
    plan = _plan(session)
    print(f"  {len(plan['new_associations'])} associations would be inserted")
    for code, term in plan["lithology"].items():
        print(f"  {code}: lithology would be set to {term!r}")
    if plan["unmapped_codes"]:
        print(f"  unmapped lithology codes: {plan['unmapped_codes']}")
    return {
        "new_associations": len(plan["new_associations"]),
        "lithology": plan["lithology"],
        "unmapped_codes": plan["unmapped_codes"],
    }


def run(session: Session) -> None:
    plan = _plan(session)

    rows = plan["new_associations"]
    if rows:
        session.execute(insert(ThingGeologicFormationAssociation), rows)
    print(f"  inserted {len(rows)} stratigraphy associations")

    for formation_code, term in plan["lithology"].items():
        plan["formations"][formation_code].lithology = term
    session.flush()
    print(f"  set lithology on {len(plan['lithology'])} formations")

    if plan["unmapped_codes"]:
        print(f"  skipped unmapped lithology codes: {plan['unmapped_codes']}")
    return None


MIGRATION = DataMigration(
    id="20261104_0001_backfill_stratigraphy_and_formation_lithology",
    alembic_revision="a3b4c5d6e7f8",
    name="Backfill stratigraphy intervals and formation lithology",
    description=(
        "The stratigraphy transfer stopped at a 1000-well limit, so most "
        "NMA_Stratigraphy intervals never became formation associations and "
        "only two formations got a lithology. NGWMN_Lithology showed only "
        "Gravel and Basalt (BDMS-1551). Inserts the missing intervals and sets "
        "each formation's lithology to its most common legacy code."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
