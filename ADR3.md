# ADR3: Serving Water-Level and Water-Chemistry Data via OGC API - EDR

## Status

Proposed.

## Summary

This ADR proposes adopting the **OGC API - Environmental Data Retrieval (EDR)**
standard as the public delivery interface for the Bureau's core observational
datasets: groundwater-level measurements (both manual readings and
instrument/transducer time series) and water-chemistry analyses.

Both datasets are already modeled in this repository as point-located,
time-stamped, parameterized observations tied to a `SampleLocation` geometry.
That shape is exactly what EDR was designed to serve. Adopting EDR gives
external consumers (agencies, researchers, dashboards, other data systems) a
single, standardized, spatiotemporal query interface instead of bespoke
per-dataset REST endpoints, and aligns the project's stated goal of a unified,
interoperable data system (see [ADR1](ADR1.md)).

The recommendation is to expose EDR as a **read-only query facade layered over
the existing PostgreSQL/PostGIS database**, keeping the FastAPI application as
the system of record and write path.

## Context

### What EDR is

OGC API - EDR is an OpenAPI-based standard for retrieving environmental data at
a position, within an area, along a trajectory, or over a time span. A consumer
does not need to understand the underlying storage. They ask questions like:

- "Give me depth-to-water at this point, from 2020 to 2024."
- "Give me all nitrate analyses within this polygon."
- "List the locations that have chloride data."

EDR standardizes these as a small set of **query patterns** over named
**collections**:

- `/position` — data at a point (optionally with a datetime range)
- `/area` — data within a polygon
- `/radius` — data within a distance of a point
- `/locations` — data at named, discrete sites (the natural fit for wells)
- `/items` — direct access to individual features
- `/cube`, `/trajectory`, `/corridor` — additional patterns we can defer

Each collection advertises its **parameter-names** (the measured variables),
its spatial and temporal extents, and its output formats. Responses are
typically **CoverageJSON** or GeoJSON.

### How this maps onto the existing data model

The mapping is close to one-to-one, which is the main reason EDR is attractive
here rather than in the abstract:

| EDR concept          | This repository                                                                        |
|----------------------|----------------------------------------------------------------------------------------|
| Location / platform  | `Well` → `SampleLocation` (`Geometry(POINT, srid=4326)` in [db/base.py](db/base.py))   |
| `waterlevels` collection | `GroundwaterLevelObservation` via `WellTimeseries` ([db/timeseries.py](db/timeseries.py)) |
| EDR instance         | `Equipment` deployment — the transducer/logger recording a series ([db/base.py](db/base.py)) |
| `water-chemistry` collection | `WaterChemistryAnalysis` via `WaterChemistryAnalysisSet` ([db/chemistry.py](db/chemistry.py)) |
| parameter-names      | depth-to-water (`value`/`unit`, default `ftbgs`); chemistry `analyte` values           |
| datetime axis        | `GroundwaterLevelObservation.timestamp`; `WaterChemistryAnalysis.analysis_timestamp`   |
| result value + units | `value`, `unit` (unit already normalized against `lexicon_term`)                       |

Water levels are a single-parameter (depth-to-water) time series per well. Water
chemistry is a multi-parameter set keyed by `analyte`, where each
`WaterChemistryAnalysisSet` shares a `collection_timestamp` and each child
`WaterChemistryAnalysis` carries its own `analyte`, `value`, `unit`,
`uncertainty`, and `method`. Both fold cleanly into EDR collections whose
primary query pattern is `/locations` (discrete wells) with `/area` and
`/radius` as secondary patterns.

### Transducer (instrument) observations

Groundwater levels arrive two ways, and both live in the same
`GroundwaterLevelObservation` table:

- **Manual measurements** — periodic hand readings, no instrument attached.
- **Transducer observations** — continuous, high-frequency readings from a
  deployed pressure transducer or data logger. These are distinguished by a
  non-null `WellTimeseries.equipment_id` pointing at an `Equipment` row whose
  `equipment_type` is a transducer/logger, with `recording_interval` (cadence),
  `date_installed`, and `date_removed` bounding the deployment.

The two differ mainly in **density and provenance**, not in physical quantity —
both are depth-to-water. EDR models this cleanly with **instances**: each
transducer deployment (`Equipment` bounded by install/removal dates) becomes an
EDR *instance* of the `waterlevels` collection. That preserves per-deployment
temporal extent, resolution (`recording_interval`), and instrument metadata
(`model`, `serial_no`) while keeping a single collection and parameter-name.
Consumers can query the whole well series or drill into one instrument
deployment. The dense transducer axis is also the primary motivation for
supporting the `/cube` and datetime-ranged `/position` patterns, not just
`/locations`.

### Why now

This branch introduces GeoServer as spatial infrastructure (see
`geoserver_iac/`). GeoServer covers WMS, WFS, and OGC API - Features well, but
**GeoServer does not implement OGC API - EDR**. Feature access alone does not
give consumers the position/area/time query semantics that observational data
needs. This ADR fills that gap and clarifies the division of labor between
GeoServer (features, maps) and the EDR facade (observations, time series).

## Decision Drivers

- **Interoperability** — a published OGC standard beats bespoke endpoints for
  cross-agency and cross-system consumption. Directly serves the ADR1 goal.
- **Fit to data** — the data is already point + time + parameter; EDR is built
  for exactly that. Minimal impedance mismatch.
- **Separation of concerns** — keep FastAPI as the authoritative write/QC path;
  expose a read-only, cacheable query surface for delivery.
- **Standards, not lock-in** — EDR is client-agnostic; any EDR client works.
- **Incremental adoption** — start with two collections and the two most useful
  query patterns; expand later without breaking the contract.

## Considered Options

### Option A — pygeoapi as an EDR facade over PostgreSQL/PostGIS (recommended)

Run [pygeoapi](https://pygeoapi.io/) as a separate read-only service configured
with two EDR collections backed by the existing database (via custom EDR
providers, or SQL views shaped for pygeoapi's providers). pygeoapi is a
reference implementation of OGC API - EDR and already appears transitively in
the environment.

- **Pros:** standards-compliant EDR out of the box (query patterns,
  CoverageJSON, OpenAPI, conformance) with little bespoke protocol code; keeps
  the write path untouched; deployable alongside GeoServer as another
  read service.
- **Cons:** a second service and config surface to operate; custom providers
  needed to bridge the normalized schema (well → timeseries → observation) into
  EDR's collection/parameter model; two mental models (FastAPI + pygeoapi).

### Option B — native EDR endpoints inside the existing FastAPI app

Implement the EDR query patterns directly as FastAPI routes and hand-roll
CoverageJSON serialization.

- **Pros:** one service, one deployment, one auth story; full control over
  query translation and reuse of existing SQLAlchemy models and helpers.
- **Cons:** we reimplement a spec that already has a reference implementation;
  ongoing burden to stay conformant (query-parameter parsing, CoverageJSON,
  OpenAPI/conformance docs, edge cases). Highest long-term maintenance cost.

### Option C — GeoServer only (OGC API - Features)

Publish wells and observations as feature collections and let consumers filter.

- **Pros:** already on this branch; no new service.
- **Cons:** Features is not EDR. No position/area/time query semantics, no
  parameter/coverage model, no CoverageJSON. Poor fit for time-series retrieval;
  pushes filtering and reshaping onto every client. Rejected as the primary
  delivery mechanism for observations.

### Option D — do nothing (keep bespoke REST)

Continue serving via `api/timeseries.py` and `api/chemisty.py`.

- **Pros:** zero new work.
- **Cons:** no standardization, no interoperability, every consumer integrates
  against a custom contract. Fails the ADR1 unification goal.

## Decision

Adopt **Option A**: expose water-level and water-chemistry data through **OGC
API - EDR served by pygeoapi as a read-only facade** over the existing
PostgreSQL/PostGIS database.

Scope for the first iteration:

- **Collections:** `waterlevels` (manual + transducer) and `water-chemistry`.
- **Query patterns:** `/locations` (primary), `/area` and `/radius`
  (secondary), plus `/collections` metadata. `/instances` for transducer
  deployments, and datetime-ranged `/position` + `/cube` for dense transducer
  series.
- **Manual + transducer merge:** a collection-level query at a well returns the
  **merged** depth-to-water series — manual readings and transducer readings on
  a single time axis. Transducer data is visible without the consumer needing to
  know instances exist.
- **Instances:** each transducer/logger `Equipment` deployment is *also* exposed
  as an EDR instance of `waterlevels`, carrying its temporal extent
  (`date_installed`/`date_removed`), resolution (`recording_interval`), and
  instrument metadata (`model`, `serial_no`). Instances are the drill-down path
  to isolate one deployment; they do not hide data from the merged series.
- **Parameter-names:** `waterlevels` exposes a single depth-to-water parameter
  (manual and transducer readings share it; measurement method is carried as
  metadata / instance, not as a separate parameter); `water-chemistry` exposes
  one parameter per `analyte` present in the lexicon.
- **Output formats:** CoverageJSON (primary) and GeoJSON.
- **CRS / units:** EPSG:4326 (consistent with `SampleLocation` and the
  project's geopackage SRS convention); units carried from `unit` and declared
  per parameter.
- **Boundary:** EDR is read-only. All writes, validation, and QC stay in the
  FastAPI application. Only QC-approved / visible records are published
  (`WaterChemistryAnalysisSet.visible`, and `quality_control_status` on
  observations).

FastAPI remains the system of record. GeoServer remains responsible for maps
and OGC API - Features. pygeoapi owns the EDR observational surface.

## Consequences

### Positive

- One standardized, self-describing spatiotemporal interface for the two most
  requested observational datasets.
- Consumers use off-the-shelf EDR clients; no custom SDK required.
- Clean separation: authoritative write path (FastAPI) vs. cacheable read path
  (pygeoapi/EDR), which also helps the concurrency posture discussed in ADR2.
- Extensible: new collections (e.g. geothermal, geochronology) follow the same
  pattern later.

### Negative / costs

- A new service to deploy, monitor, and secure (align with the existing
  GeoServer IaC on this branch).
- Custom EDR providers or purpose-built SQL views are required to bridge the
  normalized relational schema into EDR collections and parameters.
- Two frameworks in the delivery stack (FastAPI + pygeoapi) to keep in sync as
  the schema evolves.

### Risks and open questions

- **Schema bridging** — well → timeseries → observation and set → analysis are
  joins, not flat tables. Decide between custom pygeoapi providers vs. dedicated
  read views/materialized views. Views are likely simpler to start.
- **Chemistry parameter cardinality** — number of `analyte` values drives the
  parameter list; confirm this is bounded and lexicon-governed before exposing
  every analyte as a parameter-name.
- **Transducer volume and cadence** — continuous transducer series can be large
  and dense. Confirm response paging/limits, decide default vs. maximum datetime
  windows, and consider server-side decimation/aggregation for wide `/cube`
  queries. High-frequency reads are the strongest case for caching the EDR
  facade.
- **Manual vs. transducer disambiguation** — the query that splits the two is
  presence of `WellTimeseries.equipment_id` (and transducer `equipment_type`).
  Confirm `equipment_type` values are lexicon-governed so instance selection is
  reliable. **Decided:** a collection-level query at a well returns the merged
  series (manual + transducer on one time axis); instances remain available to
  isolate a single transducer deployment (see Decision).
- **Private-IP database access** — the facade must reach Cloud SQL over the
  private IP path (`10.10.0.3`), consistent with the datastore convention noted
  for GeoServer; public IP returns 502s.
- **Publication gating** — enforce that only `visible` / QC-approved records
  reach EDR, ideally at the view layer so it cannot be bypassed.
- **Units and vocabularies** — declare EDR parameter units and definitions from
  the `lexicon_term` table so the standard's parameter metadata stays truthful.

## Acceptance Criteria

- `GET /collections` lists `waterlevels` and `water-chemistry` with correct
  spatial extents, temporal extents, and parameter-names.
- `GET /collections/waterlevels/locations/{wellId}?datetime=...` returns
  CoverageJSON depth-to-water for a real well over a bounded time range,
  covering both manual and transducer readings.
- `GET /collections/waterlevels/instances` lists transducer deployments for a
  well with correct temporal extents and resolution, and querying one instance
  returns only that deployment's dense series.
- `GET /collections/water-chemistry/area?coords=...&parameter-name=...` returns
  the expected analyses for a polygon, filtered by analyte.
- Only QC-approved / visible records appear in EDR responses.
- The service reaches Cloud SQL over the private IP and passes a read-only
  smoke test against production-shaped data.
- OpenAPI and conformance documents validate against the EDR spec.

## Notes

- Related: [ADR1](ADR1.md) (unification goal), ADR2 (API concurrency — the
  read/write split here reinforces that direction), and the GeoServer IaC on
  the `geoserver-iac` branch (complementary Features/WMS surface).
- This ADR decides direction and boundaries, not a file-by-file implementation
  plan. Provider-vs-view choice and deployment wiring are follow-up work.
