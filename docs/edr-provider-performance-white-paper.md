---
generated-by: claude-opus-5-5
generated-on: 2026-11-06
prompted-by: jakeross
language-standard: ASD-STE100 (Simplified Technical English)
---

# White Paper: Memory Use and Performance of the EDR Provider

## 1. Summary

The OGC API - EDR provider (`core/edr_provider.py`) uses too much memory when
it reads water levels. A large query can stop a Gunicorn worker in production.

This paper gives the causes and a plan to correct them. The plan has three
phases:

1. **Phase 1** changes only the provider. It puts a limit on the number of rows
   in one response and reads the rows as a stream. This stops the memory
   failures. No database migration is necessary.
2. **Phase 2** moves work into PostgreSQL. A new station view and SQL
   aggregation make the queries faster and the responses smaller.
3. **Phase 3** adds a default time window and optional decimation. These items
   change the behavior of the API, so they need a decision first.

The team accepted these decisions:

- A request that is larger than the row limit gets an HTTP 400 response. The
  provider does not send a truncated response.
- The row limit is 250,000 rows after Phase 1b is complete.

This paper adds one condition to the second decision. Until Phase 1b is
complete, the limit must be 50,000 rows. Section 4 gives the reason.

## 2. Background

ADR3 added two EDR collections to the `/ogcapi` mount: `waterlevels` and
`water_chemistry`. The internal mount has the same two collections. A custom
pygeoapi provider, `WaterEDRProvider`, serves them as CoverageJSON.

The `waterlevels` collection reads the `ogc_waterlevels` view. The current
definition of this view is in migration `baba91fe5e83`. The view is a
`UNION ALL` of two sources:

- Manual measurements. These come from `observation` through `sample`,
  `field_activity`, and `field_event` to `thing`.
- Transducer readings. These come from `transducer_observation` through
  `deployment` to `thing`.

The view is a plain view, not a materialized view. Each query on the view reads
the base tables.

Transducer data is dense. For example, a transducer that logs at a 15-minute
interval makes 35,040 readings each year. A well with 10 years of such data has
approximately 350,000 readings.

ADR3 identified this risk in its open questions ("Transducer volume and
cadence"). ADR3 did not set a response limit.

## 3. Causes of the Problem

### 3.1 The provider keeps all rows in memory, more than one time

The `_fetch` method calls `cursor.fetchall()` with `RealDictCursor`. This makes
one Python dictionary for each reading. Each dictionary has eight keys, a
`datetime` object, a float, and three strings. We estimate approximately 1 KB
for each row. Section 7 tells how to measure the true value.

After `_fetch`, the `_coverage_collection` method makes more copies of the
data:

- a list of rows for each station (`stations`)
- a list of rows for each parameter (`by_param`)
- a sorted set of all timestamps (`times`)
- a dictionary from timestamp to index (`t_index`)
- an ISO 8601 string for each timestamp

Then pygeoapi serializes the full result to a JSON string. Thus, at the
highest point, the worker holds the data in three or more forms at the same
time.

### 3.2 There is no limit on the size of a response

These requests return all matching rows:

- `/cube`, `/area`, or `/position` without a `datetime` parameter
- `/locations/{id}` for a well with many years of transducer data

One such request can return millions of rows.

### 3.3 Each request reads the full view for metadata

We think that pygeoapi makes a new provider object for each request. Section 10
tells how to verify this. If this is correct, each request does these steps:

1. The constructor calls `get_fields()`. This runs `SELECT DISTINCT
   parameter_name, unit` on the full view. This query reads all of
   `transducer_observation`.
2. The constructor calls `_has_column()`. This is one more query.
3. Each query opens a new database connection and then closes it.

Other methods also read the full view:

- `instance(id)` calls `instances()`. This reads all distinct `deployment_id`
  values to examine one identifier.
- The `/locations` list runs `SELECT DISTINCT thing_id, station_name,
  longitude, latitude` on all readings.

### 3.4 Spatial filters do not use the spatial index

The `bbox` filter compares the `longitude` and `latitude` columns of the view.
The WKT filter calls `ST_MakePoint()` for each row. The view calculates these
columns with `ST_X()` and `ST_Y()`. Thus, PostgreSQL cannot use the GiST index
on `location.point`. It must examine each reading.

## 4. Memory Budget in Production

Production runs on App Engine, instance class F4_1G (2 GB). Gunicorn starts 8
workers (`gunicorn -w 8`, in `CD_production.yml`). Thus, each worker has
approximately 250 MB. The application code uses a part of this memory before
the worker gets a request. Refer to `docs/app-engine-oom-instance-churn.md`.

When a worker uses too much memory, App Engine stops the process. The user gets
an error, and the next request must wait for a new worker to load.

At approximately 1 KB for each row, 250,000 rows use approximately 250 MB in
`fetchall()` alone. This is more than the budget of one worker. For this
reason:

- **Before Phase 1b**, the row limit must be 50,000 rows.
- **After Phase 1b**, each row uses approximately 100 bytes. Thus, 250,000 rows
  use approximately 25 MB, plus the JSON output. The limit can then increase to
  250,000 rows.

These values are estimates. Use the measurement in Section 7 to replace them
with measured values.

## 5. Recommendations

### 5.1 Phase 1: Stop the Memory Failures (Provider Only)

Phase 1 changes only `core/edr_provider.py` and its tests. It does not change
the API contract, except for the new HTTP 400 response.

#### Phase 1a: Add a row limit

1. Add a `max_rows` setting. Read it from the provider definition. Let an
   environment variable override it. Set the default to 50,000.
2. In each data query, request `max_rows + 1` rows (`LIMIT max_rows + 1`).
3. If the query returns more than `max_rows` rows, raise
   `ProviderQueryError`. pygeoapi then sends HTTP 400.
4. Put a clear message in the error. Tell the user to use a shorter `datetime`
   interval or a smaller area. Include the limit value in the message.

Do not send a truncated response. A truncated hydrograph looks complete but
is not. The user cannot see that data is missing.

Phase 1a is small. Release it as a separate pull request, before the other
items.

#### Phase 1b: Read the rows as a stream

1. Use a named (server-side) cursor. Set `itersize` to a few thousand rows.
2. Use a tuple cursor, not `RealDictCursor`.
3. Format the timestamps in SQL. Use
   `to_char(datetime, 'YYYY-MM-DD"T"HH24:MI:SSOF')`. Then Python does not make
   `datetime` objects.
4. The query sorts the rows by `thing_id`, `parameter_name`, and `datetime`.
   Use this order to build each coverage in one pass:
   - Add each value and each timestamp to the lists for the current station.
   - When `thing_id` changes, complete the coverage for the last station.
5. Remove the `stations`, `by_param`, and `t_index` copies.
6. The `waterlevels` collection has one parameter. Thus, the row order is the
   time axis. Keep the union-of-timestamps logic only for collections with
   more than one parameter, for example `water_chemistry`.
7. When Phase 1b is complete, increase the default `max_rows` to 250,000.

The CoverageJSON output must not change. A test must compare the old output
and the new output for the same rows.

#### Phase 1c: Keep metadata between requests

1. Keep `_fields`, `_has_thing_type`, and the list of instances in a
   module-level cache. Use the table name as the key.
2. Give each entry a time to live (TTL) of approximately 10 minutes.
3. Change `instance(id)` to one query:
   `SELECT EXISTS (SELECT 1 FROM <view> WHERE deployment_id = %s)`.

Phase 1c is necessary only if pygeoapi makes a new provider for each request.
Verify this first (Section 10).

#### Phase 1d: Use a connection pool

Use one module-level `psycopg2.pool.ThreadedConnectionPool` with a small
maximum size. Do not open a new connection for each query.

### 5.2 Phase 2: Move the Work into PostgreSQL (Migration Necessary)

#### Phase 2a: Add a station view

1. Add the view `ogc_waterlevel_stations`. It has one row for each published
   well that has readings. The columns are `thing_id`, `name`, `longitude`,
   `latitude`, and `geom`.
2. Add the same view for the internal mount (`ogc_internal_waterlevel_stations`).
   Apply the same release rules as the readings view on each mount.
3. Use the station view for the `/locations` list.
4. For `bbox` and WKT queries, do two steps:
   1. Find the matching `thing_id` values in the station view. Use
      `ST_Intersects(geom, ...)`. This query can use the GiST index.
   2. Read the readings with `thing_id = ANY(%s)`. PostgreSQL pushes this
      filter into both parts of the `UNION ALL`.

Phase 2a also corrects the slow `/locations` list and the slow spatial
filters. Start Phase 2 with this item.

A materialized view is faster but must be refreshed. Use a plain view first.
Change to a materialized view only if a measurement shows that it is
necessary. The pg_cron refresh in `docs/pg_cron-nightly-refresh.md` is
available for this.

#### Phase 2b: Aggregate in SQL

1. Return one row for each station and parameter. Use
   `array_agg(datetime ORDER BY datetime)` and
   `array_agg(value ORDER BY datetime)`.
2. Python then gets two arrays for each station, not one object for each
   reading.
3. If pygeoapi accepts a JSON string from a provider (Section 10), build the
   full CoverageJSON in SQL with `json_build_object`. Then send the string
   without a change.

Apply the row limit before the aggregation. Use a count, or `LIMIT` in a
subquery.

#### Phase 2c: Examine the query plans

Run `EXPLAIN (ANALYZE, BUFFERS)` on data that has the same size as production.
Examine these items:

- The transducer part must use the unique index
  `uq_transducer_observation_deployment_parameter_datetime` for deployment,
  parameter, and time filters.
- The manual part joins `observation`, `sample`, `field_activity`,
  `field_event`, and `thing`. It can need an index on
  `observation (parameter_id, observation_datetime)`. A partial index for the
  groundwater level parameter is also possible.

Add an index only if the plan shows that it is necessary.

#### Phase 2d: Read the fields from the parameter table

Change `get_fields()` to read from `parameter`. Do not use `SELECT DISTINCT` on
the readings view.

### 5.3 Phase 3: Optional Items That Need a Decision

These items change the behavior of the API. Get a decision before you start
them.

| Item | Description | Decision necessary |
|---|---|---|
| Default time window | If `/area` or `/cube` has no `datetime`, refuse the request or use the last N years. | Yes. This changes the API for clients. |
| Decimation | Return daily mean values for long intervals. Use an optional parameter, for example `resolution=daily`. | Yes. This is not in the EDR standard. Amend ADR3. |
| Paging | If pygeoapi 0.24 sends `limit` and `offset` to EDR providers, return pages of coverages. | Verify pygeoapi first. |

## 6. Decisions

| Decision | Status |
|---|---|
| A request that is larger than the limit gets HTTP 400, not a truncated response. | Accepted |
| The row limit is 250,000 rows after Phase 1b. | Accepted |
| The row limit is 50,000 rows before Phase 1b. | Recommended in this paper (Section 4) |
| The phase order is 1a, then 1b to 1d, then 2, then 3. | Accepted |
| Phase 3 items need a separate decision. | Open |

## 7. Tests and Measurement

### 7.1 Unit tests

Add these tests to `tests/test_edr_provider.py`:

1. A query with more rows than `max_rows` gives HTTP 400, not HTTP 500.
2. The streamed output is the same as the current output. Use more than one
   station and more than one parameter.
3. A second provider object uses the cached metadata. It does not run the
   metadata queries again.
4. `instance(id)` runs one `EXISTS` query.

### 7.2 Memory measurement

1. Write a script that adds approximately 1,000,000 rows to
   `transducer_observation` in the test database.
2. Measure the peak memory of the process (`tracemalloc`, or
   `resource.getrusage`). Measure these requests:
   - `/cube` for all of New Mexico
   - `/locations/{id}` for the well with the most readings
3. Do the measurement before the work and after each phase.
4. Record the measured memory for each row. Use it to replace the estimates in
   Section 4.

### 7.3 Public and internal views

Each change to a public view needs the same change to its internal view.
Migration `2d3c3a268652` shows the pattern.

## 8. Sequence of Work

| Step | Work | Pull request | Migration |
|---|---|---|---|
| 1 | Phase 1a: row limit, 50,000 rows | Separate | No |
| 2 | Phase 1b to 1d: stream, cache, pool; limit to 250,000 rows | One | No |
| 3 | Phase 2a: station view and two-step spatial query | One | Yes |
| 4 | Phase 2b to 2d: SQL aggregation, indexes, fields | One or more | Possible |
| 5 | Phase 3 | After a decision | Possible |

## 9. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| A long-term transducer well has more readings than the limit. | `/locations/{id}` without `datetime` gives HTTP 400 for that well. | The error message tells the user to use a `datetime` interval. Phase 3 decimation gives a full-period view. The limit is a setting, so the team can change it. |
| The cache keeps old metadata. | A new parameter or deployment does not show for up to one TTL. | Keep the TTL short (approximately 10 minutes). |
| A named cursor keeps a transaction open. | A slow client keeps a database connection busy. | Set a statement timeout on the provider connection. |
| The streamed output is different from the old output. | Clients get changed CoverageJSON. | The comparison test in Section 7.1 prevents this. |
| A materialized station view is not current. | A new well does not show until the next refresh. | Use a plain view first (Section 5.2). |

## 10. Items to Verify

pygeoapi is not installed in the environment where this paper was written.
Verify these items in pygeoapi 0.24.0 before Phase 1c and Phase 2b:

1. Does pygeoapi call `load_plugin()` for each EDR request? If yes, Phase 1c is
   necessary.
2. Can an EDR provider return a JSON string, not a dictionary? If yes, Phase 2b
   can build the full response in SQL.
3. Does pygeoapi send `limit` and `offset` to EDR query methods? If yes, paging
   is possible in Phase 3.

## 11. References

- `ADR3.md`: EDR adoption, and the open question "Transducer volume and
  cadence"
- `core/edr_provider.py`: the provider
- `core/pygeoapi.py`: `EDR_COLLECTIONS` and `_edr_collections_block`
- `alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py`: the
  current `ogc_waterlevels` view
- `alembic/versions/2d3c3a268652_create_internal_ogc_views.py`: the internal
  views
- `db/transducer.py`: `TransducerObservation` and its unique constraint
- `docs/app-engine-oom-instance-churn.md`: instance class and worker count in
  production
- `docs/pg_cron-nightly-refresh.md`: refresh of materialized views
