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
dlt resources landing San Acacia in the GCS raw zone.

Two resources, with deliberately different dispositions:

* ``vanessen_locations`` -- the monitoring point roster, ``replace``. It is a
  snapshot of what the vendor currently lists, and a point disappearing is
  information we want to see rather than accumulate.
* ``vanessen_readings`` -- the water level series, ``append``, incremental on
  the reading timestamp. Appending is what makes Mode B replay possible: the
  raw zone keeps what the vendor said at the time, not just what it says now.

Nothing is transformed here. The raw zone stores the vendor's payload as it
arrived, in the vendor's units and on the vendor's datum, so a mapping bug is a
reprocess rather than a re-fetch. Conversion to Ocotillo's model happens in the
adapter, downstream.
"""

from collections.abc import Iterator
from typing import Any

import dlt

from automated_ingestion.shared.gcs import RAW_LAYOUT, raw_zone_bucket
from automated_ingestion.shared.windows import DAY
from automated_ingestion.shared.source_registry import SourceDefinition, register
from automated_ingestion.sources.san_acacia.client import (
    GROUND_SURFACE_REFERENCE,
    SOURCE_UNIT,
    DiverHubClient,
    DiverHubError,
)

PROJECT_ID = 4317
"""Diver-HUB project ``SanAcaciaReach``. Confirmed by probing, not assumed."""

READING_SPAN = 365 * DAY
"""Window width for this source, measured rather than assumed.

``WaterLevels`` served 730 days and 18111 rows in a single request when probed,
so the generic 90-day default in ``shared/windows.py`` would quadruple the
request count for no benefit -- a first run for one point covers a decade. This
sits at half the largest span observed to work, leaving room for a denser point
than SO-0125.
"""

LOADER_FILE_FORMAT = "parquet"
"""Raw-zone file format.

dlt writes gzipped JSONL unless told otherwise, and the first live run landed
that way. Parquet is what Mode B replay assumes: replay reads the raw zone
filtered on event time, and a columnar format with real types lets that read a
window without decompressing and parsing every record. It also preserves the
distinction between a null and a missing field, which JSONL round-trips less
reliably.
"""

INITIAL_START = "2015-01-01T00:00:00+00:00"
"""Floor for a point that has never been ingested.

A floor, never a backfill lever: moving it forward does not delete anything
already landed, and moving it backward does not fetch history for a point whose
cursor has advanced past it. Use a backfill job for that
(``BACKFILL_STRATEGY.md`` section 2).
"""

SOURCE = register(
    SourceDefinition(
        key="san_acacia",
        display_name="San Acacia Reach",
        dataset_name="raw_sanacaciareach",
    )
)


@dlt.resource(name="vanessen_locations", write_disposition="replace")
def vanessen_locations(client: DiverHubClient) -> Iterator[dict[str, Any]]:
    """The monitoring point roster.

    One request, no pagination. The payload is ``{id, name}`` and nothing more
    -- no coordinates, no construction detail -- so this cannot be the source
    of a well's geometry. It exists to enumerate the points a reading fetch
    walks, and to record what the vendor listed on a given day.
    """
    for point in client.monitoring_points(PROJECT_ID):
        yield {
            "monitoring_point_id": point["id"],
            "name": point["name"],
            "project_id": PROJECT_ID,
        }


@dlt.resource(name="vanessen_readings", write_disposition="append")
def vanessen_readings(
    client: DiverHubClient,
    monitoring_points: list[dict[str, Any]],
    end: int,
    failures: list[dict[str, Any]],
    cursor: dlt.sources.incremental[str] = dlt.sources.incremental(
        "dateAndTime", initial_value=INITIAL_START
    ),
) -> Iterator[dict[str, Any]]:
    """Water levels for every point, from each point's watermark to ``end``.

    Failure is isolated per point. One diver returning a 500 for its whole
    history should cost that diver's data for this run, not the other
    thirty-seven -- so exceptions are caught here and appended to ``failures``
    rather than raised.

    ``failures`` is supplied by the caller rather than stashed on the resource:
    a dlt resource is a module-level object shared by every run, so recording
    per-run state on it would have one run overwriting another's.
    """
    from automated_ingestion.sources.san_acacia.client import _parse_timestamp

    start = int(_parse_timestamp(cursor.last_value))

    for point in monitoring_points:
        point_id = point["monitoring_point_id"]
        try:
            approved_at = _approved_timestamps(client, point_id, start, end)
            for row in client.water_levels(
                point_id,
                start,
                end,
                reference=GROUND_SURFACE_REFERENCE,
                span=READING_SPAN,
            ):
                yield {
                    "monitoring_point_id": point_id,
                    "name": point["name"],
                    "dateAndTime": row["dateAndTime"],
                    "level": row["level"],
                    "unit": SOURCE_UNIT,
                    "reference": GROUND_SURFACE_REFERENCE,
                    "vendor_approved": row["dateAndTime"] in approved_at,
                }
        except DiverHubError as exc:
            failures.append({"monitoring_point_id": point_id, "error": str(exc)})


def _approved_timestamps(
    client: DiverHubClient, point_id: int, start: int, end: int
) -> set[str]:
    """Timestamps the vendor has marked approved.

    ``approved`` is a request parameter rather than a response field, so the
    flag has to be recovered by asking twice. We take the unfiltered series as
    the authoritative row set and use this only to tag it -- fetching
    ``approved=true`` and ``approved=false`` separately and concatenating would
    duplicate every row if the two sets overlap, which is not yet known.

    A failure here is not fatal: an untagged reading is worth more than no
    reading, and the vendor flag is not Ocotillo's review status anyway.
    """
    try:
        rows = client.water_levels(
            point_id,
            start,
            end,
            reference=GROUND_SURFACE_REFERENCE,
            approved=True,
            span=READING_SPAN,
        )
        return {row["dateAndTime"] for row in rows}
    except DiverHubError:
        return set()


def build_pipeline() -> Any:
    """A dlt pipeline writing parquet to the raw zone.

    The pipeline is named after the bucket it writes to rather than after a
    separately supplied environment. Those were two sources of truth for one
    fact, and they disagreed the first time this ran in Dagster+: a pipeline
    called ``san_acacia_staging`` writing to the production bucket, because the
    name came from a run tag that was absent and the bucket came from the
    environment. Deriving one from the other makes that impossible.
    """
    # gcsfs resolves Application Default Credentials the same way the Cloud SQL
    # connector does, and Serverless supplies none of its own.
    from automated_ingestion.shared.credentials import (
        ensure_application_default_credentials,
    )

    ensure_application_default_credentials()

    bucket = raw_zone_bucket()
    return dlt.pipeline(
        pipeline_name=f"{SOURCE.key}_{bucket}",
        destination=dlt.destinations.filesystem(
            bucket_url=f"gs://{bucket}",
            layout=RAW_LAYOUT,
        ),
        dataset_name=SOURCE.dataset_name,
    )


# ============= EOF =============================================
