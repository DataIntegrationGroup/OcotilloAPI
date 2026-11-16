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
Rules for the groundwater level export, as plain functions over plain values.

Nothing here touches the database, GCS, pyarrow or HTTP, so every decision the
export makes -- what a file contains, when a well counts as changed, which task
converts which well, what a check rejects, what a STAC item says -- is testable
in milliseconds. The step modules do the I/O and call into this one.

These rules have one caller, so they live beside it rather than in ``domain/``
(ADR4: extract when a rule is shared).
"""

import hashlib
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

FORMAT_VERSION = "1"
"""Bumped whenever the file layout changes.

It is folded into every well's content hash, so a bump marks every well as
changed and the next run rewrites every file -- which is what a format change
needs, and nothing else triggers.
"""

COLLECTION_ID = "groundwater-levels"
ITEM_ID_PREFIX = "gwl-"
PUBLISHED_PREFIX = "groundwater-levels"
"""Fixed path for published files: ``groundwater-levels/<well>/gwl-<well>.*``."""

RUNS_PREFIX = "_runs"
"""Per-snapshot working area. Not published; aged out by a bucket lifecycle rule."""

STATE_PATH = "_state/published.json"
"""What the last *completed* run published. Written last, by the STAC step."""


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # "string" | "int" | "float" | "timestamp"
    nullable: bool
    description: str


# Provisional: the column list is an open question on OCO-79 (AMP review).
# Changing it means editing this tuple and bumping FORMAT_VERSION.
COLUMNS: tuple[Column, ...] = (
    Column("well_id", "string", False, "Ocotillo well name (legacy PointID)."),
    Column("thing_id", "int", False, "Ocotillo thing id."),
    Column("observation_id", "int", False, "Ocotillo observation id."),
    Column("datetime", "timestamp", False, "Measurement time, UTC."),
    Column(
        "depth_to_water_bgs",
        "float",
        True,
        "Depth to water below ground surface: the measured value less the "
        "measuring point height (0 when none was recorded).",
    ),
    Column(
        "depth_to_water_below_mp",
        "float",
        True,
        "Depth to water below the measuring point, as measured.",
    ),
    Column(
        "measuring_point_height",
        "float",
        True,
        "Measuring point height above ground surface.",
    ),
    Column("unit", "string", True, "Unit of the three depth columns."),
    Column("measurement_method", "string", True, "How the level was measured."),
    Column("data_quality", "string", True, "Legacy NM_Aquifer data quality."),
    Column(
        "groundwater_level_reason",
        "string",
        True,
        "Why the level may not be representative (pumping, obstruction...).",
    ),
    Column("longitude", "float", False, "Well longitude, WGS84."),
    Column("latitude", "float", False, "Well latitude, WGS84."),
)
COLUMN_NAMES: tuple[str, ...] = tuple(c.name for c in COLUMNS)

# Depth-to-water bounds for the range check, in feet below ground surface.
# Negative is legitimate (flowing artesian wells); the deepest water levels in
# New Mexico are a few thousand feet. A value outside is almost certainly a unit
# or sign error. Provisional, like the column list.
DEPTH_TO_WATER_MIN_FT = -500.0
DEPTH_TO_WATER_MAX_FT = 5000.0


class ExportRuleError(ValueError):
    """A rule rejected a value."""


# --------------------------------------------------------------------- naming
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def safe_well_id(well_id: str) -> str:
    """The well name as it appears in object paths and STAC item ids.

    Well names are mostly ``AB-0001`` style, but nothing in the schema stops a
    space or slash, and either would corrupt a path. Runs of anything unsafe
    become ``_``. Two wells colliding after this is caught by ``assert_unique``.
    """
    if not well_id or not well_id.strip():
        raise ExportRuleError("well_id is empty")
    return _SAFE_ID.sub("_", well_id.strip())


def item_id(well_id: str) -> str:
    return f"{ITEM_ID_PREFIX}{safe_well_id(well_id)}"


def published_paths(well_id: str) -> dict[str, str]:
    """Fixed object paths for one well's published files."""
    safe = safe_well_id(well_id)
    base = f"{PUBLISHED_PREFIX}/{safe}/{ITEM_ID_PREFIX}{safe}"
    return {
        "parquet": f"{base}.parquet",
        "csv": f"{base}.csv",
        "item": f"{base}.json",
    }


def run_paths(snapshot_id: str) -> dict[str, str]:
    """Working-area paths for one snapshot."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", snapshot_id):
        raise ExportRuleError(f"unsafe snapshot id {snapshot_id!r}")
    base = f"{RUNS_PREFIX}/{snapshot_id}"
    return {
        "base": base,
        "snapshot": f"{base}/snapshot.parquet",
        "manifest": f"{base}/manifest.json",
        "files": f"{base}/wells",
        "reports": f"{base}/reports",
    }


def staged_paths(snapshot_id: str, well_id: str) -> dict[str, str]:
    files = run_paths(snapshot_id)["files"]
    safe = safe_well_id(well_id)
    return {
        "parquet": f"{files}/{ITEM_ID_PREFIX}{safe}.parquet",
        "csv": f"{files}/{ITEM_ID_PREFIX}{safe}.csv",
    }


def new_snapshot_id(now: datetime, run_id: str) -> str:
    """``20261116T091500Z-1a2b3c4d``: sortable, and traceable to a Dagster run."""
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = re.sub(r"[^A-Za-z0-9]", "", run_id)[:8] or "manual"
    return f"{stamp}-{suffix}"


def assert_unique(well_ids: Iterable[str]) -> None:
    seen: dict[str, str] = {}
    for well in well_ids:
        safe = safe_well_id(well)
        if safe in seen and seen[safe] != well:
            raise ExportRuleError(
                f"wells {seen[safe]!r} and {well!r} map to the same path {safe!r}"
            )
        seen[safe] = well


# ---------------------------------------------------------------- change test
def _canonical(value: Any) -> str:
    if value is None:
        return "\x00"
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ExportRuleError("naive datetime in export rows")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, float):
        return repr(value)
    return str(value)


def well_content_hash(rows: Iterable[Mapping[str, Any]]) -> str:
    """SHA-256 over one well's rows, in file order, plus the format version.

    This is the whole of change detection. A well whose hash matches the last
    published one is skipped -- no file written, no STAC call -- which is what
    makes a rerun over unchanged data write nothing.
    """
    digest = hashlib.sha256()
    digest.update(f"v{FORMAT_VERSION}\x1d{','.join(COLUMN_NAMES)}\x1d".encode())
    for row in rows:
        digest.update(
            "\x1f".join(_canonical(row.get(c)) for c in COLUMN_NAMES).encode()
        )
        digest.update(b"\x1e")
    return digest.hexdigest()


def sort_key(row: Mapping[str, Any]) -> tuple:
    """File order: by time, ties broken by observation id so order is stable."""
    return (row["datetime"], row["observation_id"])


@dataclass(frozen=True)
class Plan:
    changed: list[str]
    unchanged: list[str]
    withdrawn: list[str]


def plan_changes(current: Mapping[str, str], published: Mapping[str, str]) -> Plan:
    """Compare this snapshot's hashes with the last published ones.

    ``withdrawn`` are wells published before and absent now -- a well that
    stopped being public, or lost its last water level. Their files and items
    must come down: leaving them would keep publishing what is no longer
    releasable.
    """
    changed = sorted(w for w, h in current.items() if published.get(w) != h)
    unchanged = sorted(w for w, h in current.items() if published.get(w) == h)
    withdrawn = sorted(w for w in published if w not in current)
    return Plan(changed=changed, unchanged=unchanged, withdrawn=withdrawn)


def shard(wells: Sequence[str], task_index: int, task_count: int) -> list[str]:
    """The wells one Cloud Run task converts.

    Round-robin over the sorted list, so tasks get near-equal counts and every
    well lands in exactly one task.
    """
    if task_count < 1 or not 0 <= task_index < task_count:
        raise ExportRuleError(f"task {task_index} of {task_count} is not valid")
    return [w for i, w in enumerate(sorted(wells)) if i % task_count == task_index]


# --------------------------------------------------------------------- checks
@dataclass
class WellCheck:
    well_id: str
    errors: list[str]
    warnings: list[str]


def check_well(
    well_id: str,
    expected_rows: int,
    parquet_rows: int,
    csv_rows: int,
    schema_names: Sequence[str],
    null_ids: int,
    sorted_by_time: bool,
    depths: Iterable[float | None],
) -> WellCheck:
    """Every check one well's files must pass before they are published.

    Errors block publication of the whole run. Out-of-range depths are
    warnings: legacy data holds a few, and one bad 1970s reading should not
    freeze every other well's file. They are reported, not hidden.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if parquet_rows != expected_rows:
        errors.append(f"parquet has {parquet_rows} rows, database has {expected_rows}")
    if csv_rows != expected_rows:
        errors.append(f"csv has {csv_rows} rows, database has {expected_rows}")

    expected_schema = [*COLUMN_NAMES, "geometry"]
    if list(schema_names) != expected_schema:
        errors.append(f"schema {list(schema_names)} != {expected_schema}")
    if null_ids:
        errors.append(f"{null_ids} rows with a null id or datetime")
    if not sorted_by_time:
        errors.append("rows are not sorted by datetime")

    out_of_range = [
        d
        for d in depths
        if d is not None
        and (math.isnan(d) or not DEPTH_TO_WATER_MIN_FT <= d <= DEPTH_TO_WATER_MAX_FT)
    ]
    if out_of_range:
        warnings.append(
            f"{len(out_of_range)} depth_to_water_bgs values outside "
            f"[{DEPTH_TO_WATER_MIN_FT}, {DEPTH_TO_WATER_MAX_FT}]: "
            f"{out_of_range[:5]}"
        )
    return WellCheck(well_id=well_id, errors=errors, warnings=warnings)


# ----------------------------------------------------------------------- STAC
STAC_VERSION = "1.1.0"
FILE_EXTENSION = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"
CSV_MEDIA_TYPE = "text/csv; charset=utf-8; header=present"


def multihash_sha256(hex_digest: str) -> str:
    """``file:checksum`` wants a multihash: 0x12 (sha2-256), 0x20 (32 bytes)."""
    return f"1220{hex_digest}"


def build_item(
    well_id: str,
    thing_id: int,
    longitude: float,
    latitude: float,
    start: datetime,
    end: datetime,
    row_count: int,
    files: Mapping[str, Mapping[str, Any]],
    public_base_url: str,
    updated: datetime,
) -> dict[str, Any]:
    """The STAC item for one well.

    ``files`` maps ``parquet``/``csv`` to ``{"path", "size", "sha256"}``. Hrefs
    are absolute, built from ``public_base_url`` and the fixed path, so they do
    not change between runs -- a link someone saved keeps working.
    """
    base = public_base_url.rstrip("/")
    point = [longitude, latitude]

    def asset(kind: str, title: str, media_type: str) -> dict[str, Any]:
        meta = files[kind]
        return {
            "href": f"{base}/{meta['path']}",
            "type": media_type,
            "title": title,
            "roles": ["data"],
            "file:size": meta["size"],
            "file:checksum": multihash_sha256(meta["sha256"]),
        }

    return {
        "type": "Feature",
        "stac_version": STAC_VERSION,
        "stac_extensions": [FILE_EXTENSION],
        "id": item_id(well_id),
        "collection": COLLECTION_ID,
        "geometry": {"type": "Point", "coordinates": point},
        "bbox": [*point, *point],
        "properties": {
            "title": f"Groundwater levels for {well_id}",
            "datetime": None,
            "start_datetime": _iso(start),
            "end_datetime": _iso(end),
            "updated": _iso(updated),
            "nmbgmr:well_id": well_id,
            "nmbgmr:thing_id": thing_id,
            "nmbgmr:observation_count": row_count,
            "nmbgmr:format_version": FORMAT_VERSION,
        },
        "links": [],
        "assets": {
            "data": asset("parquet", "GeoParquet (ZSTD)", PARQUET_MEDIA_TYPE),
            "csv": asset("csv", "CSV", CSV_MEDIA_TYPE),
        },
    }


def build_collection(public_base_url: str) -> dict[str, Any]:
    """The ``groundwater-levels`` collection, created if the API lacks it."""
    return {
        "type": "Collection",
        "stac_version": STAC_VERSION,
        "stac_extensions": [],
        "id": COLLECTION_ID,
        "title": "Groundwater levels by well",
        "description": (
            "Full manual groundwater level history for each public well in "
            "Ocotillo (NMBGMR), one GeoParquet and one CSV per well, refreshed "
            "from a consistent database snapshot."
        ),
        "license": "CC-BY-4.0",
        "keywords": ["groundwater", "water level", "New Mexico", "NMBGMR"],
        "providers": [
            {
                "name": "New Mexico Bureau of Geology and Mineral Resources",
                "roles": ["producer", "host"],
                "url": "https://geoinfo.nmt.edu",
            }
        ],
        "extent": {
            # New Mexico. Temporal extent is open-ended on purpose: the
            # collection is refreshed, not closed.
            "spatial": {"bbox": [[-109.06, 31.33, -103.0, 37.0]]},
            "temporal": {"interval": [[None, None]]},
        },
        "links": [],
        "item_assets": {
            "data": {"type": PARQUET_MEDIA_TYPE, "roles": ["data"]},
            "csv": {"type": CSV_MEDIA_TYPE, "roles": ["data"]},
        },
    }


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ============= EOF =============================================
