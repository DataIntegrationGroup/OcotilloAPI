# NM_Wells → Ocotillo migration

Migration of the legacy **NM_Wells** SQL Server database (and the related
Subsurface Library) into OcotilloAPI. Source of truth for table inventory and
field-level recommendations: `NM_Wells + Subsurface library.xlsx` (planning
workbook, not in repo).

## Two-phase approach

1. **Phase 1 — 1:1 staging mirror** *(current)*. Land source tables unchanged
   into `NMW_*` mirror tables (`db/nmw_legacy.py`), column-for-column. No
   transform. Mirrors the `db/nma_legacy.py` (NM_Aquifer) convention. This lets
   us load the SQL dump first and transform later without re-reading the source.
2. **Phase 2 — transform** *(later)*. Map mirror rows into the Ocotillo data
   model (`Location → Thing → FieldEvent → FieldActivity → Sample →
   Observation`, plus `status_history`, `measuring_point_history`, `contact`,
   `publication`, `thing_geologic_formation_association`, `thing_id_link`) using
   the existing CSV→Pandas→ORM transfer pattern in `transfers/`. Per-column
   targets are recorded inline in `db/nmw_legacy.py` and summarized below.

## Source access

NM_Wells is delivered as a SQL dump. Physical source table names are
`tbl_well_*` / `tbl_gt_*` / `tbl_ws_*` (snake_case). To use the existing
transfer pipeline, export each source table to CSV (same flow as the
NM_Aquifer `nma_csv_cache`).

## Phase 1 scope (mirrored now)

Five "Migrate First / Main" tables — the only ones with an authoritative
field-level mapping in the workbook (sheet 3):

| Source table         | Mirror model         | Cols |
|----------------------|----------------------|------|
| `tbl_well_locations` | `NMW_WellLocations`  | 40   |
| `tbl_well_headers`   | `NMW_WellHeaders`    | 35   |
| `tbl_well_records`   | `NMW_WellRecords`    | 12   |
| `tbl_well_z_datum`   | `NMW_WellZDatum`     | 18   |
| `tbl_well_samples`   | `NMW_WellSamples`    | 30   |

Migration: `alembic/versions/u7v8w9x0y1z2_nmw_legacy_staging_mirror_tables.py`.

Geothermal + Drill Stem Test "Migrate First" tables are also mirrored (columns
+ lengths taken straight from the SQL-dump DDL):

| Source table                  | Mirror model               | Cols | PK |
|-------------------------------|----------------------------|------|----|
| `tbl_gt_bht_headers`          | `NMW_GtBhtHeaders`         | 16   | BHTGUID |
| `tbl_gt_bht_data`             | `NMW_GtBhtData`            | 10   | OBJECTID |
| `tbl_ws_intervals`            | `NMW_WsIntervals`         | 12   | IntrvlGUID |
| `tbl_gt_conductivity`         | `NMW_GtConductivity`      | 7    | OBJECTID |
| `tbl_gt_heat_flow`            | `NMW_GtHeatFlow`          | 13   | OBJECTID |
| `tbl_gt_sum_heat_flow`        | `NMW_GtSumHeatFlow`       | 30   | OBJECTID |
| `tbl_gt_temp_depths`          | `NMW_GtTempDepths`        | 9    | OBJECTID |
| `tbl_ws_dst_headers`          | `NMW_WsDstHeaders`        | 11   | DSTGUID |
| `tbl_ws_dst_intervals`        | `NMW_WsDstIntervals`      | 17   | DSTInterval |
| `tbl_ws_dst_flow_history`     | `NMW_WsDstFlowHistory`    | 13   | OBJECTID |
| `tbl_ws_dst_fluid_properties` | `NMW_WsDstFluidProperties`| 9    | OBJECTID |
| `tbl_ws_dst_pressure`         | `NMW_WsDstPressure`       | 28   | OBJECTID |

Migration: `alembic/versions/v8w9x0y1z2a3_nmw_geothermal_dst_mirror_tables.py`.

Link columns (`SamplSetID`, `BHTGUID`, `IntrvlGUID`, `DSTGUID`, `DSTInterval`,
`RecrdSetID`) are kept as plain indexed GUID columns — NOT enforced FKs — since
this is staging. Relationship chains documented in `db/nmw_legacy.py`.

### PK / type notes
- SQL Server `uniqueidentifier` → postgres `UUID`; `real/float` → `Float`;
  `nvarchar` → `String` (source lengths absent from the sheet, so widened);
  `datetime2` → `DateTime`; `timestamp` (rowversion) → **dropped**.
- PKs **verified against the dump DDL**: Headers→`WellDataID`,
  Records→`RecrdSetID`, Samples→`SamplSetID` (declared PKs);
  Locations→`OBJECTID`, ZDatum→`OBJECTID` (no declared PK in source — unique
  indexes on both OBJECTID and GlobalID; OBJECTID identity is never NULL).

## Loading the mirror (Phase 1 transfer)

`transfers/nmw_mirror_transfer.py` (`transfer_nmw_mirror(session, limit)`) loads
each source table into its `NMW_*` table 1:1. It is data-driven over
`NMW_MIRROR_SPECS` (one `(model, source_table)` per mirror), derives column
handling from each model's `__table__` metadata, coerces types
(uuid/int/float/datetime/string; NULL/NaN/NaT → None; rowversion dropped), and
chunk-upserts via `INSERT ... ON CONFLICT (<pk>) DO NOTHING`.

**Row source** (selected at runtime):
- **SQL Server data dump** — set `NMW_SQL_DUMP` to a `.sql` file of
  `INSERT [dbo].[tbl_*] (...) VALUES (...)` statements. `transfers/nmw_sql_dump.py`
  splits statements with **sqlparse** and `write_table_csv` writes one CSV per
  table (handles `N'...'`/escaped `''`, embedded commas/parens, `CAST(... AS ...)`,
  multi-row `VALUES`, `0x` binary → NULL, UTF-16/UTF-8 BOM). The mirror then
  bulk-loads each CSV with Postgres **`COPY ... FROM STDIN`** (truncate + COPY;
  Postgres casts text → column types). CSV dir = `NMW_CSV_DIR` (default temp).
- **CSV exports** — fallback when `NMW_SQL_DUMP` is unset; per-table CSVs in
  `nma_csv_cache` / GCS `nma_csv/`, inserted row-by-row with type coercion.

> Note: `NMWells.sql` as provided is **schema-only** (DDL, no `INSERT`s) — it
> seeded the models/migrations. A separate **data** dump (with `INSERT`s) is
> what `NMW_SQL_DUMP` should point at.

Run via the standalone orchestrator `transfers/transfer_geothermal.py`
(`python -m transfers.transfer_geothermal`) — **separate** from the deprecated
`transfers/transfer.py` (NM_Aquifer driver), which must not gain new migrations.
The orchestrator runs the reference→lexicon load (`TRANSFER_GEOTHERMAL_REFERENCE`)
then the mirror load (`TRANSFER_NMW_MIRROR`); both default on. After the mirror
load it calls `refresh_materialized_views` to `REFRESH` the materialized OGC views
(currently `ogc_geothermal_wells_temperature_profile`; missing views are skipped).
Assumes the schema already exists (`alembic upgrade head`).

## OGC views (pygeoapi)

`alembic/versions/w9x0y1z2a3b4_add_geothermal_ogc_views.py` adds two point
layers over the `NMW_*` mirror (geometry from `NMW_WellLocations` Lat/Long_dd83):

- `ogc_geothermal_wells_bht` — one feature per geothermal well with
  bottom-hole-temperature data (`NMW_GtBhtData`); aggregate BHT stats.
- `ogc_geothermal_wells_temperature_profile` — **materialized** view, one feature
  per geothermal well with a downhole temperature-vs-depth series
  (`NMW_GtTempDepths`, ~370k source rows), series as an ordered JSON array.
  Indexed (unique `well_data_id`, GiST `geom`); `REFRESH MATERIALIZED VIEW` after
  a data reload.

- `ogc_geothermal_wells_summary_heat_flow` — one feature per geothermal well with
  summary heat-flow determinations (`NMW_GtSumHeatFlow`): aggregate heat flow,
  thermal gradient, thermal conductivity, quality, plus a `measurements` JSON
  series (one element per determination, ordered by depth). Linked directly via
  `NMW_GtSumHeatFlow.RecrdSetID → NMW_WellRecords.RecrdSetID`.
- `ogc_geothermal_wells_interval_heat_flow` — one feature per geothermal well
  with **per-interval** heat-flow values (`NMW_GtHeatFlow`): aggregate heat flow
  (Q), gradient, conductivity (Kpr), diffusivity (Ka), plus a `measurements` JSON
  series (one element per interval, ordered by depth). Linked via
  `NMW_GtHeatFlow.IntrvlGUID → NMW_WsIntervals.IntrvlGUID → NMW_WellSamples →
  NMW_WellRecords`.

Well linkage: `gt_*.SamplSetID → NMW_WellSamples.SamplSetID →
NMW_WellRecords.RecrdSetID → NMW_WellLocations.WellDataID`.

## Phase 2 transform map (summary)

Key relationship re-routing: legacy `WellDataID` ties header/location/records;
`RecrdSetID` ties records→children. In Ocotillo, **wells → records** becomes
**wells (Thing) → field_event**, and `RecrdClass` → `field_activity.activity_type`.

| Source                              | Ocotillo target |
|-------------------------------------|-----------------|
| `tbl_well_locations` Lat/Long_dd83  | `location.point` |
| `tbl_well_locations` State/County   | `location.state` / `location.county` |
| `tbl_well_locations` PLSS/UTM/dd27  | **new** `NMW_Location` (township, range, section, unit_letter, utm_zone, basin, footages, dd27, source_datum, source_units) |
| `tbl_well_headers` CurWellNam/WellClass/TotalDepth/ComplDate | `thing.name` / `thing.type` / `thing.well_depth` / `thing.well_completion_date` |
| `tbl_well_headers` CurStatus        | `status_history.status` |
| `tbl_well_headers` CurOperatr/CurOwner | `contact.name` (type = operator / owner) |
| `tbl_well_headers` API              | `thing_id_link.alternate_id` |
| `tbl_well_headers` Fm_TD            | `thing_geologic_formation_association` |
| `tbl_well_headers` WellType/WellOrient/CurWellNum/Comments | **new** `well_purpose.purpose` / **new** `well_detail` (well_orient, well_number, comments) |
| `tbl_well_records` RecrdSetID/ActionDate/Comments | `field_event` (id/event_date/notes) |
| `tbl_well_records` RecrdClass       | `field_activity.activity_type` |
| `tbl_well_z_datum` Elev_GL/DF/KB/unspc | `measuring_point_history.measuring_point_height` |
| `tbl_well_z_datum` DepthDatum/DepthUnits/ElevSource | `measuring_point_history` description / units / source |
| `tbl_well_samples` SamplSetID/SampleDate/Notes/EnteredBy | `sample` (id/sample_date/notes/created_by_name) |
| `tbl_well_samples` From_Depth/To_Depth/SmpDpUnt | `observation` (depths / unit) |

**New tables Phase 2 needs:** `NMW_Location`, `well_detail`, `well_purpose`.

## Reference tables → lexicon

The legacy `ref_*` lookup tables ("Add to lexicon" in workbook sheet 1) are
loaded into the lexicon by `transfers/reference_lexicon_transfer.py`
(`transfer_reference_tables`), registered as a **foundational** transfer in
`transfers/transfer.py` (runs before wells). Each `ref_*` table becomes a
`LexiconCategory` (name = table minus `ref_`) and its rows become
`LexiconTerm`s linked to that category. Idempotent (`ON CONFLICT DO NOTHING`),
matching `core.initializers.init_lexicon`.

Term/definition columns are **auto-detected** from each CSV header (the
workbook has no column lists for `ref_*`); override `term_col`/`definition_col`
on a `RefTableSpec` if detection is wrong. The Subsurface Library `LU_*`
lookups are also "Add to lexicon" — add them to `REFERENCE_TABLE_SPECS` once
their CSVs are available.

## Not yet mapped (no field list / DDL in workbook)

Remaining "Migrate First" tables not yet mirrored:

- **Publications:** `tbl_sources` (DDL available in dump; not yet requested)
- **Subsurface Library:** `dst_scan`, `log_scanned`, `Well_Header`,
  `well_operators`

`tbl_well_bores` (Geothermal area) is "Review", not "Migrate First".

"Don't migrate" (per workbook): OCD injection/wells imports, `*_ZOLD`,
`*_DataAsOf-*` snapshots, `geometry_columns`, `spatial_ref_sys`, `sysdiagrams`.
