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
A dlt raw zone for the `oco` ingest commands.

The file and spreadsheet ingests read a source that keeps changing underneath
them -- a Google Sheet the field crew edits weekly, a workbook that gets
corrected and re-sent. Until now nothing recorded what the source said on the
day it was ingested, so "why does this sample say 7.39?" had no answer and a
mapping bug meant asking someone to re-export a file that had since moved on.

Each run therefore archives what it read before it maps anything, and then maps
**from the archive**. What gets loaded is provably what was kept. A mapping fix
is then a replay against a stored snapshot rather than a re-fetch:

    oco water-chemistry sync-sheet                 # extract -> archive -> load
    oco water-chemistry sync-sheet --replay <id>   # load again from the archive

This is dlt used for the half of ingestion dlt is actually good at -- extract,
partitioned parquet, atomic load packages, one identity story for GCS -- and
nothing more. Mapping, validation and the writes into Ocotillo's schema stay in
the service layer, because the destination is an FK-heavy relational model owned
by alembic, not a warehouse for dlt to evolve.

Row shape
---------
Each row is archived as ``{tab, row_number, cells_json}`` rather than as one
column per spreadsheet column. Spreadsheet headings change constantly -- a tab
gains "DO (mg/L)" one week -- and letting each of those become a raw-zone column
turns an ordinary edit into a schema migration in the archive. A JSON payload
keeps the headings exactly as they were typed, which is the point of an archive,
and the mapping layer is what gives them meaning.

Location
--------
``INGESTION_GCS_BUCKET`` (the same raw-zone bucket the Dagster+ ingestion uses,
never the API's upload bucket) or ``OCO_RAW_ZONE_DIR`` for a local directory.
Neither is defaulted: a run that reports success while writing nowhere useful is
worse than one that refuses to start.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

from services.chemistry_field_sheet import SheetTable

BUCKET_ENV_VAR = "INGESTION_GCS_BUCKET"
"""Raw-zone bucket. Deliberately not ``GCS_BUCKET_NAME`` -- that is the API's
user-upload bucket, and source payloads must not land there."""

LOCAL_DIR_ENV_VAR = "OCO_RAW_ZONE_DIR"
"""Local raw zone, for an engineer working without the bucket."""

RAW_PREFIX = "oco-raw"
"""Where CLI-run archives live inside the bucket, apart from the scheduled
pipelines' datasets."""

RAW_LAYOUT = "{table_name}/year={YYYY}/month={MM}/day={DD}/{load_id}.{file_id}.{ext}"
"""Mirrors the Dagster+ ingestion layout: the date is in the path, so a snapshot
can be found without reading the files."""

LOADER_FILE_FORMAT = "parquet"

_LOAD_FILE_RE = re.compile(r"(?P<load_id>[^/]+)\.(?P<file_id>[^/.]+)\.parquet$")


class RawZoneError(Exception):
    """The raw zone is not configured, or holds no such snapshot."""


@dataclass(frozen=True)
class RawExtract:
    """What one archived run wrote."""

    load_id: str
    url: str
    dataset: str
    row_counts: dict[str, int] = field(default_factory=dict)

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())


def _bucket_name(value: str) -> str:
    """The bucket out of a name or a ``gs://bucket/prefix`` URL."""
    return value.strip().removeprefix("gs://").strip("/").split("/", 1)[0]


def _reject_uploads_bucket(value: str, *, source: str) -> None:
    """Refuse a raw zone pointing at the API's user-upload bucket.

    Applies to every way a bucket can be named -- the environment variable and
    an explicit ``--raw-url`` alike. A guard that only covers the default is not
    a guard: the flag is exactly what someone reaches for when the default is
    not what they want.
    """
    uploads = os.environ.get("GCS_BUCKET_NAME", "").strip()
    if uploads and _bucket_name(value) == _bucket_name(uploads):
        raise RawZoneError(
            f"{source} points at GCS_BUCKET_NAME, the API's user-upload "
            "bucket. Source payloads must not be written there."
        )


def raw_zone_url(explicit: str | None = None) -> str:
    """Where archives are written, as an fsspec URL.

    Raises rather than guessing. ``explicit`` (a ``--raw-url``) wins, then the
    bucket, then a local directory.
    """
    if explicit:
        explicit = explicit.rstrip("/")
        if explicit.startswith("gs://"):
            _reject_uploads_bucket(explicit, source="--raw-url")
        return explicit

    bucket = os.environ.get(BUCKET_ENV_VAR, "").strip()
    if bucket:
        _reject_uploads_bucket(bucket, source=BUCKET_ENV_VAR)
        bucket = _bucket_name(bucket)
        return f"gs://{bucket}/{RAW_PREFIX}"

    local = os.environ.get(LOCAL_DIR_ENV_VAR, "").strip()
    if local:
        return Path(local).expanduser().resolve().as_uri()

    raise RawZoneError(
        "No raw zone configured, so there is nowhere to archive what this run "
        f"reads. Set {BUCKET_ENV_VAR} to the raw-zone bucket, or "
        f"{LOCAL_DIR_ENV_VAR} to a local directory. Pass --no-raw to ingest "
        "without archiving."
    )


# --- writing -------------------------------------------------------------------


def _cell_value(value: Any) -> Any:
    """JSON-safe cell value, keeping numbers as numbers.

    Dates become ISO strings, which is what the mapping layer parses anyway, and
    what a spreadsheet holding text dates would have handed us in the first
    place.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _table_rows(table: SheetTable, source_label: str) -> Iterator[dict]:
    for row in table.rows:
        cells = {
            key: _cell_value(value)
            for key, value in row.items()
            if key != SheetTable.ROW_NUMBER_KEY
        }
        yield {
            "source": source_label,
            "tab": table.title,
            "row_number": table.row_number(row),
            "header_json": json.dumps(table.header),
            "cells_json": json.dumps(cells),
        }


def archive_tables(
    tables: Sequence[SheetTable],
    *,
    dataset: str,
    source_label: str,
    raw_url: str | None = None,
    pipelines_dir: str | None = None,
) -> RawExtract:
    """Archive what was read, and report the load id that names the snapshot.

    Appends rather than replaces: the archive is a record of what each run saw,
    so an earlier snapshot stays readable after the source has moved on.
    """
    import dlt

    url = raw_zone_url(raw_url)
    tables = [table for table in tables if table.rows]
    if not tables:
        raise RawZoneError("Nothing to archive: the source held no data rows.")

    resources = [
        dlt.resource(
            _table_rows(table, source_label),
            name=table.title,
            write_disposition="append",
        )
        for table in tables
    ]

    pipeline = dlt.pipeline(
        pipeline_name=f"oco_{dataset}",
        destination=dlt.destinations.filesystem(bucket_url=url, layout=RAW_LAYOUT),
        dataset_name=dataset,
        pipelines_dir=pipelines_dir,
        progress=None,
    )
    info = pipeline.run(resources, loader_file_format=LOADER_FILE_FORMAT)

    load_ids = list(info.loads_ids)
    if not load_ids:
        raise RawZoneError("dlt reported no load package; nothing was archived.")

    return RawExtract(
        load_id=load_ids[-1],
        url=url,
        dataset=dataset,
        row_counts={table.title: len(table.rows) for table in tables},
    )


# --- reading back --------------------------------------------------------------


def _filesystem(url: str):
    import fsspec

    return fsspec.core.url_to_fs(url)


def list_snapshots(
    dataset: str, *, raw_url: str | None = None, limit: int | None = None
) -> list[str]:
    """Load ids held for ``dataset``, newest last.

    dlt load ids are epoch timestamps, so lexical order is chronological.
    """
    url = raw_zone_url(raw_url)
    fs, root = _filesystem(url)
    pattern = f"{root.rstrip('/')}/{dataset}/**/*.parquet"
    load_ids = set()
    for path in fs.glob(pattern):
        match = _LOAD_FILE_RE.search(str(path))
        if match:
            load_ids.add(match.group("load_id"))
    ordered = sorted(load_ids)
    return ordered[-limit:] if limit else ordered


def read_snapshot(
    dataset: str, load_id: str | None = None, *, raw_url: str | None = None
) -> list[SheetTable]:
    """Rebuild the tabs archived under ``load_id`` (default: the newest).

    What comes back is what the source said at that moment, so a replay maps the
    same rows the original run mapped -- including whatever was wrong with them.
    """
    import pyarrow.parquet as pq

    url = raw_zone_url(raw_url)
    fs, root = _filesystem(url)

    if load_id is None:
        available = list_snapshots(dataset, raw_url=raw_url, limit=1)
        if not available:
            raise RawZoneError(
                f"No archived snapshot for {dataset!r} at {url}. Run the ingest "
                "once to create one."
            )
        load_id = available[-1]

    # Narrowed to the wanted load id rather than listing the dataset and
    # filtering here: on GCS a listing costs a request per page, and snapshots
    # accumulate for as long as the archive is kept.
    paths = [
        path
        for path in fs.glob(f"{root.rstrip('/')}/{dataset}/**/{load_id}.*.parquet")
        if (match := _LOAD_FILE_RE.search(str(path))) is not None
        and match.group("load_id") == load_id
    ]
    if not paths:
        raise RawZoneError(
            f"No snapshot {load_id!r} for {dataset!r} at {url}. "
            f"Available: {', '.join(list_snapshots(dataset, raw_url=raw_url)) or 'none'}."
        )

    by_tab: dict[str, list[dict]] = {}
    headers: dict[str, list[str]] = {}
    for path in sorted(paths):
        with fs.open(path, "rb") as handle:
            for record in pq.read_table(handle).to_pylist():
                tab = record["tab"]
                headers.setdefault(tab, json.loads(record["header_json"] or "[]"))
                row = json.loads(record["cells_json"] or "{}")
                row[SheetTable.ROW_NUMBER_KEY] = record["row_number"]
                by_tab.setdefault(tab, []).append(row)

    return [
        SheetTable(
            title=tab,
            header=headers.get(tab, []),
            rows=sorted(rows, key=lambda r: r.get(SheetTable.ROW_NUMBER_KEY) or 0),
        )
        for tab, rows in by_tab.items()
    ]


# ============= EOF =============================================
