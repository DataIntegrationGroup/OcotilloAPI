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
Backfill ``stratigraphic_interval`` from the legacy ``NMA_Stratigraphy`` table,
so a well's stratigraphic log and ``NGWMN_Lithology`` match the legacy data
(BDMS-1551, BDMS-1554).

Two gaps, fixed together:

1. **Missing intervals (BDMS-1551).** The 2026-02-27 stratigraphy transfer ran
   with a well limit (``TRANSFER_LIMIT // 10`` = 1000 wells, in PointID order)
   and stopped there. ``NMA_Stratigraphy`` holds every legacy interval (4,265
   on staging), but only 993 became intervals.
2. **Interval fields (BDMS-1554).** The transfer kept only depths and
   formation. Revision ``7480e4ee69dc`` renamed the table to
   ``stratigraphic_interval`` and added the rest of the legacy row: lithology,
   lithologic modifier, contributing unit and source. ``NGWMN_Lithology``
   now reads lithology per interval instead of once per formation.

This migration walks ``NMA_Stratigraphy`` in legacy id order. For each row:

* **Depths.** The transfer's rules apply: the top must not be negative, and
  the top must be above the bottom unless both are zero. Rows that fail are
  skipped and counted.
* **Already migrated.** A row whose ``GlobalID`` is already on an interval's
  ``nma_pk_stratigraphy`` is skipped. That makes a re-run a no-op.
* **Adopted.** Otherwise, if an interval with the same well, formation, top
  and bottom exists and has no ``nma_pk_stratigraphy`` (the 993 transferred
  rows), the legacy row adopts it: its empty fields are filled and its
  ``nma_pk_stratigraphy`` is set. Values already present are never overwritten.
  Each existing interval is adopted at most once, so legacy duplicates of one
  interval become separate rows, as they were in the legacy view.
* **Inserted.** Otherwise a new interval is inserted.

Field mapping:

* ``UnitIdentifier`` (trimmed) -> ``geologic_formation_id`` when it names a
  ``geologic_formation``; otherwise null. Unknown codes are reported.
* ``Lithology`` -> ``lithology`` through ``LU_LITHOLOGY`` (case-insensitive:
  the legacy data has ``Sand`` and ``Coal`` next to ``SAND``/``COAL``). A code
  not in the table, or whose term is not in ``lexicon_term``, is reported and
  left null.
* ``LithologicModifier`` -> ``lithologic_modifier``; ``StratSource`` ->
  ``source`` (blank becomes null).
* ``ContributingUnit`` -> ``contributing_unit``: Y/YES/T/TRUE/1 is true,
  N/NO/F/FALSE/0 is false. Anything else is reported and left null.
* ``StratNotes`` -> a ``General`` note on the interval, unless the interval
  already has a note with the same text.

``geologic_formation.lithology`` is left as it is; the view falls back to it
only for intervals without their own lithology. ``NMA_Stratigraphy`` is not
changed and stays the record of the original values.

New intervals take the model default release status, matching the transferred
ones; the view is gated on the well's release status.
"""

from collections import Counter, defaultdict, deque

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.geologic_formation import GeologicFormation
from db.lexicon import LexiconTerm
from db.nma_legacy import NMA_Stratigraphy
from db.notes import Notes
from db.stratigraphic_interval import StratigraphicInterval

TARGET_TABLE = StratigraphicInterval.__tablename__
NOTE_TYPE = "General"
TRUE_VALUES = {"Y", "YES", "T", "TRUE", "1"}
FALSE_VALUES = {"N", "NO", "F", "FALSE", "0"}
# Interval fields filled from the legacy row; adoption fills only empty ones.
FILLED_FIELDS = (
    "lithology",
    "lithologic_modifier",
    "contributing_unit",
    "source",
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


def _text(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _plan(session: Session) -> dict:
    """Work out every change without writing anything."""
    formations = {
        f.formation_code: f.id for f in session.scalars(select(GeologicFormation))
    }
    lexicon = set(session.scalars(select(LexiconTerm.term)))

    migrated = set()
    # (thing, formation, top, bottom) -> unclaimed intervals, lowest id first.
    pool = defaultdict(deque)
    for row in session.execute(
        select(
            StratigraphicInterval.id,
            StratigraphicInterval.thing_id,
            StratigraphicInterval.geologic_formation_id,
            StratigraphicInterval.top_depth,
            StratigraphicInterval.bottom_depth,
            StratigraphicInterval.nma_pk_stratigraphy,
            *(getattr(StratigraphicInterval, f) for f in FILLED_FIELDS),
        ).order_by(StratigraphicInterval.id)
    ).mappings():
        if row["nma_pk_stratigraphy"]:
            migrated.add(row["nma_pk_stratigraphy"])
            continue
        key = (
            row["thing_id"],
            row["geologic_formation_id"],
            row["top_depth"],
            row["bottom_depth"],
        )
        pool[key].append(row)

    legacy = session.scalars(
        select(NMA_Stratigraphy).order_by(NMA_Stratigraphy.id)
    ).all()

    inserts, updates, notes = [], [], []
    stats = Counter()
    unmapped_lithology = Counter()
    unmapped_contributing = Counter()
    unknown_units = Counter()
    for strat in legacy:
        if not _accepted(strat.strat_top, strat.strat_bottom):
            stats["skipped_depths"] += 1
            continue
        pk = str(strat.nma_global_id) if strat.nma_global_id else None
        if pk and pk in migrated:
            stats["already_migrated"] += 1
            continue

        unit = _text(strat.unit_identifier)
        formation_id = formations.get(unit) if unit else None
        if unit and formation_id is None:
            unknown_units[unit] += 1

        code = _text(strat.lithology)
        lithology = LU_LITHOLOGY.get(code.upper()) if code else None
        if lithology not in lexicon:
            lithology = None
        if code and lithology is None:
            unmapped_lithology[code] += 1

        flag = _text(strat.contributing_unit)
        contributing = None
        if flag and flag.upper() in TRUE_VALUES:
            contributing = True
        elif flag and flag.upper() in FALSE_VALUES:
            contributing = False
        elif flag:
            unmapped_contributing[flag] += 1

        values = {
            "lithology": lithology,
            "lithologic_modifier": _text(strat.lithologic_modifier),
            "contributing_unit": contributing,
            "source": _text(strat.strat_source),
        }
        note = _text(strat.strat_notes)

        top, bottom = float(strat.strat_top), float(strat.strat_bottom)
        key = (strat.thing_id, formation_id, top, bottom)
        if pool[key]:
            row = pool[key].popleft()
            change = {
                field: value
                for field, value in values.items()
                if value is not None and row[field] is None
            }
            if pk:
                change["nma_pk_stratigraphy"] = pk
            if change:
                updates.append({"id": row["id"], **change})
            stats["adopted"] += 1
            if note:
                notes.append((row["id"], note))
        else:
            inserts.append(
                {
                    "thing_id": strat.thing_id,
                    "geologic_formation_id": formation_id,
                    "top_depth": top,
                    "bottom_depth": bottom,
                    "nma_pk_stratigraphy": pk,
                    **values,
                    "_note": note,
                }
            )
            if formation_id is None:
                stats["inserted_without_formation"] += 1
        if pk:
            migrated.add(pk)

    return {
        "inserts": inserts,
        "updates": updates,
        "notes": notes,
        "stats": dict(stats),
        "unmapped_lithology": dict(unmapped_lithology),
        "unmapped_contributing_unit": dict(unmapped_contributing),
        "unknown_units": dict(unknown_units),
    }


def _summary(plan: dict) -> dict:
    return {
        "inserted": len(plan["inserts"]),
        "updated": len(plan["updates"]),
        "notes": len(plan["notes"]) + sum(1 for r in plan["inserts"] if r["_note"]),
        "stats": plan["stats"],
        "unmapped_lithology": plan["unmapped_lithology"],
        "unmapped_contributing_unit": plan["unmapped_contributing_unit"],
        "unknown_units": plan["unknown_units"],
    }


def _report(summary: dict, verb: str) -> None:
    print(f"  {summary['inserted']} intervals {verb} inserted")
    print(f"  {summary['updated']} existing intervals {verb} updated")
    print(f"  up to {summary['notes']} notes {verb} added")
    for name, count in sorted(summary["stats"].items()):
        print(f"  {name}: {count}")
    for name in ("unmapped_lithology", "unmapped_contributing_unit", "unknown_units"):
        if summary[name]:
            print(f"  {name}: {summary[name]}")


def dry_run(session: Session) -> dict:
    summary = _summary(_plan(session))
    _report(summary, "would be")
    return summary


def _add_notes(session: Session, notes: list[tuple[int, str]]) -> int:
    if not notes:
        return 0
    ids = {target_id for target_id, _ in notes}
    existing = set(
        session.execute(
            select(Notes.target_id, Notes.content).where(
                Notes.target_table == TARGET_TABLE,
                Notes.target_id.in_(ids),
            )
        ).all()
    )
    rows = []
    for target_id, content in notes:
        if (target_id, content) in existing:
            continue
        existing.add((target_id, content))
        rows.append(
            {
                "target_id": target_id,
                "target_table": TARGET_TABLE,
                "note_type": NOTE_TYPE,
                "content": content,
            }
        )
    if rows:
        session.execute(insert(Notes), rows)
    return len(rows)


def run(session: Session) -> None:
    plan = _plan(session)
    summary = _summary(plan)

    notes = list(plan["notes"])
    if plan["updates"]:
        session.execute(update(StratigraphicInterval), plan["updates"])
    if plan["inserts"]:
        rows = [{k: v for k, v in r.items() if k != "_note"} for r in plan["inserts"]]
        ids = session.scalars(
            insert(StratigraphicInterval).returning(
                StratigraphicInterval.id, sort_by_parameter_order=True
            ),
            rows,
        ).all()
        notes.extend(
            (new_id, r["_note"])
            for new_id, r in zip(ids, plan["inserts"])
            if r["_note"]
        )
    added = _add_notes(session, notes)
    session.flush()

    summary["notes"] = added
    _report(summary, "were")
    return None


MIGRATION = DataMigration(
    id="20261105_0001_backfill_stratigraphic_intervals",
    alembic_revision="7480e4ee69dc",
    name="Backfill stratigraphic intervals from NMA_Stratigraphy",
    description=(
        "The stratigraphy transfer stopped at a 1000-well limit (BDMS-1551) and "
        "kept only depths and formation (BDMS-1554). Inserts the missing "
        "NMA_Stratigraphy intervals and fills lithology, lithologic modifier, "
        "contributing unit, source and notes on every interval, so "
        "NGWMN_Lithology reports each interval's own lithology."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
