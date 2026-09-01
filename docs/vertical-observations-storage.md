# Vertical observations: needs and assumptions

**Status:** Storage shape decided 2026-09-01; several questions still open.
**Date:** 2026-09-01, decisions recorded same day

## Decisions

Decided by Jake Ross, 2026-09-01:

1. **Vertical observations get their own table**, separate from `Observation`,
   paired with a profile container mirroring `TransducerObservationBlock`. This
   resolves need 7 below: neither depth-on-`Observation` nor sample-per-depth.
2. **Review status is held per profile (run)**, not per reading. No per-reading
   QC column, and no per-reading correction note.
3. **The Subsurface Library is the dataset driving this**, alongside the
   geothermal temperature-depth profiles already held and the new ones the
   geothermal team is collecting in spreadsheets.

Whitepaper version, for non-engineering readers:
<https://nmbgmr.atlassian.net/wiki/spaces/Ocotillo/pages/2908749826>

## What this is about

Every observation the schema stores today is indexed by **time**. `Observation`
carries `observation_datetime` and no depth; `TransducerObservation` carries
`observation_datetime` and no depth. A well's hydrograph is a value read against
a time axis, and both the manual path (`Sample` → `Observation`) and the
continuous path (`Deployment` → `TransducerObservation`) are built around that.

A **vertical observation** is one where the domain axis is **depth**: a series of
values collected at one visit, at many depths in one borehole, where the
interesting variation is with depth and the timestamp is effectively constant
across the series. Temperature-depth profiles, downhole sonde profiles
(temperature/SC/DO down the water column), geophysical logs, and interval
properties from core all have this shape.

The schema has no home for it. This document records what such data needs and
what we are assuming, so that whoever designs the tables is not re-deriving it.

## What exists now

Depth appears in five places, none of them an observation axis:

| Where | Columns | Meaning |
|---|---|---|
| `db/thing.py` | `well_depth`, `hole_depth`, `well_casing_depth`, `well_pump_depth`, `screen_depth_top/bottom` | Construction geometry, one value per well |
| `db/sample.py` | `depth_top`, `depth_bottom` | Interval a discrete sample came from |
| `db/thing_geologic_formation_association.py` | `top_depth`, `bottom_depth` | Lithology picks, "from ground surface" |
| `db/nmw_legacy.py` | `NMW_GtTempDepths.depth` / `.temp` | 1:1 mirror of NM_Wells `tbl_gt_temp_depths` — a real temp-vs-depth profile, readable only as legacy |
| `db/geothermal.py` | `GeothermalTemperatureProfile*` | Commented out in full. An earlier attempt at exactly this problem |

Published today: `ogc_geothermal_wells_temperature_profile`, a materialized view
over the legacy mirror, one row per depth. That is the only vertical dataset
reaching users, and it bypasses the observation model entirely.

`schemas/validators.py:DepthIntervalMixin` is the only shared depth rule:
non-negative, bottom strictly greater than top. It assumes intervals, so it does
not apply to point-depth readings.

## Needs

### 1. Depth is meaningless without a reference

A stored number needs three things fixed before it can be compared to anything:

- **Datum** — ground surface, top of casing, measuring point, or an elevation
  datum (NAVD88). The existing depth columns say "from ground surface" in
  comments only; nothing enforces or records it per row.
- **Direction** — positive down (depth) or positive up (elevation). Mixing these
  silently in one column is the classic failure.
- **Unit** — the existing depth columns are feet; `Location.elevation` is
  **meters**, NAVD88. Any conversion from depth to elevation crosses a unit
  boundary, and nothing in the schema flags that.

### 2. Depth must be convertible to elevation, and that conversion is dated

To turn a bgs depth into an elevation the reader needs `Location.elevation` (m,
NAVD88) and, if the depth is measured from the measuring point, the MP height in
effect **on the observation date** — `MeasuringPointHistory` already models MP
height as a dated interval, precisely because it changes.

Consequence: the depth as measured must be stored as measured, against the
reference in effect at the time, and never rewritten when the datum changes. A
re-survey or a new wellhead changes the conversion, not the field reading.
`docs/measuring-point-height-null-handling.md` already sets the convention for
the null case (missing MP height means ground surface, i.e. zero).

### 3. A profile is a thing, not a bag of readings

The N readings of one logging run belong together: same instrument, same trip
down the hole, same QC verdict, same source file. That is the same requirement
`TransducerObservationBlock` solves for the time axis — a container carrying
`review_status`, `source_file`, `corrections`, and a reviewer, so a run can be
approved, annotated, or deleted as a unit. Vertical data needs the equivalent;
without it there is no way to say "this log is bad" except row by row.

Per decision 2, the container is also where review state *stops*.
`review_status`, `data_maturity`, and `release_status` all live on the profile;
the readings table gets none of them. This is a real simplification over the
transducer path, and it is available because a corrected transducer series has
readings that differ from what the instrument recorded, while a vertical profile
is stored as logged. Adding a per-reading flag later is additive and does not
invalidate stored rows.

### 4. Measured depth is not always true vertical depth

NM_Wells carries `From_TVD`/`To_TVD` alongside `From_Depth`/`To_Depth` because
deviated boreholes exist. Most NM monitoring wells are vertical and the two are
equal, but the distinction has to be representable or the deviated ones are
silently wrong.

### 5. Row counts are a different order of magnitude

A manual water level is one `Observation` per visit. A geophysical log at 0.1 ft
spacing in a 1,000 ft hole is 10,000 rows per run. Whatever holds these needs an
index that supports "all readings for this profile, ordered by depth" and a
loader that upserts idempotently — the lesson `TransducerObservation` encodes in
its `UniqueConstraint`, and the lesson behind the ~391k silently dropped rows in
the continuous transfer.

### 6. Point depths and intervals are both real

A sonde reading at 42.0 ft is a point. A thermal-conductivity measurement over
120–135 ft is an interval, and so are core sample properties and lithology
picks — which is most of what the Subsurface Library holds, so per decision 3
this is now the first design question rather than a detail. These are
different enough that one nullable pair of columns handles them only by
convention (`depth_top == depth_bottom` for a point, or `depth_bottom IS NULL`).
Whichever convention is chosen has to be stated and validated, and
`DepthIntervalMixin` does not currently permit either — it requires
`bottom > top` strictly.

Overlap rules also need stating. Lithology picks must not overlap; sample
intervals from different runs legitimately can.

### 7. The `Sample` hierarchy forces a choice

`Location → Thing → FieldEvent → FieldActivity → Sample → Observation` puts
depth on `Sample`. Taken literally, a 10,000-point log is 10,000 `Sample` rows,
each with a unique `sample_name` (a `NOT NULL UNIQUE` column). That is not
tenable for logs. Either depth moves onto the observation, or vertical data gets
its own path beside the manual one — which is what the continuous data already
did.

**Resolved by decision 1:** its own path. Depth-on-`Observation` was the other
live option and would have kept the parameter/unit/lexicon plumbing shared, but
an `Observation` requires a parent `Sample`, so it does not escape this problem
without relaxing that foreign key, and it puts log-scale volume in the table
backing most existing API traffic. The cost accepted is a third observation
path: parameter and unit handling to keep consistent across three, and "all
observations for this well" becoming a union of three sources.

### 8. Publication has no obvious shape

OGC API - Features serves 2D point features. A profile is not a feature; it is a
series hanging off one. The existing answer — a materialized view with one row
per depth, repeating the well's geometry — works and is already shipped for
geothermal, but it makes every depth a separate "feature". Anything new should
either follow that precedent deliberately or say why not. Field titles and units
for whatever lands go in `core/ogc-field-descriptions.yml`; see
`docs/ogc-field-descriptions.md`.

### 9. Nulls carry reasons; maturity is orthogonal to release

Two existing patterns apply unchanged. A null value needs a reason in the same
row (`Observation.groundwater_level_reason`). And review state
(`data_maturity`: provisional / in review / approved) is separate from who may
see the row (`release_status`) — a reading can be public and provisional at
once, which is why `TransducerObservation` has both.

## Assumptions

These are the working assumptions. Each is a candidate to be confirmed or
overturned before any table is built.

1. **Depth is positive downward.** A larger number is deeper. Elevation, where
   needed, is derived, not stored alongside as a second authority.
2. **Ground surface is the default datum**, matching every existing depth column
   and the San Acacia ingestion decision. Rows measured from anything else must
   say so explicitly; the datum is not inferable from the parameter. Monitoring
   wells share one convention; a library assembled over decades from many
   operators does not, so test this against real Subsurface Library records
   before relying on it.
3. **Feet are the stored unit for depth**, matching existing depth columns, even
   though `Location.elevation` is meters. The depth unit is recorded per row (or
   per profile) as a lexicon term rather than assumed, following how
   `Observation.unit` is handled.
4. **One timestamp per profile.** A run is treated as instantaneous. A log where
   per-reading time genuinely matters (e.g. a slow thermal equilibration) is
   out of scope for this shape and belongs on the time axis.
5. **Measured depth equals TVD unless a deviation survey says otherwise.** No
   deviation data is stored today; assuming equality is the honest default for
   vertical NM wells, but the column pair should exist rather than be added later.
   Close to theoretical for monitoring wells, not for the oil and gas boreholes
   in the Subsurface Library.
6. **Depth values are never recomputed.** Datum changes, re-surveys, and well
   deepening change the interpretation, not the recorded number.
7. **Vertical data gets its own path**, parallel to `TransducerObservation`,
   rather than being forced through `Sample`. **Decided 2026-09-01**, no longer
   an assumption. The `Sample` path stays correct for discrete samples that
   happen to have a depth interval — a bailer at 200 ft is a sample, not a
   profile.
8. **The existing geothermal temp-depth data is the first migration target.**
   `NMW_GtTempDepths` is real, already published, and already the right shape.
   Any design that cannot absorb it is the wrong design.

## Where this sits in the migration

Naming the Subsurface Library as the driver (decision 3) locates this work in
the NM Wells migration plan, which sequences the library as a Phase 4 1:1 mirror
(BDMS-948) and the refactor into the native model as Phase 5. **This table is a
Phase 5 artifact.** Two consequences:

- Nothing here blocks Phase 4, and Phase 4 should not wait on it. The library
  arrives as `NMW_*`-style mirror tables first, exactly as NM Wells did.
- Phase 5 already lists establishing geothermal and subsurface lexicon terms as
  prerequisite work. That is this table's prerequisite too — `parameter` and
  `unit` are controlled terms, so it cannot hold a reading whose parameter has
  no term.

The nearer driver is **Phase 2**: the geothermal team is collecting new
temperature-depth profiles in spreadsheets with no path into a system of record.
Those are vertical observations, they are being produced now, and they are the
smallest clean first load this table could take.

Out of scope, deliberately: the Subsurface Library's headline problems are
identifier reconciliation against NM Wells (no shared key) and PLSS coordinates
at varying precision. Both are `Location`/`Thing` problems, resolved before any
depth-indexed row is written. This design should not try to absorb them.

## Open questions

Engineering, and now the critical path:

- **Do intervals and points share a table, or split?** Decision 3 promotes this
  to question one: temp-depth profiles are point series, but core properties,
  lithology picks, and sample intervals are not, and they are most of the
  library. If shared, the point convention (`depth_top == depth_bottom`, or a
  null bottom) needs stating once plus a `DepthIntervalMixin` variant, since the
  current mixin requires `bottom > top` strictly. If split, the profile
  container is shared and only the readings tables differ.
- Is the profile container a new entity, or is `FieldActivity` already it? A
  logging run is an activity during a field event, which is close.
- How are profiles exposed in the REST API, given that the OGC path is already
  settled by precedent?

Domain staff:

- Is one timestamp per profile (assumption 4) safe for the data actually queued?
  A slow thermal equilibration run may not fit it.
- Are profiles ever measured from a reference other than ground surface, and if
  so, is that reference in the source data or only in the head of whoever
  collected it? Matters most for Subsurface Library material.

Answered 2026-09-01:

| Question | Answer |
| --- | --- |
| Separate table, or depth on `Observation`? | Separate |
| Per-reading QC, or run-level? | Run-level is enough |
| Which datasets are queued? | Subsurface Library, plus geothermal temp-depth profiles held and incoming |

## Related

- Whitepaper for non-engineering readers:
  <https://nmbgmr.atlassian.net/wiki/spaces/Ocotillo/pages/2908749826>
- NM Wells migration plan, Phases 2/4/5:
  <https://nmbgmr.atlassian.net/wiki/spaces/Ocotillo/pages/2854780929>
- `docs/measuring-point-height-null-handling.md` — null MP height defaults to
  ground surface
- `docs/hydrograph-correction-publish.md` — the block/QC pattern on the time axis
- `docs/nm_wells-migration.md` — where the geothermal profile data comes from
- `docs/ogc-field-descriptions.md` — field titles/units for anything published
- `ADR4.md` — depth/datum conversion rules belong in `domain/`, not `services/`
