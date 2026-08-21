#!/usr/bin/env python3
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
"""Seed the test database with NMA legacy major/minor chemistry data.

Copies a small subset of real chemistry out of a local clone of another database
(by default the ``ocotillo_prod`` clone) into ``ocotilloapi_test``, so that
chemistry endpoints, the normalized-chemistry views and the LIMS ingestion code
have realistic analytes, units, censored ("<") symbols and detection limits to
read without a SQL Server connection.

Copied per selected ``NMA_Chemistry_SampleInfo``:

    thing (parent of the sample info; thing_id is NOT NULL)
      -> location + location_thing_association (the live thing->location link)
      -> NMA_Chemistry_SampleInfo
           -> NMA_MajorChemistry rows
           -> NMA_MinorTraceChemistry rows

Primary keys are *not* preserved. The target already holds unrelated rows at low
ids, so every row is inserted without its id and children are repointed at the
new parent id. Legacy uuid/OBJECTID columns are copied verbatim -- they are the
natural keys this script reconciles on, which is what makes re-runs idempotent:

    NMA_Chemistry_SampleInfo."nma_SamplePtID"  already present -> candidate skipped
    location.nma_pk_location / thing.nma_pk_welldata  already present -> reused

Lexicon-backed columns are validated against the target ``lexicon_term`` table.
Nullable ones are nulled out when the term is missing; ``thing.thing_type`` is
NOT NULL, so a thing whose type is absent from the target lexicon disqualifies
its sample infos instead.

The seed is transient. ``tests/conftest.py`` has a session-scoped autouse
fixture that drops and re-migrates the schema, so any ``pytest`` run wipes these
rows -- re-run this script afterwards.

Usage:
    python -m scripts.seed_nma_chemistry                    # 60 sample infos
    python -m scripts.seed_nma_chemistry --samples 200
    python -m scripts.seed_nma_chemistry --dry-run
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections import defaultdict
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

# Columns never copied: surrogate keys and the trigger-maintained search vector.
SKIP_COLUMNS = {"id", "search_vector"}

# Geometry columns are read as EWKT and re-parsed on insert; pg8000 has no
# geometry codec of its own.
GEOMETRY_COLUMNS = {("location", "point")}

# Columns whose value must exist in the target lexicon_term table.
LEXICON_COLUMNS = {
    "location": {"release_status", "nma_data_reliability"},
    "thing": {
        "thing_type",
        "release_status",
        "formation_completion_code",
        "spring_type",
        "well_construction_method",
        "well_pump_type",
    },
}

CHEMISTRY_TABLES = ("NMA_MajorChemistry", "NMA_MinorTraceChemistry")


def build_engine(database: str) -> Engine:
    """Engine for `database` on the host configured in .env.

    Deliberately does not import db.engine: that module binds one engine to
    POSTGRES_DB at import time, and this script needs two databases at once.
    """
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "").strip() or getpass.getuser()

    auth = f"{user}:{password}@" if user and password else ""
    port_part = f":{port}" if port else ""
    url = f"postgresql+pg8000://{auth}{host}{port_part}/{database}"
    return create_engine(url, future=True)


def copyable_columns(src: Connection, dst: Connection, table: str) -> list[str]:
    """Columns present in both databases and safe to insert explicitly."""
    sql = text(
        "select column_name from information_schema.columns "
        "where table_schema = 'public' and table_name = :t"
    )
    src_cols = {r[0] for r in src.execute(sql, {"t": table})}
    dst_cols = {r[0] for r in dst.execute(sql, {"t": table})}
    if not src_cols:
        raise SystemExit(f"Source database has no table {table!r}")
    if not dst_cols:
        raise SystemExit(f"Target database has no table {table!r}")

    missing = (src_cols - dst_cols) | (dst_cols - src_cols)
    if missing:
        print(f"  {table}: skipping columns absent on one side: {sorted(missing)}")

    return sorted((src_cols & dst_cols) - SKIP_COLUMNS)


def select_clause(table: str, columns: list[str]) -> str:
    parts = []
    for col in columns:
        if (table, col) in GEOMETRY_COLUMNS:
            parts.append(f'ST_AsEWKT("{col}") as "{col}"')
        else:
            parts.append(f'"{col}"')
    return ", ".join(parts)


def insert_returning_id(
    dst: Connection, table: str, columns: list[str], row: dict[str, Any]
) -> int:
    placeholders = []
    for col in columns:
        if (table, col) in GEOMETRY_COLUMNS:
            placeholders.append(f"ST_GeomFromEWKT(:{col})")
        else:
            placeholders.append(f":{col}")

    col_list = ", ".join(f'"{c}"' for c in columns)
    sql = text(
        f'insert into "{table}" ({col_list}) values ({", ".join(placeholders)}) '
        "returning id"
    )
    return dst.execute(sql, {c: row[c] for c in columns}).scalar_one()


def scrub_lexicon(
    table: str, row: dict[str, Any], terms: set[str], nulled: dict[str, int]
) -> None:
    """Null out nullable lexicon-backed values the target lexicon lacks."""
    for col in LEXICON_COLUMNS.get(table, ()):
        if col == "thing_type":  # NOT NULL; handled by candidate filtering
            continue
        value = row.get(col)
        if value is not None and value not in terms:
            row[col] = None
            nulled[f"{table}.{col}"] += 1


def load_lexicon_terms(dst: Connection) -> set[str]:
    return {r[0] for r in dst.execute(text("select term from lexicon_term"))}


def select_candidates(
    src: Connection, dst: Connection, limit: int, terms: set[str]
) -> list[dict[str, Any]]:
    """Sample infos worth copying, oldest id first for a stable subset.

    Requires both a major and a minor/trace row so the seed always exercises
    both tables, and a thing whose type the target lexicon already knows.
    """
    seeded = {
        r[0]
        for r in dst.execute(
            text(
                'select "nma_SamplePtID" from "NMA_Chemistry_SampleInfo" '
                'where "nma_SamplePtID" is not null'
            )
        )
    }

    rows = src.execute(
        text(
            """
            select si.id, si."nma_SamplePtID", si.thing_id, t.thing_type
            from "NMA_Chemistry_SampleInfo" si
            join thing t on t.id = si.thing_id
            where si."nma_SamplePtID" is not null
              and exists (select 1 from "NMA_MajorChemistry" mc
                          where mc.chemistry_sample_info_id = si.id)
              and exists (select 1 from "NMA_MinorTraceChemistry" mt
                          where mt.chemistry_sample_info_id = si.id)
            order by si.id
            """
        )
    ).mappings()

    candidates = []
    skipped_seeded = 0
    skipped_type = 0
    for row in rows:
        if row["nma_SamplePtID"] in seeded:
            skipped_seeded += 1
            continue
        if row["thing_type"] not in terms:
            skipped_type += 1
            continue
        candidates.append(dict(row))
        if len(candidates) >= limit:
            break

    if skipped_seeded:
        print(f"  {skipped_seeded} sample info(s) already seeded, skipped")
    if skipped_type:
        print(
            f"  {skipped_type} sample info(s) skipped: thing_type not in target lexicon"
        )
    return candidates


def copy_location(
    src: Connection,
    dst: Connection,
    columns: list[str],
    source_location_id: int,
    location_map: dict[int, int],
    terms: set[str],
    nulled: dict[str, int],
) -> int | None:
    """Copy one source location, reusing a target row when already present."""
    if source_location_id in location_map:
        return location_map[source_location_id]

    row = (
        src.execute(
            text(
                f"select {select_clause('location', columns)} from location "
                "where id = :i"
            ),
            {"i": source_location_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    row = dict(row)

    legacy_key = row.get("nma_pk_location")
    if legacy_key is not None:
        existing = dst.execute(
            text("select id from location where nma_pk_location = :k limit 1"),
            {"k": legacy_key},
        ).scalar()
        if existing is not None:
            location_map[source_location_id] = existing
            return existing

    scrub_lexicon("location", row, terms, nulled)
    target_id = insert_returning_id(dst, "location", columns, row)
    location_map[source_location_id] = target_id
    return target_id


def copy_location_associations(
    src: Connection,
    dst: Connection,
    column_sets: dict[str, list[str]],
    source_thing_id: int,
    target_thing_id: int,
    location_map: dict[int, int],
    terms: set[str],
    nulled: dict[str, int],
) -> tuple[int, int]:
    """Copy a thing's locations and the association rows that link them.

    thing.nma_pk_location is a legacy audit column; the live model reaches a
    location through location_thing_association (Thing.location_associations),
    so a seeded thing without association rows reads as a well with no location.
    """
    assoc_columns = column_sets["location_thing_association"]
    rows = (
        src.execute(
            text(
                f"select {select_clause('location_thing_association', assoc_columns)} "
                "from location_thing_association where thing_id = :i order by id"
            ),
            {"i": source_thing_id},
        )
        .mappings()
        .all()
    )

    locations = 0
    associations = 0
    for row in rows:
        payload = dict(row)
        source_location_id = payload["location_id"]
        before = len(location_map)
        target_location_id = copy_location(
            src,
            dst,
            column_sets["location"],
            source_location_id,
            location_map,
            terms,
            nulled,
        )
        if target_location_id is None:
            continue
        if len(location_map) > before:
            locations += 1

        payload["location_id"] = target_location_id
        payload["thing_id"] = target_thing_id
        insert_returning_id(dst, "location_thing_association", assoc_columns, payload)
        associations += 1

    return locations, associations


def copy_thing(
    src: Connection,
    dst: Connection,
    columns: list[str],
    thing_id: int,
    terms: set[str],
    nulled: dict[str, int],
) -> tuple[int, bool]:
    """Return (target thing id, created) for a source thing id."""
    row = (
        src.execute(
            text(f"select {select_clause('thing', columns)} from thing where id = :i"),
            {"i": thing_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise SystemExit(f"Source thing {thing_id} vanished mid-run")
    row = dict(row)

    legacy_key = row.get("nma_pk_welldata")
    if legacy_key is not None:
        existing = dst.execute(
            text("select id from thing where nma_pk_welldata = :k limit 1"),
            {"k": legacy_key},
        ).scalar()
        if existing is not None:
            return existing, False

    scrub_lexicon("thing", row, terms, nulled)
    return insert_returning_id(dst, "thing", columns, row), True


def copy_chemistry(
    src: Connection,
    dst: Connection,
    table: str,
    columns: list[str],
    source_sample_info_id: int,
    target_sample_info_id: int,
) -> int:
    rows = (
        src.execute(
            text(
                f'select {select_clause(table, columns)} from "{table}" '
                "where chemistry_sample_info_id = :i order by id"
            ),
            {"i": source_sample_info_id},
        )
        .mappings()
        .all()
    )

    count = 0
    for row in rows:
        payload = dict(row)
        payload["chemistry_sample_info_id"] = target_sample_info_id
        insert_returning_id(dst, table, columns, payload)
        count += 1
    return count


def seed(source_db: str, target_db: str, samples: int, dry_run: bool) -> int:
    source_engine = build_engine(source_db)
    target_engine = build_engine(target_db)

    nulled: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)

    with source_engine.connect() as src, target_engine.begin() as dst:
        print(f"Reading {source_db!r}, writing {target_db!r}")

        column_sets = {
            table: copyable_columns(src, dst, table)
            for table in (
                "location",
                "thing",
                "location_thing_association",
                "NMA_Chemistry_SampleInfo",
                *CHEMISTRY_TABLES,
            )
        }
        terms = load_lexicon_terms(dst)

        candidates = select_candidates(src, dst, samples, terms)
        if not candidates:
            print("Nothing to seed: no unseeded sample infos matched.")
            return 0
        print(f"Selected {len(candidates)} sample info(s) to copy")

        if dry_run:
            for candidate in candidates[:10]:
                print(
                    f"  would copy sample_info id={candidate['id']} "
                    f"thing_id={candidate['thing_id']}"
                )
            if len(candidates) > 10:
                print(f"  ... and {len(candidates) - 10} more")
            dst.rollback()
            return 0

        thing_map: dict[int, int] = {}
        location_map: dict[int, int] = {}
        for candidate in candidates:
            source_thing_id = candidate["thing_id"]
            if source_thing_id not in thing_map:
                target_thing_id, created = copy_thing(
                    src, dst, column_sets["thing"], source_thing_id, terms, nulled
                )
                thing_map[source_thing_id] = target_thing_id
                if created:
                    totals["thing"] += 1

                if created:
                    locations, associations = copy_location_associations(
                        src,
                        dst,
                        column_sets,
                        source_thing_id,
                        target_thing_id,
                        location_map,
                        terms,
                        nulled,
                    )
                    totals["location"] += locations
                    totals["location_thing_association"] += associations

            info_columns = column_sets["NMA_Chemistry_SampleInfo"]
            info_row = (
                src.execute(
                    text(
                        f"select {select_clause('NMA_Chemistry_SampleInfo', info_columns)} "
                        'from "NMA_Chemistry_SampleInfo" where id = :i'
                    ),
                    {"i": candidate["id"]},
                )
                .mappings()
                .first()
            )
            payload = dict(info_row)
            payload["thing_id"] = thing_map[source_thing_id]

            target_info_id = insert_returning_id(
                dst, "NMA_Chemistry_SampleInfo", info_columns, payload
            )
            totals["NMA_Chemistry_SampleInfo"] += 1

            for table in CHEMISTRY_TABLES:
                totals[table] += copy_chemistry(
                    src,
                    dst,
                    table,
                    column_sets[table],
                    candidate["id"],
                    target_info_id,
                )

    print("\nSeeded:")
    for table in (
        "location",
        "thing",
        "location_thing_association",
        "NMA_Chemistry_SampleInfo",
        *CHEMISTRY_TABLES,
    ):
        print(f"  {table}: {totals[table]}")
    if nulled:
        print("\nNulled lexicon-backed values missing from the target lexicon:")
        for key, count in sorted(nulled.items()):
            print(f"  {key}: {count}")
    return 0


def main() -> int:
    load_dotenv(override=False)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-db",
        default="ocotillo_prod",
        help="database to read from (default: ocotillo_prod)",
    )
    parser.add_argument(
        "--target-db",
        default="ocotilloapi_test",
        help="database to write to (default: ocotilloapi_test)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=60,
        help="number of sample infos to copy (default: 60)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be copied, write nothing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow a target database whose name lacks 'test'",
    )
    args = parser.parse_args()

    if "test" not in args.target_db and not args.force:
        parser.error(
            f"refusing to write to {args.target_db!r}: name does not contain "
            "'test'. Pass --force if this is really intended."
        )
    if args.source_db == args.target_db:
        parser.error("--source-db and --target-db must differ")

    return seed(args.source_db, args.target_db, args.samples, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
