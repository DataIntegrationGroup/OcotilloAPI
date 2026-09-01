# Vertical observations: needs and assumptions

**Status:** Draft — needs and assumptions only. No storage decision is made here.
**Date:** 2026-09-01

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
120–135 ft is an interval, and so is a core-derived chemistry value. These are
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
   say so explicitly; the datum is not inferable from the parameter.
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
6. **Depth values are never recomputed.** Datum changes, re-surveys, and well
   deepening change the interpretation, not the recorded number.
7. **Vertical data gets its own path**, parallel to `TransducerObservation`,
   rather than being forced through `Sample`. The `Sample` path stays correct for
   discrete samples that happen to have a depth interval — a bailer at 200 ft is
   a sample, not a profile.
8. **The existing geothermal temp-depth data is the first migration target.**
   `NMW_GtTempDepths` is real, already published, and already the right shape.
   Any design that cannot absorb it is the wrong design.

## Open questions

- Does depth go on `Observation` (nullable columns, one table for both axes) or
  on a separate `VerticalObservation` table? The transducer precedent argues
  separate; the parameter/unit/lexicon plumbing argues shared.
- Is the profile container a new entity, or is `FieldActivity` already it? A
  logging run is an activity during a field event, which is close.
- Do intervals and points share a table, or split?
- Does a profile need per-reading QC, or is run-level `review_status` enough?
  Transducer data needed both.
- Which datasets beyond geothermal are actually queued — downhole sonde
  profiles, geophysical logs, core interval chemistry? The answer changes the
  row-count and interval requirements sharply.
- How are profiles exposed in the REST API, given that the OGC path is already
  settled by precedent?

## Related

- `docs/measuring-point-height-null-handling.md` — null MP height defaults to
  ground surface
- `docs/hydrograph-correction-publish.md` — the block/QC pattern on the time axis
- `docs/nm_wells-migration.md` — where the geothermal profile data comes from
- `docs/ogc-field-descriptions.md` — field titles/units for anything published
- `ADR4.md` — depth/datum conversion rules belong in `domain/`, not `services/`
