# NM_Wells 1:1 Mirror Transfer — Runbook

Operational steps to run the NM_Wells (geothermal) Phase-1 mirror transfer and verify it
worked. Phase 1 is a faithful, column-for-column copy of the legacy NM_Wells SQL Server
tables into the Postgres `NMW_*` staging mirror — no transform to the Ocotillo model.

- Code: `transfers/transfer_geothermal.py` (orchestrator), `transfers/nmw_mirror_transfer.py`
  (loader), `transfers/export_nmw_csvs.py` (CSV export), `transfers/nmw_sql_dump.py` (dump parser).
- Models: `db/nmw_legacy.py` (18 `NMW_*` tables).
- Design notes: [docs/nm_wells-migration.md](nm_wells-migration.md).
- Jira: [BDMS-945](https://nmbgmr.atlassian.net/browse/BDMS-945) (story),
  [BDMS-969](https://nmbgmr.atlassian.net/browse/BDMS-969) (this e2e run),
  [BDMS-970](https://nmbgmr.atlassian.net/browse/BDMS-970) (SQL Server access — blocker).

---

## 0. Prerequisites

- [ ] **SQL Server access** ([BDMS-970](https://nmbgmr.atlassian.net/browse/BDMS-970)):
      password reset done, can reach the NM_Wells host (Argon / Agustin / Sediment /
      SQL dev / SQLServer2019 as applicable).
- [ ] Python env ready: `uv venv && source .venv/bin/activate && uv sync --locked`.
- [ ] Target Postgres + PostGIS reachable; `.env` has `POSTGRES_*` (or Cloud SQL) creds.
- [ ] `.env` has the SQL Server source creds (only needed for the live export, step 1):

```bash
NMW_HOST=<sqlserver host/IP>
NMW_PORT=1433
NMW_USER=<user>
NMW_PASSWORD=<password>
NMW_DATABASE=NM_Wells
```

Pick **one** row source for the load:

| Source | When | Set |
|--------|------|-----|
| Per-table CSVs | live export via pymssql (default path) | nothing (`NMW_SQL_DUMP` unset) |
| SQL dump `.sql` | you have an SSMS data dump | `NMW_SQL_DUMP=/path/to/dump.sql` |

---

## 1. Apply schema (migrations)

The transfer assumes the schema already exists — it does not create/drop tables.

```bash
alembic upgrade head
```

Creates the 18 `NMW_*` tables + FKs and the 8 OGC backing views. Migration chain:
`c0d1e2f3a4b5` (tables+FK) → `d1e2f3a4b5c6` (per-well views) → `e2f3a4b5c6d7` (measurement views).

Verify the tables and views exist:

```bash
psql "$DATABASE_URL" -c '\dt "NMW_*"'        # expect 18 tables
psql "$DATABASE_URL" -c '\dv ogc_*'          # ogc_* views
psql "$DATABASE_URL" -c '\dm ogc_*'          # matview: ogc_geothermal_wells_temperature_profile
```

---

## 2. Export source tables to CSV (live source)

Skip if you're loading from a `.sql` dump (`NMW_SQL_DUMP` set).

```bash
uv run python -m transfers.export_nmw_csvs
```

- Writes `transfers/data/nma_csv_cache/<table>.csv`, one per mirrored table.
- Prints per-table row counts — **record these**; they are the source-of-truth counts for
  the post-load comparison in step 4.
- Any `FAILED: ...` line means that table didn't export — investigate before loading.

---

## 3. Run the transfer

Smoke-test with a row cap first, then run the full load.

```bash
# Smoke test: 1000 rows/table
TRANSFER_LIMIT=1000 uv run python -m transfers.transfer_geothermal

# Full load (all rows)
uv run python -m transfers.transfer_geothermal
```

Relevant env (all optional, sane defaults):

| Var | Default | Effect |
|-----|---------|--------|
| `TRANSFER_LIMIT` | 0 (all) | rows per table |
| `NMW_SQL_DUMP` | unset | load from `.sql` dump instead of CSVs |
| `NMW_CSV_DIR` | temp dir | where dump-derived CSVs are written (dump path) |
| `TRANSFER_GEOTHERMAL_REFERENCE` | 1 | load `ref_*` → lexicon |
| `TRANSFER_NMW_MIRROR` | 1 | load `NMW_*` mirror + refresh matviews |

The orchestrator: loads reference→lexicon, loads the mirror parent→child in FK order, then
refreshes the materialized OGC view. It prints a summary dict — confirm
`mirror.errors == 0` and `reference.errors == 0`.

Re-running is safe: dump path is truncate+COPY (CASCADE), CSV path is
`INSERT ... ON CONFLICT DO NOTHING`. No duplicate rows.

---

## 4. Verify — row counts

Compare each mirror table's row count against the source counts captured in step 2
(or against SQL Server directly).

```bash
psql "$DATABASE_URL" <<'SQL'
SELECT 'NMW_WellHeaders'        AS t, count(*) FROM "NMW_WellHeaders"
UNION ALL SELECT 'NMW_WellLocations',        count(*) FROM "NMW_WellLocations"
UNION ALL SELECT 'NMW_WellRecords',          count(*) FROM "NMW_WellRecords"
UNION ALL SELECT 'NMW_WellSamples',          count(*) FROM "NMW_WellSamples"
UNION ALL SELECT 'NMW_WellZDatum',           count(*) FROM "NMW_WellZDatum"
UNION ALL SELECT 'NMW_Sources',              count(*) FROM "NMW_Sources"
UNION ALL SELECT 'NMW_GtBhtHeaders',         count(*) FROM "NMW_GtBhtHeaders"
UNION ALL SELECT 'NMW_GtBhtData',            count(*) FROM "NMW_GtBhtData"
UNION ALL SELECT 'NMW_GtTempDepths',         count(*) FROM "NMW_GtTempDepths"
UNION ALL SELECT 'NMW_GtConductivity',       count(*) FROM "NMW_GtConductivity"
UNION ALL SELECT 'NMW_GtHeatFlow',           count(*) FROM "NMW_GtHeatFlow"
UNION ALL SELECT 'NMW_GtSumHeatFlow',        count(*) FROM "NMW_GtSumHeatFlow"
UNION ALL SELECT 'NMW_WsDstHeaders',         count(*) FROM "NMW_WsDstHeaders"
UNION ALL SELECT 'NMW_WsDstIntervals',       count(*) FROM "NMW_WsDstIntervals"
UNION ALL SELECT 'NMW_WsDstFlowHistory',     count(*) FROM "NMW_WsDstFlowHistory"
UNION ALL SELECT 'NMW_WsDstFluidProperties', count(*) FROM "NMW_WsDstFluidProperties"
UNION ALL SELECT 'NMW_WsDstPressure',        count(*) FROM "NMW_WsDstPressure"
UNION ALL SELECT 'NMW_WsIntervals',          count(*) FROM "NMW_WsIntervals"
ORDER BY t;
SQL
```

**Pass:** every count matches source (or matches `TRANSFER_LIMIT` if capped). Note any table
where the count is 0 or short — likely a failed export or an FK-skipped child row.

---

## 5. Verify — FK integrity

No child row should reference a missing parent. Spot-check the main hierarchy
(`NMW_WellHeaders` is the root parent):

```bash
psql "$DATABASE_URL" <<'SQL'
-- locations / records with no matching well header (expect 0)
SELECT 'orphan_locations' AS check, count(*)
FROM "NMW_WellLocations" l
LEFT JOIN "NMW_WellHeaders" h ON l."WellDataID" = h."WellDataID"
WHERE h."WellDataID" IS NULL
UNION ALL
SELECT 'orphan_records', count(*)
FROM "NMW_WellRecords" r
LEFT JOIN "NMW_WellHeaders" h ON r."WellDataID" = h."WellDataID"
WHERE h."WellDataID" IS NULL;
SQL
```

**Pass:** both counts are 0. (FK constraints are enforced at load, so a non-zero here means
data was loaded out of order or a constraint is missing — investigate.)

**Known exception:** `orphan_locations` reports **51** rows. These are `NMW_WellLocations`
rows whose `WellDataID` is blank in the source (`tbl_well_locations.csv`): empty values load
as NULL, NULL FK columns are exempt from FK enforcement, and the `LEFT JOIN ... IS NULL`
check counts them as orphans. This is a source data-quality issue, not a load-order or
constraint problem — accepted as-is. `orphan_records` must still be 0.

---

## 6. Verify — OGC views + matview

Refresh happens automatically in step 3. To refresh manually:

```bash
psql "$DATABASE_URL" -c 'REFRESH MATERIALIZED VIEW ogc_geothermal_wells_temperature_profile;'
```

Confirm each backing view returns rows and the per-well views emit **one feature per well**
(no count multiplication from duplicate location rows):

```bash
psql "$DATABASE_URL" <<'SQL'
SELECT 'ogc_geothermal_wells_bht'              AS v, count(*) FROM ogc_geothermal_wells_bht
UNION ALL SELECT 'ogc_geothermal_wells_temperature_profile', count(*) FROM ogc_geothermal_wells_temperature_profile
UNION ALL SELECT 'ogc_geothermal_wells_summary_heat_flow',   count(*) FROM ogc_geothermal_wells_summary_heat_flow
UNION ALL SELECT 'ogc_geothermal_wells_interval_heat_flow',  count(*) FROM ogc_geothermal_wells_interval_heat_flow
UNION ALL SELECT 'ogc_bht_measurements',       count(*) FROM ogc_bht_measurements
UNION ALL SELECT 'ogc_temp_depth_measurements',count(*) FROM ogc_temp_depth_measurements
UNION ALL SELECT 'ogc_heat_flow',              count(*) FROM ogc_heat_flow
UNION ALL SELECT 'ogc_dst',                    count(*) FROM ogc_dst;
SQL
```

Then hit the OGC API (with the app running) — all 6 collections should resolve and return
GeoJSON features:

```bash
for c in geothermal_wells_bht geothermal_wells_temperature_profile \
         bht_measurements temp_depth_measurements heat_flow dst; do
  echo "== $c =="
  curl -s "http://localhost:8000/ogcapi/collections/$c/items?limit=1" | head -c 400
  echo
done
```

**Pass:** each returns HTTP 200 with a `FeatureCollection`; per-well collections show
distinct wells (no duplicate `WellDataID`).

---

## 7. Verify — migrations reversible (non-prod only)

On a scratch/test DB, confirm a clean down/up cycle drops and recreates all 18 tables + 8
views with no orphans:

```bash
alembic downgrade base
psql "$DATABASE_URL" -c '\dt "NMW_*"'   # expect 0
psql "$DATABASE_URL" -c '\dv ogc_*'     # expect 0
alembic upgrade head                     # recreate
```

Automated coverage for this lives in `tests/test_nmw_mirror.py` (19 tests):
`uv run pytest tests/test_nmw_mirror.py`.

---

## Sign-off checklist (closes BDMS-969 → unblocks BDMS-951 / BDMS-954)

- [ ] Schema applied; 18 tables + 8 views present (step 1).
- [ ] Source CSVs exported; per-table source counts recorded (step 2).
- [ ] Transfer ran with `errors == 0` (step 3).
- [ ] Row counts match source (step 4).
- [ ] No orphan FK rows (step 5).
- [ ] All 6 OGC collections resolve; one feature per well (step 6).
- [ ] Migrations down/up clean on scratch DB (step 7).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `export_nmw_csvs` connection refused | SQL Server access not granted | [BDMS-970](https://nmbgmr.atlassian.net/browse/BDMS-970); check `NMW_HOST/PORT`, VPN |
| `TRUNCATE ... cannot truncate a table referenced in a foreign key` | parent truncated before child | loader uses `TRUNCATE ... CASCADE` (B2); confirm you're on current branch |
| Mirror column holds literal `CAST(...)` string | dump parser missed a parameterised type | fixed in `nmw_sql_dump.py` (B1); confirm branch is current |
| Per-well OGC view count > # wells | duplicate `NMW_WellLocations` rows | views dedup via `DISTINCT ON (WellDataID)` (B3); confirm branch is current |
| matview empty / stale | refresh skipped | `REFRESH MATERIALIZED VIEW ogc_geothermal_wells_temperature_profile;` |
| child table row count short | FK-skipped rows (`ON CONFLICT`/missing parent) | check parent loaded first; re-run full load |
