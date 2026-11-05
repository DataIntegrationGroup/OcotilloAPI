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
Backfill the legacy stratigraphy intervals and give each one its own
lithology, so ``NGWMN_Lithology`` matches the legacy view (BDMS-1551,
BDMS-1554).

Two gaps, fixed together because the second needs the first:

1. **Missing intervals (BDMS-1551).** The 2026-02-27 stratigraphy transfer ran
   with a well limit (``TRANSFER_LIMIT // 10`` = 1000 wells, in PointID order)
   and stopped there. ``NMA_Stratigraphy`` holds every legacy interval (4,265
   on staging), but only the first 1,000 wells became
   ``thing_geologic_formation_association`` rows (993 on staging).
2. **One lithology per formation (BDMS-1554).** ``NGWMN_Lithology`` read
   ``geologic_formation.lithology``, which the transfer set from the first code
   it saw and only reached ``110ALVM`` (Gravel) and ``120SRVB`` (Basalt). The
   legacy view joined each ``Stratigraphy`` row to ``LU_Lithology``, so every
   interval had its own lithology. Eight formations carry more than one legacy
   code (``211DKOT`` is mostly SNDS but also SDSL). Revision ``7480e4ee69dc``
   adds ``thing_geologic_formation_association.lithology`` for this.

This migration reads ``NMA_Stratigraphy`` in legacy id order and, per interval:

* Resolves the formation from ``UnitIdentifier`` (trimmed) and the lithology
  term from ``Lithology`` through ``LU_LITHOLOGY`` (case-insensitive: the
  legacy data has ``Sand`` and ``Coal`` next to ``SAND``/``COAL``). A term not
  in ``lexicon_term`` is treated as unmapped, because the column is a foreign
  key to it.
* Applies the transfer's depth rules: the top must not be negative, and the
  top must be above the bottom unless both are zero.
* If the same well, formation, top and bottom already exist, fills that row's
  lithology when it is null. A lithology already set (by a user, or an earlier
  run) is never overwritten. Otherwise inserts the interval with its
  lithology.
* Intervals whose ``UnitIdentifier`` is blank or names no known formation are
  inserted with a null ``geologic_formation_id`` **only if they have a mapped
  lithology** (for example the AH- wells coded BSLT). They were in the legacy
  view; without a lithology there is nothing to export, so they are skipped,
  as the transfer skipped them.
* A legacy interval repeating an earlier one's well, formation, top and bottom
  is skipped; the first one (lowest legacy id) wins.

``geologic_formation.lithology`` is left as it is. BDMS-1551 proposed setting
an empty one to the formation's most common legacy code; with per-interval
lithology that is no longer needed for coded intervals, and it would make the
view's fallback report a guessed lithology for every uncoded interval in a
mixed formation.

Associations are not versioned and are written in bulk. New rows take the
model default release status, matching the transferred ones; the view is
gated on the well's release status.

Safe to re-run: a second run finds nothing missing and changes nothing.
"""

from collections import Counter

from sqlalchemy import insert, select, update
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


def _term(code: str | None, lexicon: set[str]) -> str | None:
    if not code or not code.strip():
        return None
    term = LU_LITHOLOGY.get(code.strip().upper())
    return term if term in lexicon else None


def _plan(session: Session) -> dict:
    """Work out what is missing without writing anything."""
    formations = {
        f.formation_code: f.id for f in session.scalars(select(GeologicFormation))
    }
    lexicon = set(session.scalars(select(LexiconTerm.term)))

    # (thing, formation, top, bottom) -> (association id, lithology). If the
    # partial transfer wrote a key twice, the lowest id is the one filled.
    existing = {}
    for row in session.execute(
        select(
            ThingGeologicFormationAssociation.id,
            ThingGeologicFormationAssociation.thing_id,
            ThingGeologicFormationAssociation.geologic_formation_id,
            ThingGeologicFormationAssociation.top_depth,
            ThingGeologicFormationAssociation.bottom_depth,
            ThingGeologicFormationAssociation.lithology,
        ).order_by(ThingGeologicFormationAssociation.id)
    ):
        key = (row.thing_id, row.geologic_formation_id, row.top_depth, row.bottom_depth)
        existing.setdefault(key, (row.id, row.lithology))

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
    updates = []
    seen = set()
    unmapped = Counter()
    stats = Counter()
    for thing_id, unit, top, bottom, code in legacy:
        formation_id = formations.get((unit or "").strip())
        term = _term(code, lexicon)
        if code and code.strip() and term is None:
            unmapped[code] += 1

        if not _accepted(top, bottom):
            stats["skipped_depths"] += 1
            continue
        if formation_id is None and term is None:
            stats["skipped_no_formation_or_lithology"] += 1
            continue

        key = (thing_id, formation_id, float(top), float(bottom))
        if key in seen:
            stats["skipped_duplicate"] += 1
            continue
        seen.add(key)

        if key in existing:
            association_id, current = existing[key]
            if current is None and term is not None:
                updates.append({"id": association_id, "lithology": term})
            elif current is not None and term is not None and current != term:
                stats["kept_existing_lithology"] += 1
            continue

        new_rows.append(
            {
                "thing_id": thing_id,
                "geologic_formation_id": formation_id,
                "top_depth": float(top),
                "bottom_depth": float(bottom),
                "lithology": term,
            }
        )
        if formation_id is None:
            stats["new_without_formation"] += 1

    return {
        "new_associations": new_rows,
        "lithology_updates": updates,
        "unmapped_codes": dict(unmapped),
        "stats": dict(stats),
    }


def _summary(plan: dict) -> dict:
    return {
        "new_associations": len(plan["new_associations"]),
        "lithology_updates": len(plan["lithology_updates"]),
        "unmapped_codes": plan["unmapped_codes"],
        "stats": plan["stats"],
    }


def dry_run(session: Session) -> dict:
    summary = _summary(_plan(session))
    print(f"  {summary['new_associations']} associations would be inserted")
    print(f"  {summary['lithology_updates']} interval lithologies would be set")
    for name, count in sorted(summary["stats"].items()):
        print(f"  {name}: {count}")
    if summary["unmapped_codes"]:
        print(f"  unmapped lithology codes: {summary['unmapped_codes']}")
    return summary


def run(session: Session) -> None:
    plan = _plan(session)

    rows = plan["new_associations"]
    if rows:
        session.execute(insert(ThingGeologicFormationAssociation), rows)
    print(f"  inserted {len(rows)} stratigraphy associations")

    updates = plan["lithology_updates"]
    if updates:
        session.execute(update(ThingGeologicFormationAssociation), updates)
    print(f"  set lithology on {len(updates)} existing associations")

    for name, count in sorted(plan["stats"].items()):
        print(f"  {name}: {count}")
    if plan["unmapped_codes"]:
        print(f"  skipped unmapped lithology codes: {plan['unmapped_codes']}")
    return None


MIGRATION = DataMigration(
    id="20261105_0001_backfill_stratigraphy_interval_lithology",
    alembic_revision="7480e4ee69dc",
    name="Backfill stratigraphy intervals with per-interval lithology",
    description=(
        "The stratigraphy transfer stopped at a 1000-well limit (BDMS-1551) and "
        "lithology was stored once per formation (BDMS-1554), so "
        "NGWMN_Lithology was missing intervals and reported the wrong rock "
        "type for many. Inserts the missing NMA_Stratigraphy intervals and "
        "sets each interval's lithology from its legacy LU_Lithology code."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
