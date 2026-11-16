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
Step 1's database read: every public groundwater level, in one transaction.

Both queries run inside a single ``REPEATABLE READ, READ ONLY`` transaction, so
the rows and the per-well counts the checks compare them against come from the
same instant. Pointed at a read replica (the Cloud Run job's
``CLOUD_SQL_INSTANCE_NAME``), the export never loads the primary.

"Public" is the same rule ``NGWMN_WaterLevels`` applies -- every level of the
observation's lineage released -- plus the well's current location, because a
published file carries the well's coordinates. Whether that is the right line
for private wells is an open SBAC question on OCO-79; ``PUBLIC_LEVELS_CTE`` is
the one place it changes.
"""

from datetime import datetime, timezone
from typing import Any

PUBLIC_LEVELS_CTE = """
WITH latest_location AS (
    SELECT DISTINCT ON (lta.thing_id)
        lta.thing_id,
        lta.location_id
    FROM location_thing_association AS lta
    WHERE lta.effective_end IS NULL
    ORDER BY lta.thing_id, lta.effective_start DESC
),
public_wells AS (
    SELECT
        t.id AS thing_id,
        t.name AS well_id,
        ST_X(l.point) AS longitude,
        ST_Y(l.point) AS latitude
    FROM thing AS t
    JOIN latest_location AS ll ON ll.thing_id = t.id
    JOIN location AS l ON l.id = ll.location_id
    WHERE t.thing_type = 'water well'
      AND t.release_status = 'public'
      AND l.release_status = 'public'
      AND l.point IS NOT NULL
),
levels AS (
    SELECT
        w.well_id,
        w.thing_id,
        o.id AS observation_id,
        o.observation_datetime AS datetime,
        o.value - COALESCE(o.measuring_point_height, 0) AS depth_to_water_bgs,
        o.value AS depth_to_water_below_mp,
        o.measuring_point_height,
        o.unit,
        s.sample_method AS measurement_method,
        o.nma_data_quality AS data_quality,
        o.groundwater_level_reason,
        w.longitude,
        w.latitude
    FROM observation AS o
    JOIN parameter AS p ON p.id = o.parameter_id
    JOIN sample AS s ON s.id = o.sample_id
    JOIN field_activity AS fa ON fa.id = s.field_activity_id
    JOIN field_event AS fe ON fe.id = fa.field_event_id
    JOIN public_wells AS w ON w.thing_id = fe.thing_id
    WHERE p.parameter_name = 'groundwater level'
      AND o.release_status = 'public'
      AND s.release_status = 'public'
      AND fa.release_status = 'public'
      AND fe.release_status = 'public'
)
"""

ROWS_SQL = PUBLIC_LEVELS_CTE + """
SELECT * FROM levels
ORDER BY well_id, datetime, observation_id
"""

COUNTS_SQL = PUBLIC_LEVELS_CTE + """
SELECT well_id, count(*) AS n FROM levels GROUP BY well_id
"""


def read_snapshot(session: Any) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Rows and per-well database counts from one consistent snapshot.

    ``SET TRANSACTION`` must be the transaction's first statement; the session
    opens its transaction lazily on the first execute, so it is.
    """
    from sqlalchemy import text

    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    result = session.execute(text(ROWS_SQL))
    rows = [_normalize(dict(r._mapping)) for r in result]
    counts = {well: int(n) for well, n in session.execute(text(COUNTS_SQL)).all()}
    return rows, counts


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    stamp: datetime = row["datetime"]
    if stamp.tzinfo is None:
        # The column is timestamptz, so this is defensive: a naive value from
        # a driver quirk is UTC, and the hash refuses naive datetimes outright.
        stamp = stamp.replace(tzinfo=timezone.utc)
    row["datetime"] = stamp.astimezone(timezone.utc)
    for key in (
        "depth_to_water_bgs",
        "depth_to_water_below_mp",
        "measuring_point_height",
        "longitude",
        "latitude",
    ):
        if row[key] is not None:
            row[key] = float(row[key])
    return row


# ============= EOF =============================================
