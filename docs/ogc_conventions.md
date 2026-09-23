# OGC Layer Naming Conventions

**Version:** 1.1 — 2026-08-28

| Date | Change |
|---|---|
| 2026-08-27 | Initial version. |
| 2026-08-28 | Implemented Level 1 title changes for the confirmed rows; inventory updated to reflect the new titles. |

This doc is the standing convention. When a recommended rename below is
agreed and actually implemented, update the layer.

## Purpose

OGC layer IDs are part of the public URL contract
(`/ogcapi/collections/{layer_id}/items`). Once a consumer integrates against an
ID, renaming it breaks that integration silently. This doc exists so naming
decisions are made consistently, once, rather than re-litigated per layer.

## Scope

Covers OGC **Feature** layer IDs and titles — `core/pygeoapi.py`,
`core/pygeoapi-config.yml`, `core/pygeoapi-config-internal.yml`.

## Governing standard

**Authority:** USGS NWIS site-type vocabulary.

**Why this standard:** it's an established, published vocabulary — adopting it
avoids inventing a new framework. The Bureau has also previously used USGS
conventions for QC practices, giving precedent for treating it as
authoritative.

**How to apply it:** don't use literal USGS codes (`GW`, `SP`, `FA-OF`) in
layer IDs. Use plain English words that match USGS site-type labels, so a
USGS or partner-agency consumer recognizes the layer without translation.
Where no USGS analogue exists, use plain descriptive English.

Relevant codes: `GW` = Well · `SP` = Spring · `ST` = Stream · `ST-DCH` =
Ditch · `FA-DV` = Diversion · `LK` = Lake, Reservoir, Impoundment · `AT` =
Atmosphere · `FA-OF` = Outfall.

## Do / Don't rules

**Do:**
- Use plain English that matches a USGS NWIS site-type label where one exists
  (`springs`, not `SP`).
- Put qualifiers before the feature type, not after — `surface_water_diversions`,
  not `diversions_surface_water`; `rock_sample_sites`, not `sites_rock_sample`.
- Spell abbreviations out in full: `total_dissolved_solids`, not `tds`.
- For Group B analytic/summary layers, prefer a `water_well_` prefix over a
  `_wells` suffix.
- When a layer's data changes scope, re-check whether its name is still
  accurate before assuming a rename is needed — widening or correcting the
  data can be the right fix instead (see
  [Deviations](#deviations-from-usgs-nwis-conventions)).

**Don't:**
- Don't use internal data-model vocabulary in a public name (`thing`,
  `other_things`) — a consumer outside this codebase has no context for it.
- Don't let a name read as a comma-separated description instead of a name.
- Don't invent a new abbreviation scheme. If the accurate name is long,
  that's fine.
- Don't let a layer's name claim something its data doesn't support (e.g. a
  name implying recency or scope the data doesn't have).
- Don't embed anything likely to change into a name — status terms ("draft,"
  "old"), authorship, or file format. A layer ID is a long-term commitment,
  and renaming it once published carries the same cost as any other rename
  covered by this doc.

## Deviations from USGS NWIS conventions

NWIS classifies physical monitoring **sites** — it has no vocabulary for
several categories of layer this catalog actually serves. These are
deliberate, structural deviations, not naming defects:

- **Analytic/summary layers** (`water_well_summary`, `major_chemistry_results`,
  `latest_tds_wells`, etc.) are derived, aggregated data products, not
  physical sites — NWIS has no site-type code for "a computed summary of
  observations at a site." These follow the plain-English fallback rule
  instead of a USGS code.
- **Geothermal layers** (`geothermal_wells_bht`, `bht_measurements`,
  `temp_depth_measurements`, `heat_flow`, `dst`) are outside NWIS's
  water-monitoring domain entirely — bottom-hole temperature logs, drill-stem
  tests, and heat-flow data are geothermal/drilling-industry concepts with no
  water-data equivalent. NWIS alignment doesn't apply; the plain-English rule
  and the abbreviation rule still do.
- **`actively_monitored_wells`** — NWIS has no concept of monitoring-network
  or group membership; this layer describes a Bureau-specific organizational
  construct (which wells belong to which monitoring group), not a physical
  site type. It's exempt from NWIS alignment by definition. It was widened to
  cover all groups rather than renamed.

## Change-level framework

Before renaming any layer, decide which level applies. A layer's row in the
inventory below may need more than one level at once — e.g. Level 1 for its
title and Level 2 for its ID, if both need to change.

- **Level 1 — Cosmetic only.** Update `title`/`description`, leave the layer
  ID (and therefore the URL) unchanged. Non-breaking, ship anytime.
- **Level 2 — Hard rename.** Rename the ID directly, no alias or grace
  period.

## Applying this to new layers

Check any newly-added layer against the [do/don't rules](#do--dont-rules)
**before** it merges, not retroactively.

## Current layer inventory

Every layer this catalog publishes. "Proposed" columns are `N/A` where the
current ID/title already conforms. "Title" is the pygeoapi `title` field (the
human-readable display name).

### Group A — thing-type layers (`core/pygeoapi.py`)

| Layer ID | Proposed ID | Layer Title | Proposed Title | Level | Rationale |
|---|---|---|---|---|---|
| `water_wells` | N/A | Water Wells | N/A | N/A | Conforms (USGS `GW`) |
| `springs` | N/A | Springs | N/A | N/A | Conforms (USGS `SP`) |
| `diversions_surface_water` | `surface_water_diversions` | Surface Water Diversions | N/A | 2 | Word-order inversion in the ID; title already correct. Matches USGS `FA-DV` (Diversion) |
| `ephemeral_streams` | N/A | Ephemeral Streams | N/A | N/A | Conforms |
| `lakes_ponds_reservoirs` | `lakes_and_reservoirs` | Lakes and Reservoirs | N/A | 2 | Title implemented. USGS's `LK` category doesn't separately name ponds, so consolidating the title is consistent with the standard |
| `meteorological_stations` | N/A | Meteorological Stations | N/A | N/A | Conforms (USGS `AT`) |
| `outfalls_wastewater_return_flow` | `wastewater_outfalls` | Outfalls and Return Flow | N/A | 2 | ID reads as a description, not a name; title is already fine |
| `perennial_streams` | N/A | Perennial Streams | N/A | N/A | Conforms |
| `rock_sample_locations` | `rock_sample_sites` | Rock Sample Sites | N/A | 2 | Title implemented. USGS uses "site" consistently |
| `soil_gas_sample_locations` | `soil_gas_sample_sites` | Soil Gas Sample Sites | N/A | 2 | Title implemented. USGS uses "site" consistently |
| `other_things` *(internal-only)* | N/A | Other Thing Types | N/A | N/A | "Thing" jargon resolved by removing from the public catalog, not renaming |

### Group B — analytic layers (`core/pygeoapi-config.yml`)

| Layer ID | Proposed ID | Layer Title | Proposed Title | Level | Rationale |
|---|---|---|---|---|---|
| `latest_tds_wells` | `water_well_latest_total_dissolved_solids` | Latest Total Dissolved Solids (Water Wells) | N/A | 2 | Title implemented. `tds` unexplained abbreviation in the ID |
| `depth_to_water_trend_wells` | N/A | Depth to Water Trend (Water Wells) | N/A | N/A | Conforms |
| `water_elevation_wells` | N/A | Water Elevation (Water Wells) | N/A | N/A | Conforms |
| `water_well_summary` | N/A | Water Well Summary | N/A | N/A | Conforms |
| `well_water_column` | `water_well_water_column` | Water Column (Water Wells) | N/A | 2 | Title implemented |
| `major_chemistry_results` | `water_well_major_chemistry` | Major Chemistry (Water Wells) | N/A | 2 | Missing `water_well_` prefix; "Results" is redundant — every layer is a result |
| `minor_chemistry_wells` | `water_well_minor_chemistry` | Minor Chemistry (Water Wells) | N/A | 2 | Should mirror the recommended `water_well_major_chemistry` for its sibling layer |
| `actively_monitored_wells` | N/A | Actively Monitored Wells | N/A | N/A | Not renamed — see [Deviations](#deviations-from-usgs-nwis-conventions) |
| `project_areas` | N/A | Project Areas | N/A | N/A | Conforms |
| `geothermal_wells_bht` | `geothermal_wells_bottom_hole_temperature` | Bottom-Hole Temperature (Geothermal Wells) | N/A | 2 | Title implemented. `bht` abbreviation in the ID |
| `geothermal_wells_temperature_profile` | N/A | Temperature-Depth Profile (Geothermal Wells) | N/A | N/A | Conforms. Title implemented |
| `bht_measurements` | `bottom_hole_temperature_measurements` | Bottom-Hole Temperature Measurements | N/A | 2 | Title implemented. `bht` abbreviation in the ID |
| `temp_depth_measurements` | `temperature_depth_measurements` | Temperature-Depth Measurements | N/A | 2 | ⚠️ *needs review*: `temp` abbreviation in the ID only; title already spells it out |
| `heat_flow` | N/A | Heat Flow | N/A | N/A | Conforms |
| `dst` | `drill_stem_tests` | Drill Stem Tests | N/A | 2 | ⚠️ *needs review*: ID is a bare abbreviation; title already spells it out — recommended ID matches the title exactly |

### Internal-only (`core/pygeoapi-config-internal.yml`)

| Layer ID | Proposed ID | Layer Title | Proposed Title | Level | Rationale |
|---|---|---|---|---|---|
| `locations` | N/A | Locations | N/A | N/A | Conforms. Hidden from public catalog — scope decision, not a naming fix |
| `avg_tds_wells` | `water_well_average_total_dissolved_solids` | Average Total Dissolved Solids (Water Wells) | N/A | 2 | Title implemented. `avg` abbreviation remains in the ID; hidden from public catalog but the rule still applies for internal consumers |
| `latest_depth_to_water_wells` | N/A | Latest Depth to Water (Water Wells) | N/A | N/A | Conforms. Hidden from public catalog — audit flagged it as redundant with `water_well_summary`, not a naming defect |
| `water_well_field_operations` | N/A | Water Well Field Operations | N/A | N/A | Conforms. Internal-only with no public form at all — it publishes landowner contact details and staff-written access notes |

## Current-record semantics

Layers that read a history table (`status_history`, `permission_history`,
`measuring_point_history`, `monitoring_frequency_history`) disagree about what
"current" means, and the disagreement is deliberate.

`ogc_actively_monitored_wells` takes the row with the greatest `start_date` and
**ignores `end_date`**, so a monitoring status closed in 2019 still reads as
current there. That is tolerable on a summary layer, where the question is
roughly "is this well in the programme".

`ogc_internal_water_well_field_operations` honours the window:

```sql
WHERE h.start_date <= CURRENT_DATE
  AND (h.end_date IS NULL OR h.end_date >= CURRENT_DATE)
ORDER BY h.start_date DESC, h.id DESC
```

Its columns answer "may a crew do this today", and a permission that ran out
last month must not read as a permission. A row whose window has not opened yet
is not current either, and reads null.

New layers should follow the second form. The first is kept only because
changing it would move rows in a published layer.

## References

1. GeoCat/GeoServer layer naming guidance (<https://docs.geocat.net/map/2021/setup/names/index.html#layer-naming-coverage-resources>)
   — technical/structural naming rules (character restrictions, case-sensitivity,
   long-term stability).
2. OGC Feature Layer Audit Report (Section 4.1 — naming findings; Section
   6.2 — naming proposal and change-level framework).
