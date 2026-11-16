# Groundwater level bulk export (OCO-79)

One GeoParquet file and one CSV per public well, each holding that well's full
manual water-level history, published at a fixed GCS path and registered as a
STAC item. Dagster+ runs it; every step executes in Cloud Run.

```
Dagster+ (ocotillo-automated-ingestion)          Cloud Run job gwl-export-<env>
───────────────────────────────────────          ──────────────────────────────
gwl_snapshot        ── jobs:run  snapshot ─────▶ read replica ─▶ _runs/<id>/snapshot.parquet + manifest.json
gwl_well_files      ── jobs:run  convert ×N ───▶ _runs/<id>/wells/gwl-<well>.parquet|.csv
gwl_checks          ── jobs:run  check ────────▶ _runs/<id>/reports/check.json (fails the run on error)
gwl_published_files ── jobs:run  publish ──────▶ groundwater-levels/<well>/gwl-<well>.parquet|.csv
gwl_stac_items      ── jobs:run  register ─────▶ STAC API + gwl-<well>.json, then _state/published.json
```

Code:

| Where | What |
|---|---|
| `automated_ingestion/defs/assets/groundwater_level_export.py` | The five assets. Each launches one execution and reads its report back as metadata. |
| `automated_ingestion/defs/jobs/groundwater_level_export.py` | Job over the asset group, plus a nightly schedule that is **off by default**. |
| `automated_ingestion/shared/cloud_run.py` | Runs a job execution over the Cloud Run Admin API v2 and waits for it. Cancels the execution if the Dagster run is terminated. |
| `automated_ingestion/exports/groundwater_levels/` | The worker: `rules.py` (pure rules), `snapshot.py` (SQL), `steps.py` (the five steps), `stac_api.py`, `storage.py`, `worker.py` (container entry point). |
| `docker/gwl_export/Dockerfile` | The job image. |
| `automated_ingestion/iac/gwl_export.tf` | Bucket, Cloud Run job, service account, IAM. |
| `automated_ingestion/sql/gwl_export_role.sql` | Read-only grants for the job's database role. |

## Why Cloud Run

Dagster+ Serverless runners are small, run outside GCP, and sit a long way from
Cloud SQL. The export reads every public water level and writes thousands of
files, which belongs next to the database and the bucket. Dagster launches,
orders, retries, schedules, and records. One job definition serves all five
steps: the step name and snapshot id go in as container args. `convert` fans out
across parallel tasks (`CLOUD_RUN_TASK_INDEX`/`COUNT`), at one task per 250
changed wells and no more than 50 tasks. Both limits are set in the
`gwl_well_files` run config.

## Behaviour worth knowing

**The snapshot is consistent.** The rows and the per-well counts are read in a
single `REPEATABLE READ, READ ONLY` transaction on the replica. The check step
compares every file against those counts.

**Change detection is a content hash.** Each well's rows are hashed in file
order, together with `FORMAT_VERSION`, and compared with
`_state/published.json`. A well whose hash is unchanged gets no new file and no
STAC call. If no well changed, `gwl_well_files` launches no execution at all.
Bumping `FORMAT_VERSION` in `rules.py` republishes every well.

**`_state/published.json` is the commit point**, and `register` writes it last.
A run that dies at any step leaves the previous state in place, so the next run
redoes the work. Every step can safely be repeated.

**Withdrawal.** A well in the last published state but missing from this
snapshot has stopped being public or lost its last level. `publish` deletes its
files and `register` deletes its STAC item and static JSON. Leaving them up
would keep publishing data that is no longer releasable.

**Checks.** These are errors and block publication of the whole run: row counts
that differ from the database (Parquet or CSV), schema drift, null ids or
datetimes, rows out of time order, and missing GeoParquet `geo` metadata.
Depths outside `[-500, 5000]` ft are only *warnings*. Legacy data contains a few
such values, and one bad old reading should not freeze every other well. The
warnings appear in `gwl_checks` metadata.

**STAC before OCO-78.** `register` always writes the item as static JSON beside
the files. It upserts to the STAC API only when `STAC_API_URL` is set, using the
Transactions extension: `POST`, then `PUT` on 409. When the configured URL
differs from the one recorded in the state, which includes the first time a URL
is configured, every published well is upserted, so the API catches up with no
manual backfill.

**One run at a time.** Two runs interleaving steps on one bucket would corrupt
the state. The job carries the tag `ocotillo/export=gwl`. Add a run-queue limit
for it in the Dagster+ deployment settings:

```yaml
run_queue:
  tag_concurrency_limits:
    - key: ocotillo/export
      value: gwl
      limit: 1
```

## File format (provisional)

The columns are listed in `rules.COLUMNS`: `well_id, thing_id, observation_id,
datetime (UTC), depth_to_water_bgs, depth_to_water_below_mp,
measuring_point_height, unit, measurement_method, data_quality,
groundwater_level_reason, longitude, latitude`, plus a WKB `geometry` in the
Parquet. Rows are in long format, sorted by `datetime`. The Parquet is ZSTD
compressed with GeoParquet 1.1 metadata (CRS84). The CSV is UTF-8 with a BOM,
so Excel reads it correctly, and its times are ISO 8601 `Z`. The column list
still awaits AMP review on OCO-79. Changing it means editing `COLUMNS` and
bumping `FORMAT_VERSION`.

"Public" follows the `NGWMN_WaterLevels` rule: every level of the observation's
lineage is released, and the well's current location must be public too,
because the file carries its coordinates. The SBAC definition of public versus
internal wells is still open on OCO-79. `PUBLIC_LEVELS_CTE` in `snapshot.py` is
the single place to change it.

## Standing it up

Nothing below has been applied. Do it per environment, staging first.

1. **Terraform.** Add the environment to `gwl_export` in `terraform.tfvars`
   (see the example file). Leave `public_read` false until the SBAC question is
   settled. Then `terraform plan`, review it, and apply.
2. **Database grants.** Run `automated_ingestion/sql/gwl_export_role.sql`
   against the primary, as described in its header.
3. **Image.** Build and push from the repo root:
   `docker build -f docker/gwl_export/Dockerfile -t <tag> .` then
   `gcloud run jobs update gwl-export-<env> --image <tag> --region us-west4`.
   Terraform ignores image changes after creation.
4. **Dagster+ environment variables** on the code location, taken from the
   `gwl_export` Terraform output: `GWL_EXPORT_ROOT`,
   `GWL_EXPORT_CLOUD_RUN_PROJECT`, `GWL_EXPORT_CLOUD_RUN_REGION`,
   `GWL_EXPORT_CLOUD_RUN_JOB`. The existing `INGESTION_GCP_CREDENTIALS_JSON`
   supplies the credentials. Also add the run-queue limit shown above.
5. **First run.** Materialize the `groundwater_level_export` group by hand. The
   first run converts every well. Once it looks right, turn on
   `groundwater_level_export_nightly`.

To run a step locally against a directory instead of GCS:

```bash
export GWL_EXPORT_PUBLIC_BASE_URL=http://localhost:8080
python -m automated_ingestion.exports.groundwater_levels.worker snapshot --snapshot-id dev-1 --root ./gwl-out
```

## Open questions from OCO-79 and what this does for now

| Question | Current behaviour |
|---|---|
| Single statewide file too? | Not built. The snapshot Parquet in `_runs/` already is one, so publishing it would be a small extra step. |
| Versioned paths or overwrite? | Overwrite at fixed paths. Bucket object versioning keeps prior files for 30 days. |
| Sensor (continuous) data? | Excluded. Manual `groundwater level` observations only. |
| Depth to water, elevation, or both? | Depth below ground surface and below the measuring point. No elevation. |
| Snapshot schedule | Nightly at 02:15 America/Denver, off by default. |
