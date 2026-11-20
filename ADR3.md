# ADR3: Serving Water-Level and Water-Chemistry Data via OGC API - EDR

## Status

Accepted for `manual_waterlevels` and `water_chemistry`; the transducer
collection (`continuous_waterlevels`) is pending. See
[Update 2026-11-20](#update-2026-11-20).

## Summary

This ADR proposes adopting the **OGC API - Environmental Data Retrieval (EDR)**
standard as the delivery interface for the Bureau's core observational
datasets: groundwater-level measurements below ground surface (manual readings)
and water-chemistry analyses.

These datasets are already modeled in this repository as point-located,
time-stamped, parameterized observations tied to a `Location` geometry. That
shape is exactly what EDR was designed to serve. Adopting EDR gives external
consumers (agencies, researchers, dashboards, other data systems) a single,
standardized, spatiotemporal query interface instead of bespoke per-dataset
REST endpoints, and aligns the project's stated goal of a unified,
interoperable data system (see [ADR1](ADR1.md)).

The recommendation is to **add EDR collections to the pygeoapi service that is
already mounted at `/ogcapi`** (see [core/pygeoapi.py](core/pygeoapi.py)),
backing them with read-only, publication-filtered database views — the same
pattern the existing OGC API - Features collections already use. The FastAPI
application remains the system of record and the write/QC path.

## Context

### What EDR is

OGC API - EDR is an OpenAPI-based standard for retrieving environmental data at
a position, within an area, at named locations, or over a time span. A consumer
does not need to understand the underlying storage. They ask questions like:

- "Give me depth-to-water below ground surface at this well, from 2020 to 2024."
- "Give me all pH analyses within this polygon."
- **Pending:** "List the transducer deployments recording at this well."

EDR standardizes these as a small set of **query patterns** over named
**collections**:

- `/position` — data at a point (optionally with a datetime range)
- `/area` — data within a polygon
- `/radius` — data within a distance of a point
- `/locations` — data at named, discrete sites (the natural fit for wells)
- `/instances` — sub-series of a collection (the natural fit for a transducer
  deployment)
- `/cube` — data within a bounding box
- `/trajectory`, `/corridor` — additional patterns we can defer

Each collection advertises its **parameter-names** (the measured variables),
its spatial and temporal extents, and its output formats. EDR responses are
**CoverageJSON**.

### The existing OGC surface

pygeoapi is **already running** in this application, mounted at `/ogcapi` by
[core/pygeoapi.py](core/pygeoapi.py). It currently serves OGC API - **Features**
collections (`water_wells`, `springs`, `perennial_streams`, …), each backed by
an `ogc_<id>` PostgreSQL view filtered to `release_status = 'public'`. So the
standards server, the publication-gating pattern, and the config-generation
machinery all exist today.

What is missing is **EDR**. Features answers "where are the wells?" and returns
point geometries with summary attributes; it does not answer "what is the
depth-to-water time series at this well between two dates?" as a coverage. EDR
is the query model built for that, and this ADR adds it alongside the existing
Features collections on the same mount.

### How this maps onto the actual data model

The mapping is close to one-to-one, which is the main reason EDR is attractive
here rather than in the abstract:

| EDR concept          | This repository (staging schema)                                                                 |
|----------------------|--------------------------------------------------------------------------------------------------|
| Location / platform  | `Thing` (`thing_type = "water well"`) sited via `Location.point` ([db/thing.py](db/thing.py), [db/location.py](db/location.py)) |
| `manual_waterlevels` | `Observation` where `parameter` = "groundwater level" ([db/observation.py](db/observation.py)) |
| `continuous_waterlevels` **(pending)** | `TransducerObservation`, grouped by `TransducerObservationBlock`, per `Deployment` ([db/transducer.py](db/transducer.py), [db/deployment.py](db/deployment.py)) |
| `water_chemistry` collection | `Observation` tied to a `Sample`, keyed by `Parameter` analyte ([db/sample.py](db/sample.py), [db/parameter.py](db/parameter.py)) |
| EDR instance         | `Deployment` — a `Sensor` install bounded by `installation_date`/`removal_date` ([db/sensor.py](db/sensor.py)) |
| parameter-names      | A name column in the backing view (e.g. "groundwater level below ground surface", "pH", chemistry analytes) |
| datetime axis        | `Observation.observation_datetime`; `TransducerObservation.observation_datetime` |
| result value + units | `Observation.value` / `TransducerObservation.value`; units from a unit column in the backing view (e.g. "ft") |
| publication gate     | `release_status` (`ReleaseMixin`), exposed only where `= 'public'` via `ogc_*` views |

Water levels are a depth-to-water time series per well, published with a
companion `groundwater level reason` qualifier parameter. Water chemistry is
multi-parameter: a `Sample` collected at a well has many `Observation` rows,
each carrying one `Parameter` analyte, a `value`, an `analysis_method`, and a
unit. Each water chemistry observation will have a companion qualifier, too.
Both fold cleanly into EDR collections whose primary query pattern is
`/locations` (discrete wells) with `/area`, `/position` and `/cube` as either
primary patterns or secondary for `/instances`.

### Transducer (instrument) observations

Groundwater levels arrive two ways, from two different tables:

- **Manual measurements** — `Observation` rows (parameter "groundwater level"),
  optionally linked to the `Sensor`/`Sample`/`AnalysisMethod` used; periodic
  hand readings.
- **Transducer observations (pending)** — `TransducerObservation` rows:
  continuous, high-frequency readings from a deployed pressure transducer or
  logger. Each row references a `Deployment` (`deployment_id`) and a
  `Parameter`, and is grouped for review by a `TransducerObservationBlock`
  (`start_datetime`, `end_datetime`, `review_status`, `reviewer`). A
  `Deployment` records the `Sensor`, `installation_date`, `removal_date`, and
  `recording_interval`.

The two differ mainly in **density and provenance**, not in physical quantity —
both are depth-to-water. EDR models this cleanly with **instances**: each
transducer `Deployment` becomes an EDR *instance* of the
`continuous_waterlevels` collection. That preserves per-deployment temporal
extent (`installation_date`/`removal_date`), resolution (`recording_interval`),
and instrument metadata (`Sensor.model`, `Sensor.serial_no`). Consumers can
query a well's whole continuous series or drill into one deployment.

## Decision Drivers

- **Interoperability** — a published OGC standard beats bespoke endpoints for
  cross-agency and cross-system consumption. Directly serves the ADR1 goal.
- **Fit to data** — the data is already point + time + parameter; EDR is built
  for exactly that. Minimal impedance mismatch.
- **Reuse existing infrastructure** — pygeoapi, the `/ogcapi` mount, the
  `ogc_*` publication-view pattern, and the config generator are already in
  production for Features. EDR extends them rather than standing up something new.
- **Separation of concerns** — keep FastAPI as the authoritative write/QC path;
  expose a read-only, cacheable query surface for delivery.
- **Incremental adoption** — start with two collections and the most useful
  query patterns; expand later without breaking the contract.

## Considered Options

### Option A — add EDR collections to the existing pygeoapi mount (recommended)

Extend [core/pygeoapi.py](core/pygeoapi.py) with EDR collection definitions
(alongside `THING_COLLECTIONS`) for `manual_waterlevels` and `water_chemistry`,
each using an EDR provider over publication-filtered `ogc_*` views/materialized
views. Same server, same mount, same gating pattern as Features today.

- **Pros:** standards-compliant EDR (query patterns, CoverageJSON, OpenAPI,
  conformance) with no new service; reuses the deployment, config generation,
  and `release_status='public'` view convention already in place; keeps the
  write path untouched.
- **Cons:** pygeoapi's built-in EDR providers target gridded/xarray data, so an
  observational **PostgreSQL-backed EDR provider** (or a thin custom provider)
  is needed to serve point/time-series coverages from the relational schema;
  bridging `Thing`/`Observation`/`TransducerObservation`/`Deployment` into
  EDR collections and instances requires purpose-built read views.

### Option B — native EDR endpoints inside the FastAPI app

Implement the EDR query patterns directly as FastAPI routes and hand-roll
CoverageJSON serialization.

- **Pros:** full control over query translation; reuse of existing SQLAlchemy
  models and helpers; no dependence on pygeoapi's EDR provider maturity.
- **Cons:** reimplements a spec pygeoapi already largely provides; ongoing
  burden to stay conformant (query-parameter parsing, CoverageJSON, OpenAPI /
  conformance docs, edge cases); a second OGC surface to keep consistent with
  the `/ogcapi` Features mount. Highest long-term maintenance cost.

### Option C — OGC API - Features only

Publish observations as feature collections and let consumers filter.

- **Pros:** already deployed; no new work.
- **Cons:** Features is not EDR — no position/area/time query semantics, no
  parameter/coverage model, no CoverageJSON. Poor fit for time-series retrieval;
  pushes filtering and reshaping onto every client. Rejected as the primary
  delivery mechanism for observations.

### Option D — do nothing (keep bespoke REST)

Continue serving observations through the existing FastAPI observation routes.

- **Pros:** zero new work.
- **Cons:** no standardization, no interoperability, every consumer integrates
  against a custom contract. Fails the ADR1 unification goal.

## Decision

Adopt **Option A**: expose water-level and water-chemistry data through **OGC
API - EDR collections added to the existing pygeoapi `/ogcapi` mount**, backed
by read-only, publication-filtered database views.

Scope for the first iteration:

- **Collections:** `manual_waterlevels` and `water_chemistry`,
  registered next to the current Features collections in
  [core/pygeoapi.py](core/pygeoapi.py).
- **Backing views:** `ogc_manual_waterlevels` and `ogc_water_chemistry`
  (Alembic-managed, following the existing `ogc_<id>` convention), each
  filtered to `release_status = 'public'`.
- **Query patterns:** `/locations` to get sites, `/locations/{lodId}` to
  get time series data at a site, plus `/area`, `/position` and
  `/cube` to get site series for sites within a defined bound, each with an
  optional `datetime` range and `parameter-name` comma-separated list on every
  collection, plus `/collections` metadata.
  - `/radius`, `/trajectory` and `/corridor` are not served.
  - **Pending with `continuous_waterlevels`:** `/instances` for transducer
  deployments.
- **Parameter-names:** read from a name column in the backing view
  (`parameter_columns` in [core/pygeoapi.py](core/pygeoapi.py)).
  `manual_waterlevels` exposes "groundwater level below ground surface" and
  its qualifier, "groundwater level reason". `water_chemistry` exposes one
  parameter per analyte present and an associated qualifier.
- **Output format:** CoverageJSON.
- **CRS / units:** CRS84 / EPSG:4326 (consistent with `Location.point` and the
  bbox the mount already advertises); units declared per parameter from
  a pre-defined unit column in the backing view.
- **Boundary:** EDR is read-only. All writes, validation, and QC stay in the
  FastAPI application. Only `release_status = 'public'` records are published,
  enforced at the `ogc_*` view layer so it cannot be bypassed.
- **Water wells only:** `manual_waterlevels` publishes readings only from
  things with `thing_type = 'water well'`.

FastAPI remains the system of record. pygeoapi owns the OGC read surface —
Features today, plus EDR after this ADR.

## Consequences

### Positive

- One standardized, self-describing spatiotemporal interface for the two most
  requested observational datasets, on infrastructure already in production.
- Consumers use off-the-shelf EDR clients; no custom SDK required.
- Publication gating reuses the proven `ogc_*` / `release_status='public'`
  view pattern, so public/private handling is consistent with Features.
- Clean separation: authoritative write path (FastAPI) vs. cacheable read path
  (pygeoapi/EDR), which also reinforces the read/write split discussed in ADR2.
- Extensible: further collections (e.g. geothermal, geochronology) can follow
  the same pattern later.

### Negative / costs

- A custom PostgreSQL-backed EDR provider was required, since pygeoapi's
  bundled EDR providers target gridded data rather than relational
  point/time-series (`StationEDRProvider`, [core/edr_provider.py](core/edr_provider.py)).
- Purpose-built `ogc_*` read views/materialized views are needed to bridge the
  normalized schema (`Thing` → `Observation` / `TransducerObservation` /
  `Deployment`; `Sample` → `Observation`) into EDR collections and instances.
- More surface area in the generated pygeoapi config and its Alembic-managed
  backing views to maintain as the schema evolves.

### Risks and open questions

- **EDR provider choice** — **Decided:** a thin custom provider,
  `StationEDRProvider` ([core/edr_provider.py](core/edr_provider.py)), emits
  CoverageJSON from the `ogc_*` views.
- **Schema bridging** — `Thing → Observation` and `Sample → Observation` are
  joins, not flat tables. `ogc_manual_waterlevels` and `ogc_water_chemistry`
  are plain views; revisit materialized views for the dense transducer data.
- **Chemistry parameter cardinality** — the number of `Parameter` analytes with
  chemistry `Observation`s drives the parameter list; confirm it is bounded and
  lexicon-governed before exposing every analyte as a parameter-name.
- **Transducer volume and cadence (pending)** — continuous
  `TransducerObservation` series can be large and dense. Confirm response
  paging/limits, decide default vs. maximum datetime windows, and consider
  server-side decimation/aggregation for wide `/cube` queries. High-frequency
  reads are the strongest case for caching.
- **Manual vs. transducer disambiguation** — manual readings come from
  `Observation`, transducer readings from `TransducerObservation`. **Decided:**
  they are published as two collections, `manual_waterlevels` now and
  `continuous_waterlevels` later. Instances isolate a single `Deployment`
  within the continuous collection.
- **Depth-to-water and `measuring_point_height`** — **Decided:** depth below
  ground surface is `Observation.value` minus `measuring_point_height`, the
  same convention as the Features water-level layers. A null measuring point
  height counts as 0 (see
  [docs/measuring-point-height-null-handling.md](docs/measuring-point-height-null-handling.md)).
  A reading already in `ftbgs` has no measuring point height subtracted.
- **Units and vocabularies** — each view declares its parameter units in a unit
  column. `manual_waterlevels` always publishes feet: readings in `m` are
  converted, and a reading in any non-length unit is published with a null
  level and a reason. Parameter definitions come from the lexicon, so the
  standard's parameter metadata stays truthful.

## Acceptance Criteria

- `GET /ogcapi/collections` lists `manual_waterlevels` and `water_chemistry`
  alongside the existing Features collections, with correct spatial extents,
  temporal extents, and parameter-names.
- `GET /ogcapi/collections/manual_waterlevels/locations/{locId}?datetime=...`
  returns CoverageJSON depth-to-water below ground surface for a real well over
  a bounded time range, covering only manual readings.
- `GET /ogcapi/collections/manual_waterlevels/instances` returns an empty list,
  since manual measurements have no instances.
  - **Pending for transducer data:** `/instances` lists each transducer
    deployment as an EDR instance. (Note: pygeoapi 0.23.4's Starlette app routes
    the generic `.../area|locations|...` query patterns ahead of their
    `.../instances/{instanceId}/...` counterparts because `collection_id` is matched as a
    greedy path, so instance-scoped *data* queries are not currently served;
    instance discovery is. Tracked as a follow-up / upstream limitation.)
- `GET /ogcapi/collections/water_chemistry/area?coords=...&parameter-name=...`
  returns the expected analyses for a polygon, filtered by analyte.
- Only `release_status = 'public'` records appear in EDR responses.
- `GET /ogcapi/conformance` advertises the OGC API - EDR conformance classes.
- The EDR collections pass a read-only smoke test against production-shaped data.

These criteria are pinned as an executable spec in
[tests/features/edr-water-data.feature](tests/features/edr-water-data.feature).

## Notes

- Related: [ADR1](ADR1.md) (unification goal) and ADR2 (API concurrency — the
  read/write split here reinforces that direction).
- This ADR decides direction and boundaries, not a file-by-file implementation
  plan. The column-level contract for `manual_waterlevels` lives in
  [docs/ogc-waterlevels-data-contract.md](docs/ogc-waterlevels-data-contract.md).

## Update 2026-11-20

This ADR originally proposed a single `waterlevels` collection serving a merged
time series of manual and transducer water levels. After the first
implementation, manual and transducer readings were split into separate
collections and views: `manual_waterlevels` now, `continuous_waterlevels`
later. These are two distinct datasets that, while complimentary, should be seen
as different. Because of the sheer number of continuous water levels serving
both of them together would have put a large strain on resources. Furthermore,
it would have been quite difficult to distinguish the two as different parameter-names
since they measure the same thing, but in different ways. The transducer material
above is marked "pending" until that collection is built.
