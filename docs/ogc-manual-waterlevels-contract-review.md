---
generated-by: claude-opus-5-5
generated-on: 2026-11-06
prompted-by: jakeross
---

# Review: `docs/ogc-waterlevels-data-contract.md` (commit 446a87b)

Writing style: ASD-STE100 (Simplified Technical English). Short sentences.
Active voice. One topic in each paragraph.

All code references are to commit `446a87b`.

## 1. Summary

The analysis of the views is correct. The analysis of the EDR memory problem
is not correct. It puts the cause on the EDR standard. The cause is our
provider. Also, the analysis does not measure the data volume. Manual water
levels are small. The memory risk comes from the transducer readings.

Section 6 is an example contract. It shows the parts that the current
document does not have.

## 2. Statements that are correct

| Statement in the document | Result | Evidence |
|---|---|---|
| `ogc_waterlevels` is a union of manual and transducer readings. | Correct | `baba91fe5e83`, lines 59-111. |
| The view reports `groundwater level` and ignores the measuring-point height. | Correct | The view selects `o.value`. It does not read `o.measuring_point_height` or `measuring_point_history`. |
| The feature `id` is an integer. The coverage `id` is a string. | Correct | `core/edr_provider.py`: `"id": row["thing_id"]` and `"id": str(thing_id)`. |
| `_station_properties` must change to add `well_depth` and other fields. | Correct | It returns only `name` (and `thing_type` for chemistry). |
| A null measuring-point height must be documented. | Correct | `docs/measuring-point-height-null-handling.md` tells new layers to follow the `0` rule or to document why not. |
| A 413 response is a good guard. | Correct | OGC API - EDR lists 413 as the response for a query that is too large. |

## 3. Statements that are not correct, or not complete

### 3.1 "EDR APIs do not paginate"

This is not the correct cause. OGC API - EDR does not define paging for data
queries. But it does not tell a server to load all data into memory. Our
provider does that:

1. `_fetch()` calls `cur.fetchall()`.
2. `_coverage_collection()` builds the full CoverageJSON dict.
3. pygeoapi serializes that dict in one step.

We can fix this in the provider. Do a `count(*)` with the same filters before
the read. If the count is more than a limit, send 413. This gives a known
upper limit on memory for each request. The standard permits it.

### 3.2 "No guarantee that one location will not exceed memory"

This is true in theory only. Measure it. A manual reading is one row of
approximately 100-200 bytes. A well with 50 years of monthly visits has
approximately 600 rows. That is less than 1 MB. A manual-only collection
does not have a memory problem at `/locations/{locId}`.

The transducer data is different. One transducer at a 15-minute interval
makes approximately 35,000 readings each year. These rows cause the memory
problem. When you split manual from transducer (Section 3.5), most of the
problem goes away for WeaverAPI.

Action: run these queries on production before you make a decision.

```sql
SELECT source, count(*) FROM ogc_waterlevels GROUP BY source;

SELECT source, max(n) FROM (
  SELECT source, thing_id, count(*) AS n
  FROM ogc_waterlevels GROUP BY source, thing_id
) s GROUP BY source;
```

### 3.3 The "easy" workflow uses the worst query

The document says: get all locations, then call `/area` or `/cube` with a box
that holds all locations. That is one request for all of the data. It is the
request most likely to fail. Use one of these:

- Call `/locations/{locId}` one time for each well. For manual data, each
  response is small (Section 3.2).
- Divide the state into tiles. Call `/cube` one time for each tile.

### 3.4 A second coverage for measuring-point height

The document proposes "a second `coverage` with n measuring point heights".
This is not the correct CoverageJSON structure. A coverage can hold more than
one range on the same domain. Add `measuring point height` as a second key in
`parameters` and a second key in the `ranges` of the same coverage. The two
arrays then align on the same `t` axis. A second coverage does not align.

We do not need this if the view calculates the depth below ground surface
(Section 4.1).

### 3.5 Split by parameter name or by collection

The document does not see that the view already has a `source` column
(`'manual'` or `'transducer'`). The provider does not use it.

There is a problem with a split by parameter name only. The provider makes one
`t` axis for each well. This axis is the union of the times of all parameters
(`times = sorted({r["datetime"] for r in srows})`). If one coverage holds a
manual parameter and a transducer parameter, the manual array gets one null
for each transducer time. A well with 10 manual readings and 100,000
transducer readings gives a manual array of 100,000 items. Almost all items
are null.

Recommendation: make a separate collection. Make a view
`ogc_manual_waterlevels` that selects `WHERE source = 'manual'` (or copy the
manual half of the union). Add it to `EDR_COLLECTIONS` in `core/pygeoapi.py`.
Do the same for `ogc_internal_waterlevels`.

### 3.6 "Pivot to Features is harder"

The reasons in the document are weak.

- OGC API - Features has paging (`limit`, `offset`, `next` links). Our
  config sets `max_items: 10000`. This directly fixes the memory problem.
- A `thing_id` property on each observation is a foreign key. It is not
  "mixed data". The consumer joins it to the well collection. This is the
  same join that the EDR design needs.

Features has real costs. Deep `offset` pages on a large view are slow. The
response is not CoverageJSON.

Recommendation: for WeaverAPI, keep EDR and use Section 3.3. Use Features
only if WeaverAPI must get a full copy of all readings in one job.

## 4. Problems that the document does not identify

### 4.1 The measuring-point height is on the observation row

`observation.measuring_point_height` exists (`db/observation.py`, line 73).
`measuring_point_history` also exists, with `start_date` and `end_date`. The
view can calculate the depth below ground surface for each reading:

```sql
o.value - COALESCE(
  o.measuring_point_height,
  (SELECT mph.measuring_point_height
     FROM measuring_point_history mph
    WHERE mph.thing_id = t.id
      AND mph.start_date <= o.observation_datetime::date
      AND (mph.end_date IS NULL OR mph.end_date > o.observation_datetime::date)
    ORDER BY mph.start_date DESC LIMIT 1),
  0
) AS value
```

Decision needed: which source wins if both exist. The example above uses the
observation value first.

The current field description says "Depth from the measuring point". The new
parameter must say "Depth from the ground surface". Update
`core/ogc-field-descriptions.yml`.

### 4.2 Readings at the same time overwrite each other

In `_coverage_collection()`, this line puts each value into a slot:
`values[t_index[r["datetime"]]] = r["value"]`. If two readings have the same
`datetime` and the same parameter, the second value replaces the first. The
provider does not show an error. This can occur now with a manual reading and
a transducer reading at the same time. The contract must state the rule. For
example: "One value for each time. Duplicates are not permitted." Then add a
check or a unique constraint.

### 4.3 The `/locations` list reads the full view

The `/locations` list does `SELECT DISTINCT ... FROM ogc_waterlevels`. This
reads every transducer row to find the wells. A manual-only view fixes most
of this. A view of wells only (one row for each well) fixes all of it.

### 4.4 Incremental sync is not possible

The document says that WeaverAPI runs each night. The EDR `datetime` filter
uses the observation time. It does not use the time of the last change. A
correction to a reading from 1998 is not found by a filter for "last night".
WeaverAPI must read all of the data each night, or we must add a "changed
since" filter. The contract must say which.

### 4.5 The contract itself is not complete

The current "Shape" section shows a template. It does not show:

- Data types, and which fields can be null.
- The meaning of null (for example, `well_depth` unknown).
- The datetime format and time zone.
- The sort order of the `t` axis.
- The set of wells included (public only? wells only, or springs also?).
- The error responses.
- The size limits.
- The version and the change policy.
- A real example that a consumer can test against.

The placeholders (`id`, `longitude`) are not valid JSON. A consumer cannot
validate against them.

## 5. Answers to the open questions

| Question | Recommendation |
|---|---|
| `groundwater level` or `groundwater level below ground surface`? | Calculate the depth below ground surface in the view (Section 4.1). Also send the measuring-point height as a second range if WeaverAPI needs to audit the calculation. |
| Pivot to Features? | No, not for this use. See Section 3.6. |
| Is `/manual_waterlevels` the correct id? | Yes. It agrees with the existing snake_case ids (`water_chemistry`). |
| One `/waterlevels` with two parameter names, or two collections? | Two collections. See Section 3.5. |

## 6. Example API contract

This is an example of the form of a contract. The values are examples.
Do not use them as the decision.

---

### Contract: `manual_waterlevels` collection

| Item | Value |
|---|---|
| Contract version | 1.0.0 |
| Status | Draft |
| Provider | OcotilloAPI |
| Consumers | WeaverAPI |
| Standard | OGC API - EDR 1.1, CoverageJSON 1.0, GeoJSON (RFC 7946) |
| Base path | `/ogcapi/collections/manual_waterlevels` |
| Authentication | None. Public data only. |

#### 6.1 Scope

1. The collection contains hand-measured groundwater levels only.
2. The collection does not contain transducer readings.
3. The collection contains wells only. It does not contain springs.
4. The collection contains a well only if the well is public.
5. The collection contains a reading only if the reading is public.
6. The collection does not contain readings with no value (for example, a dry
   well). *(Decision needed: send these as null with a reason?)*

#### 6.2 Versioning and change policy

1. The provider uses semantic versioning for this contract.
2. A new optional property is a minor change.
3. A removed or renamed property is a major change.
4. A change to a unit or a datum is a major change.
5. The provider tells all consumers 30 days before a major change.

#### 6.3 Endpoints

| Method | Path | Response type | Use |
|---|---|---|---|
| GET | `/locations` | GeoJSON FeatureCollection | Get all wells and their metadata. |
| GET | `/locations/{locId}` | CoverageJSON CoverageCollection | Get all readings for one well. |
| GET | `/cube?bbox=...` | CoverageJSON CoverageCollection | Get the readings for all wells in a box. |

Query parameters (all optional):

| Name | Type | Example | Rule |
|---|---|---|---|
| `datetime` | ISO 8601 instant or interval | `2020-01-01T00:00:00Z/..` | Filters on the observation time. `..` is open. |
| `bbox` | 4 numbers, CRS84 | `-107.0,33.0,-106.0,34.0` | Required for `/cube`. |
| `parameter-name` | string | `groundwater_level_below_ground_surface` | Only one parameter exists in 1.0.0. |
| `f` | string | `json` | Only `json` is supported. |

#### 6.4 Site (Feature) properties

| Field | Type | Null | Unit | Description |
|---|---|---|---|---|
| `id` | string | No | - | Ocotillo well id. Same value as the coverage `id` and as `{locId}`. |
| `geometry.coordinates` | [number, number] | No | degrees | Longitude, latitude. CRS84 (WGS84). |
| `properties.name` | string | No | - | Well name. |
| `properties.elevation` | number | No | m | Ground surface elevation. NAVD88. |
| `properties.well_depth` | number | Yes | ft | Depth of the well below ground surface. Null means unknown. |
| `properties.alternate_ids` | array of objects | No | - | Other ids for the well. Empty array if none. |
| `properties.alternate_ids[].id` | string | No | - | The other id. |
| `properties.alternate_ids[].authority` | string | No | - | The agency that gave the id (for example, `USGS`, `OSE POD`). |
| `properties.last_modified` | string (RFC 3339, UTC) | No | - | Last change to this well or to any of its readings. |

Note: one well can have more than one alternate id. A single
`alternate_id` field cannot hold them.

#### 6.5 Reading (Coverage) rules

1. The collection has one parameter:
   `groundwater_level_below_ground_surface`.
2. The unit is `ft`.
3. A positive value is below the ground surface. A negative value is above
   the ground surface (a flowing well).
4. The provider calculates the value as: measured depth below the measuring
   point, minus the measuring-point height.
5. If the measuring-point height is not known, the provider uses `0`
   (`docs/measuring-point-height-null-handling.md`).
6. The coverage `id` is the well `id`.
7. The `t` axis is in RFC 3339 format, in UTC, with a `Z` suffix.
8. The `t` axis is sorted from oldest to newest.
9. Each time occurs one time only. The `values` array has no null items.
10. The `shape` value is equal to the length of `t` and of `values`.

#### 6.6 Errors

| Status | When | Consumer action |
|---|---|---|
| 400 | A query parameter is not valid. | Correct the request. |
| 404 | `{locId}` does not exist, or it is not public. | Remove the well from the local list. |
| 204 | The query is valid but finds no readings. | Continue. This is not an error. |
| 413 | The query finds more than 50,000 readings. | Use a smaller `bbox` or `datetime`, or use `/locations/{locId}`. |
| 500, 503 | Server problem. | Try again after 60 s. Stop after 5 attempts. |

#### 6.7 Limits

1. Each data response contains a maximum of 50,000 readings.
2. A consumer must not send more than 5 requests each second.

#### 6.8 Example: `GET /locations`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "4182",
      "geometry": { "type": "Point", "coordinates": [-106.89123, 34.05871] },
      "properties": {
        "name": "SO-0245",
        "elevation": 1412.6,
        "well_depth": 310.0,
        "alternate_ids": [
          { "id": "340352106532801", "authority": "USGS" },
          { "id": "RG-01234", "authority": "OSE POD" }
        ],
        "last_modified": "2026-10-28T17:04:11Z"
      }
    },
    {
      "type": "Feature",
      "id": "4190",
      "geometry": { "type": "Point", "coordinates": [-106.90210, 34.06120] },
      "properties": {
        "name": "SO-0251",
        "elevation": 1409.1,
        "well_depth": null,
        "alternate_ids": [],
        "last_modified": "2025-03-14T21:40:00Z"
      }
    }
  ]
}
```

#### 6.9 Example: `GET /locations/4182?datetime=2024-01-01T00:00:00Z/..`

```json
{
  "type": "CoverageCollection",
  "domainType": "PointSeries",
  "parameters": {
    "groundwater_level_below_ground_surface": {
      "type": "Parameter",
      "description": {
        "en": "Depth from the ground surface down to the water table, measured by hand. Larger values mean the water table is further below the surface."
      },
      "observedProperty": {
        "id": "groundwater_level_below_ground_surface",
        "label": { "en": "Groundwater level below ground surface" }
      },
      "unit": { "symbol": "ft", "label": { "en": "feet" } }
    }
  },
  "referencing": [
    {
      "coordinates": ["x", "y"],
      "system": {
        "type": "GeographicCRS",
        "id": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
      }
    },
    {
      "coordinates": ["t"],
      "system": { "type": "TemporalRS", "calendar": "Gregorian" }
    }
  ],
  "coverages": [
    {
      "type": "Coverage",
      "id": "4182",
      "domain": {
        "type": "Domain",
        "domainType": "PointSeries",
        "axes": {
          "x": { "values": [-106.89123] },
          "y": { "values": [34.05871] },
          "t": {
            "values": [
              "2024-01-17T18:20:00Z",
              "2024-06-11T16:05:00Z",
              "2025-01-22T19:45:00Z"
            ]
          }
        }
      },
      "ranges": {
        "groundwater_level_below_ground_surface": {
          "type": "NdArray",
          "dataType": "float",
          "axisNames": ["t"],
          "shape": [3],
          "values": [142.31, 143.05, 142.88]
        }
      }
    }
  ]
}
```

Note: this example puts `referencing` on the collection, one time. CoverageJSON
permits this. It is optional. The current provider puts it on each coverage.

#### 6.10 Conformance tests

The provider runs these tests in CI. The consumer can run the same tests.

1. Each feature `id` is a string.
2. Each coverage `id` is equal to one feature `id`.
3. For each range, `shape[0]` is equal to the length of `values` and of `t`.
4. The `t` values are sorted and unique.
5. A request that finds more than the limit gets 413.
6. The `/locations` list does not contain a well that is not public.
