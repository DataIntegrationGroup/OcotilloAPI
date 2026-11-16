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
The five steps of the export. Each runs as its own Cloud Run job execution.

Steps hand off through the export root, never through memory: every step reads
what the previous one wrote under ``_runs/<snapshot_id>/`` and writes a report
to ``_runs/<snapshot_id>/reports/<step>.json``, which the Dagster asset reads
back as metadata. That is what lets a single step be re-run on its own, and
what lets the steps run in separate containers at all.

The commit point is ``_state/published.json``, written last by ``register``.
Until it is, the previous state stands, so a run that dies anywhere is redone
in full by the next one -- every step is safe to repeat.
"""

import csv
import hashlib
import io
import struct
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from automated_ingestion.exports.groundwater_levels import rules
from automated_ingestion.exports.groundwater_levels.storage import (
    Storage,
    read_json,
    write_json,
)


class StepError(RuntimeError):
    """A step refused to continue. The worker exits non-zero on it."""


# ---------------------------------------------------------------- arrow bits
def _arrow_schema(with_geometry: bool):
    import json

    import pyarrow as pa

    kinds = {
        "string": pa.string(),
        "int": pa.int64(),
        "float": pa.float64(),
        "timestamp": pa.timestamp("us", tz="UTC"),
    }
    fields = [
        pa.field(c.name, kinds[c.kind], nullable=c.nullable) for c in rules.COLUMNS
    ]
    if with_geometry:
        fields.append(pa.field("geometry", pa.binary(), nullable=False))
    metadata = {
        "nmbgmr:format_version": rules.FORMAT_VERSION,
        "nmbgmr:column_descriptions": json.dumps(
            {c.name: c.description for c in rules.COLUMNS}
        ),
    }
    return pa.schema(fields, metadata=metadata)


def _point_wkb(lon: float, lat: float) -> bytes:
    # Little-endian WKB Point: byte order, type 1, x, y.
    return struct.pack("<BIdd", 1, 1, lon, lat)


def _geo_metadata(lon: float, lat: float) -> bytes:
    """GeoParquet 1.1 file metadata. No ``crs`` key means OGC:CRS84 (lon/lat)."""
    import json

    return json.dumps(
        {
            "version": "1.1.0",
            "primary_column": "geometry",
            "columns": {
                "geometry": {
                    "encoding": "WKB",
                    "geometry_types": ["Point"],
                    "bbox": [lon, lat, lon, lat],
                }
            },
        }
    ).encode()


def _report(storage: Storage, snapshot_id: str, step: str, body: dict) -> dict:
    body = {"step": step, "snapshot_id": snapshot_id, **body}
    write_json(storage, f"{rules.run_paths(snapshot_id)['reports']}/{step}.json", body)
    return body


def read_report(storage: Storage, snapshot_id: str, step: str) -> dict:
    return read_json(storage, f"{rules.run_paths(snapshot_id)['reports']}/{step}.json")


def _manifest(storage: Storage, snapshot_id: str) -> dict:
    path = rules.run_paths(snapshot_id)["manifest"]
    if not storage.exists(path):
        raise StepError(f"no manifest for snapshot {snapshot_id}; run snapshot first")
    return read_json(storage, path)


def _state(storage: Storage) -> dict:
    return read_json(storage, rules.STATE_PATH, default={"wells": {}})


# ------------------------------------------------------------ 1. snapshot
def snapshot(
    storage: Storage,
    snapshot_id: str,
    rows: list[dict[str, Any]],
    db_counts: dict[str, int],
    taken_at: datetime,
) -> dict:
    """Write the snapshot and decide which wells changed.

    ``rows`` and ``db_counts`` come from ``snapshot.read_snapshot`` -- one
    transaction -- so a disagreement between them means the read was not
    consistent, and nothing downstream can be trusted.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    by_well: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_well[row["well_id"]].append(row)
    rules.assert_unique(by_well)

    counted = {w: len(r) for w, r in by_well.items()}
    if counted != db_counts:
        diff = sorted(set(counted.items()) ^ set(db_counts.items()))[:10]
        raise StepError(f"snapshot rows disagree with database counts: {diff}")

    wells: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for well_id in sorted(by_well):
        well_rows = sorted(by_well[well_id], key=rules.sort_key)
        ordered.extend(well_rows)
        first = well_rows[0]
        wells[well_id] = {
            "thing_id": first["thing_id"],
            "longitude": first["longitude"],
            "latitude": first["latitude"],
            "rows": len(well_rows),
            "start": well_rows[0]["datetime"].isoformat(),
            "end": well_rows[-1]["datetime"].isoformat(),
            "sha256": rules.well_content_hash(well_rows),
        }

    published = {w: m["sha256"] for w, m in _state(storage)["wells"].items()}
    plan = rules.plan_changes({w: m["sha256"] for w, m in wells.items()}, published)

    paths = rules.run_paths(snapshot_id)
    table = pa.Table.from_pylist(ordered, schema=_arrow_schema(with_geometry=False))
    buffer = io.BytesIO()
    # Row groups of ~64k rows keep the convert tasks' well filter cheap: a task
    # reads only the groups whose well_id range overlaps its shard.
    pq.write_table(table, buffer, compression="zstd", row_group_size=65_536)
    storage.write_bytes(paths["snapshot"], buffer.getvalue())

    write_json(
        storage,
        paths["manifest"],
        {
            "snapshot_id": snapshot_id,
            "taken_at": taken_at.astimezone(timezone.utc).isoformat(),
            "format_version": rules.FORMAT_VERSION,
            "db_row_total": sum(db_counts.values()),
            "wells": wells,
            "plan": {
                "changed": plan.changed,
                "unchanged": plan.unchanged,
                "withdrawn": plan.withdrawn,
            },
        },
    )
    return _report(
        storage,
        snapshot_id,
        "snapshot",
        {
            "rows": len(ordered),
            "wells": len(wells),
            "changed": len(plan.changed),
            "unchanged": len(plan.unchanged),
            "withdrawn": len(plan.withdrawn),
        },
    )


# ------------------------------------------------------------- 2. convert
def convert(
    storage: Storage, snapshot_id: str, task_index: int = 0, task_count: int = 1
) -> dict:
    """Write GeoParquet and CSV for this task's share of the changed wells."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    manifest = _manifest(storage, snapshot_id)
    mine = rules.shard(manifest["plan"]["changed"], task_index, task_count)
    step = f"convert-{task_index:04d}"
    if not mine:
        return _report(storage, snapshot_id, step, {"wells": 0, "rows": 0})

    snapshot_bytes = storage.read_bytes(rules.run_paths(snapshot_id)["snapshot"])
    table = pq.read_table(
        pa.BufferReader(snapshot_bytes), filters=[("well_id", "in", mine)]
    )
    schema = _arrow_schema(with_geometry=True)

    rows_written = 0
    for well_id in mine:
        meta = manifest["wells"][well_id]
        well = table.filter(pc.equal(table["well_id"], well_id)).sort_by(
            [("datetime", "ascending"), ("observation_id", "ascending")]
        )
        lon, lat = meta["longitude"], meta["latitude"]
        well = well.append_column(
            "geometry", pa.array([_point_wkb(lon, lat)] * well.num_rows, pa.binary())
        ).cast(schema)
        well = well.replace_schema_metadata(
            {**(schema.metadata or {}), b"geo": _geo_metadata(lon, lat)}
        )

        staged = rules.staged_paths(snapshot_id, well_id)
        buffer = io.BytesIO()
        pq.write_table(well, buffer, compression="zstd")
        storage.write_bytes(
            staged["parquet"], buffer.getvalue(), rules.PARQUET_MEDIA_TYPE
        )
        storage.write_bytes(staged["csv"], _to_csv(well), rules.CSV_MEDIA_TYPE)
        rows_written += well.num_rows

    return _report(
        storage, snapshot_id, step, {"wells": len(mine), "rows": rows_written}
    )


def _to_csv(table) -> bytes:
    """CSV for spreadsheets: UTF-8 with BOM, ISO 8601 UTC times, no WKB."""
    out = io.StringIO()
    out.write("﻿")  # Excel reads UTF-8 correctly only with a BOM.
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(rules.COLUMN_NAMES)
    for row in table.select(list(rules.COLUMN_NAMES)).to_pylist():
        writer.writerow([_csv_value(row[c]) for c in rules.COLUMN_NAMES])
    return out.getvalue().encode("utf-8")


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, float):
        return repr(value)
    return str(value)


# --------------------------------------------------------------- 3. check
def check(storage: Storage, snapshot_id: str) -> dict:
    """Verify every staged file against the database counts and the schema.

    Raises ``StepError`` -- failing the Cloud Run execution and so the Dagster
    asset -- when any well has an error. Publication never sees a run that
    failed here.
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    manifest = _manifest(storage, snapshot_id)
    paths = rules.run_paths(snapshot_id)
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    snapshot_rows = pq.read_metadata(
        pa.BufferReader(storage.read_bytes(paths["snapshot"]))
    ).num_rows
    if snapshot_rows != manifest["db_row_total"]:
        errors["_snapshot"] = [
            f"snapshot has {snapshot_rows} rows, database had "
            f"{manifest['db_row_total']}"
        ]

    for well_id in manifest["plan"]["changed"]:
        staged = rules.staged_paths(snapshot_id, well_id)
        missing = [k for k, p in staged.items() if not storage.exists(p)]
        if missing:
            errors[well_id] = [f"missing staged {', '.join(missing)}"]
            continue

        table = pq.read_table(pa.BufferReader(storage.read_bytes(staged["parquet"])))
        csv_rows = (
            sum(
                1
                for _ in csv.reader(
                    io.StringIO(storage.read_bytes(staged["csv"]).decode("utf-8-sig"))
                )
            )
            - 1
        )
        null_ids = sum(
            table[c].null_count
            for c in ("well_id", "thing_id", "observation_id", "datetime")
        )
        times = table["datetime"]
        is_sorted = table.num_rows < 2 or bool(
            pc.all(
                pc.greater_equal(times.slice(1), times.slice(0, table.num_rows - 1))
            ).as_py()
        )
        result = rules.check_well(
            well_id=well_id,
            expected_rows=manifest["wells"][well_id]["rows"],
            parquet_rows=table.num_rows,
            csv_rows=csv_rows,
            schema_names=table.schema.names,
            null_ids=null_ids,
            sorted_by_time=is_sorted,
            depths=table["depth_to_water_bgs"].to_pylist(),
        )
        if b"geo" not in (table.schema.metadata or {}):
            result.errors.append("parquet has no GeoParquet 'geo' metadata")
        if result.errors:
            errors[well_id] = result.errors
        if result.warnings:
            warnings[well_id] = result.warnings

    report = _report(
        storage,
        snapshot_id,
        "check",
        {
            "passed": not errors,
            "wells_checked": len(manifest["plan"]["changed"]),
            "errors": errors,
            "warnings": warnings,
        },
    )
    if errors:
        raise StepError(
            f"{len(errors)} wells failed checks; see " f"{paths['reports']}/check.json"
        )
    return report


# ------------------------------------------------------------- 4. publish
def publish(storage: Storage, snapshot_id: str) -> dict:
    """Move checked files to their fixed paths; take withdrawn wells down."""
    manifest = _manifest(storage, snapshot_id)
    checked = (
        read_report(storage, snapshot_id, "check")
        if storage.exists(f"{rules.run_paths(snapshot_id)['reports']}/check.json")
        else None
    )
    if not checked or not checked.get("passed"):
        raise StepError(f"snapshot {snapshot_id} has not passed checks")

    files: dict[str, dict[str, dict[str, Any]]] = {}
    for well_id in manifest["plan"]["changed"]:
        staged = rules.staged_paths(snapshot_id, well_id)
        target = rules.published_paths(well_id)
        files[well_id] = {}
        for kind, media in (
            ("parquet", rules.PARQUET_MEDIA_TYPE),
            ("csv", rules.CSV_MEDIA_TYPE),
        ):
            data = storage.read_bytes(staged[kind])
            storage.write_bytes(target[kind], data, media)
            files[well_id][kind] = {
                "path": target[kind],
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }

    for well_id in manifest["plan"]["withdrawn"]:
        target = rules.published_paths(well_id)
        storage.delete(target["parquet"])
        storage.delete(target["csv"])

    return _report(
        storage,
        snapshot_id,
        "publish",
        {
            "published": len(files),
            "withdrawn": len(manifest["plan"]["withdrawn"]),
            "files": files,
        },
    )


# ------------------------------------------------------------ 5. register
def register(
    storage: Storage,
    snapshot_id: str,
    public_base_url: str,
    stac: Any = None,
    now: datetime | None = None,
) -> dict:
    """Upsert each changed well's STAC item, then commit the new state.

    The item is also written beside the files as static JSON, so the files are
    described even before the STAC API (OCO-78) exists. When the API URL
    changes from the one the state was committed against -- including the
    first time one is configured -- every published well is upserted, not
    just the changed ones, so the API catches up without a manual backfill.
    """
    now = now or datetime.now(tz=timezone.utc)
    manifest = _manifest(storage, snapshot_id)
    published = read_report(storage, snapshot_id, "publish")
    state = _state(storage)
    api_url = getattr(stac, "base_url", None)

    changed = set(manifest["plan"]["changed"])
    if api_url and state.get("stac_api_url") != api_url:
        to_register = sorted(manifest["wells"])
    else:
        to_register = sorted(changed)

    new_state_wells: dict[str, Any] = {}
    for well_id in manifest["wells"]:
        files = (
            published["files"].get(well_id)
            if well_id in changed
            else state["wells"].get(well_id, {}).get("files")
        )
        if files is None:
            # Unchanged in hash but never published: only possible if state
            # was edited by hand. Refuse rather than register a dangling item.
            raise StepError(f"{well_id} has no published files on record")
        new_state_wells[well_id] = {
            "sha256": manifest["wells"][well_id]["sha256"],
            "files": files,
        }

    if stac is not None:
        stac.ensure_collection(rules.build_collection(public_base_url))

    for well_id in to_register:
        meta = manifest["wells"][well_id]
        item = rules.build_item(
            well_id=well_id,
            thing_id=meta["thing_id"],
            longitude=meta["longitude"],
            latitude=meta["latitude"],
            start=datetime.fromisoformat(meta["start"]),
            end=datetime.fromisoformat(meta["end"]),
            row_count=meta["rows"],
            files=new_state_wells[well_id]["files"],
            public_base_url=public_base_url,
            updated=now,
        )
        write_json(storage, rules.published_paths(well_id)["item"], item)
        if stac is not None:
            stac.upsert_item(rules.COLLECTION_ID, item)

    for well_id in manifest["plan"]["withdrawn"]:
        storage.delete(rules.published_paths(well_id)["item"])
        if stac is not None:
            stac.delete_item(rules.COLLECTION_ID, rules.item_id(well_id))

    # The commit point. Everything above is repeatable; this makes it stick.
    write_json(
        storage,
        rules.STATE_PATH,
        {
            "format_version": rules.FORMAT_VERSION,
            "snapshot_id": snapshot_id,
            "committed_at": now.isoformat(),
            "stac_api_url": api_url or state.get("stac_api_url"),
            "wells": new_state_wells,
        },
    )
    return _report(
        storage,
        snapshot_id,
        "register",
        {
            "registered": len(to_register),
            "withdrawn": len(manifest["plan"]["withdrawn"]),
            "stac_api": api_url or "not configured (static items only)",
        },
    )


# ============= EOF =============================================
