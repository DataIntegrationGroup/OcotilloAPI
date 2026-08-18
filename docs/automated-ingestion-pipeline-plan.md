# Draft: Automated Ingestion Pipeline Epic (BDMS)

1 new Epic → 4 Tasks → 17 Sub-tasks. **Nothing written to Jira yet.**

## TL;DR

Build the Bureau's first automated data ingestion pipeline, in the OcotilloAPI repo, so continuous depth-to-groundwater readings reach Ocotillo on a schedule instead of by hand. San Acacia Reach (33 Van Essen divers) is the pilot source; the structure it establishes is what every later source inherits.

Stack: **Dagster+** code location → **dlt** extraction → **GCS** raw parquet → **`domain/`** mapping → direct **Postgres** load. Watermark and backfill mechanics are ported from Aqueduct, with two deliberate improvements a relational destination allows: the watermark is read from Postgres rather than a GCS sidecar, and an upsert replaces Aqueduct's delete-then-repost (removing its known window where data goes temporarily missing).

**Decided** — four calls already made, so reviewers don't reopen them:

- **Owned by OcotilloAPI, not Aqueduct.** The loader writes over a direct database connection, which wants the `db/` SQLAlchemy models and `domain/` rules in the same process. Running it as a third Aqueduct source would mean maintaining a copy of Ocotillo's schema in another repo. Aqueduct stays the FROST/SensorThings pipeline; shared code is **ported, not imported**, so the two can diverge without breaking each other.
- **Ground-surface datum.** `TransducerObservation.value` stores depth to water below ground surface, in feet. That picks Van Essen's `gs` arrays and drops `vrd` entirely. No measuring-point correction on ingest — `domain/water_levels.py`'s MP reconciliation belongs to the manual-measurement path, where a field crew measured the height on the day. Datum shifts are the Hydrograph Corrector's job, downstream.
- **Public + provisional.** Visible from the first run, and marked provisional so no consumer mistakes an uncorrected diver series for a reviewed one. This matches what the retired FROST pipeline asserted for this source (`is_provisional: true`) — adopted deliberately here rather than inherited silently, which was the open question left in Aqueduct's mapping doc. It needs a schema change: `release_status` is one column, and its lexicon lists `public` and `provisional` as siblings, so visibility and maturity — two orthogonal axes — currently collide.
- **Vendor approval flag ≠ Ocotillo review status.** Van Essen's `approvedWaterLevels*` records what *the vendor* approved. Ocotillo's `review_status` is `approved` / `not reviewed`, and `TransducerObservationBlock.reviewer_id` FKs a Bureau `Contact` — so `approved` asserts a Bureau human reviewed it. Mapping one onto the other would manufacture provenance that doesn't exist. All San Acacia blocks land `not reviewed`; the vendor flag is preserved as a separate per-row attribute.

**Watch:** two schema changes — a unique constraint on `transducer_observation`, and a new field because `release_status` cannot hold "public" and "provisional" at once. The vendor blocker cleared on 2026-08-18: the readings endpoint works, but only through the private Diver-HUB API, only with a 1-hour JWT, and only in bounded time windows.

**Sequencing:** Task 1 gates everything. Tasks 2 and 3 run largely in parallel after it. Nothing is vendor-blocked any more.

## All tasks

| # | Item | In one line | Blocked by |
|---|---|---|---|
| **T1** | **Foundations** | Package, Dagster+ code location, GCS, DB connectivity | — |
| 1.1 | Scaffold package + Dagster skeleton | `automated_ingestion/` layout, deps, loads in `dagster dev` | — |
| 1.2 | Register Dagster+ code location | `dagster_cloud.yaml` + prod/branch deploy workflows | 1.1 |
| 1.3 | GCS buckets + service account | `ocotillo-ingestion-{production,staging}`, date-partitioned layout | — |
| 1.4 | DB connectivity + least-privilege role | Cloud SQL connector from serverless; scoped Postgres role | 1.2 |
| **T2** | **Source extraction** | Van Essen API → GCS raw zone | T1 |
| 2.1 | Confirm endpoint + finalize mapping | **Unblocked.** Diver-HUB swagger, JWT login, measure the window ceiling | — |
| 2.2 | dlt resource: locations | 33 wells, `replace`, one call, no pagination | 1.3 |
| 2.3 | dlt resource: readings, incremental | Windowed per-point fetch, dlt cursor, `append`, token refresh, failure isolation | 2.1 |
| **T3** | **Domain mapping + load** | Van Essen records → Ocotillo Postgres | T1 |
| 3.1 | Domain layer | Pure functions: units, datum, timestamps, geometry, external keys | — |
| 3.2 | Bootstrap reference data | Reconcile 33 wells; seed parameter, sensor, deployments | 3.1 |
| 3.3 | Represent "public but provisional" | **Schema change.** `release_status` can't hold both axes | — |
| 3.4 | Unique constraint + upsert loader | **Schema change.** `ON CONFLICT DO UPDATE`; makes backfill idempotent | 3.2, 3.3 |
| 3.5 | Watermark from Postgres | `MAX(observation_datetime)` per series; no GCS sidecar | 3.4 |
| **T4** | **Backfill + operations** | Recover from gaps, bugs, and vendor corrections | T3 |
| 4.1 | Port shared backfill primitives | `month_chunks`, `BackfillCheckpointStore`, `ChunkResult` from Aqueduct | — |
| 4.2 | Mode A — refetch | Re-fetch from API for a window; `dry_run: true` default; chunked, resumable | 4.1, 2.3 |
| 4.3 | Mode B — replay | Reprocess GCS parquet through the current adapter; no API calls | 4.1, 3.4 |
| 4.4 | Schedule, observability, alerting | Daily schedule, log bridge, failure notification, run metadata | 4.2 |
| 4.5 | Documentation | Source mapping, storage conventions, backfill runbook, new-source checklist | 4.3 |

---

# EPIC — Automated Ingestion Pipeline

**Goal:** continuous depth-to-groundwater data lands in Ocotillo automatically, on a schedule, with no one hand-carrying files — starting with San Acacia Reach.

The Hydrograph Corrector UI exists and works (BDMS-1137 done), but has no automatic supply of raw data. San Acacia Reach's 33 Van Essen divers historically flowed through the retired FROST/`st2` stack and now flow nowhere. This epic builds the supply. Correction, review, and publication workflows are **out of scope** and belong to their own epic.

New top-level `automated_ingestion/` package in OcotilloAPI, deployed as its own Dagster+ code location in the existing `nmbgmr-data-services` org. dlt extracts the Van Essen API to a GCS raw zone; a `domain/` layer maps to the Ocotillo model; a loader writes to Ocotillo Postgres over a direct DB connection. Watermark and backfill mechanics come from Aqueduct.

San Acacia first: 33 wells, one DTW series each, and already mapped in `Aqueduct/docs/sources/san_acacia.md`. It authenticates with a short-lived JWT and must be read in bounded time windows — both cheap enough here to establish the pattern before a harder source needs it. What it establishes — source registry, per-source dlt pipeline, adapter, backfill job factory — every later source inherits.

**Ownership: OcotilloAPI.** Not a third Aqueduct source writing into Ocotillo. The loader writes over a direct database connection, which wants the `db/` SQLAlchemy models and `domain/` rules in-process rather than a duplicated schema in another repo. Aqueduct stays the FROST/SensorThings pipeline; this is Ocotillo's own. The two share code by porting (see below), not by importing.

### Adopted from Aqueduct

| Artifact | Adoption |
|---|---|
| `docs/BACKFILL_STRATEGY.md` | Wholesale: Mode A refetch / Mode B replay, per-source generated jobs, calendar-month chunking, `dry_run: true` default, `initial_start_date` as a floor only |
| `shared/backfill.py`, `shared/gcs.py` | Port near-verbatim — already destination-agnostic |
| `shared/source_registry.py` | Port the pattern; registry drives job + schedule generation |
| `canonical/base_adapter.py` | Adapt: same `extract`/`to_*`/`run` shape and per-record failure isolation, emitting Ocotillo structs |
| `loader/watermark_store.py` | **Adapt, not port** — see deviation 1 |
| `docs/STORAGE_CONVENTIONS.md` | Adopt, renamed for `ocotillo-ingestion-<env>` |

### Deviations from Aqueduct

1. **Watermark in Postgres, not a GCS sidecar.** Aqueduct needs `_frost_watermarks.json` because FROST has no transactional read. Ocotillo's destination does: `MAX(observation_datetime)` per `(thing_id, parameter_id)`, read in the write transaction. No sidecar drift, no recovery path.
2. **Upsert replaces delete-then-repost.** `BACKFILL_STRATEGY.md` §4.4 accepts a temporary hole in FROST because observations have no dedup key there. Postgres does — unique constraint plus `ON CONFLICT DO UPDATE` makes load and backfill idempotent with no destructive delete. Resolves that doc's §6 open question.
3. **Target is `Thing → Deployment → TransducerObservation`**, not `FieldEvent → … → Observation`. 5-minute diver series are continuous, not field visits.

### Data classification — decided

- **Datum: ground surface.** `TransducerObservation.value` = depth to water below ground surface, feet. Ingest Van Essen's `gs` arrays, not `vrd`. No measuring-point correction on ingest — `domain/water_levels.py`'s MP reconciliation is the manual-measurement path. Datum shifts are the corrector's business.
- **Visibility public, maturity provisional.** Public from the first run, marked provisional so nobody mistakes an uncorrected diver series for a reviewed one. Matches what the old FROST pipeline asserted (`is_provisional: true`) — adopted deliberately, not inherited silently.
- **Schema cannot express this today.** `release_status` is one scalar column (`ReleaseMixin` → `lexicon_term.term`), and its lexicon category holds `public` *and* `provisional` as siblings. Visibility and maturity are orthogonal; the lexicon conflates them. Sub-task 3.3 resolves it.
- **Vendor approval ≠ Ocotillo review status.** `approvedWaterLevels*` records what the *vendor* approved. Ocotillo `review_status` is `approved` / `not reviewed`, and `TransducerObservationBlock.reviewer_id` FKs a Bureau `Contact` — `approved` means a Bureau human reviewed it. All San Acacia blocks land `not reviewed`; the vendor flag is kept as a separate per-row attribute.

### Epic acceptance criteria

- `automated_ingestion/` deploys as a Dagster+ code location on merge; jobs visible in the Dagster UI.
- Scheduled job runs end to end: Van Essen API → GCS parquet → domain mapping → Ocotillo Postgres.
- Re-running over an already-loaded window: zero duplicates, zero errors.
- Both backfill jobs exist, default `dry_run: true`, chunk by month, resume from last completed chunk.
- 33 wells resolve to `Thing` records — matched or created, no duplicates.
- Readings are public, marked provisional, stored as DTW below ground surface in feet.
- Series render in the Hydrograph Corrector.
- Domain mapping unit-tested with no database, per `ADR4.md`.

### Blocker — resolved 2026-08-18

The 500s were never a vendor outage. Two things were wrong on our side, both reported by Chase Martin:

1. **Wrong API.** Readings come from the private Diver-HUB API — `GET https://diver-hub.com/private/api/v1/DiverData/ByMonitoringPoint/{id}` — not the doubled-segment `/api/api/monitoringPoint/{project}/{id}` path the earlier draft assumed. Swagger: `https://diver-hub.com/private/swagger/index.html`, which is now the authority over anything inferred from retired FROST data.
2. **Window too large.** The endpoint 500s rather than paginating or erroring cleanly when asked for too much. A confirmed-good request is a ~3-month window in **Unix seconds**:

   ```
   https://diver-hub.com/private/api/v1/DiverData/ByMonitoringPoint/40?startTime=1767225600&endTime=1775001600
   ```

**Auth:** POST to the login endpoint with the credentials Ethan circulated; it returns a **JWT valid for one hour**. This overturns the "unauthenticated" assumption in the earlier draft and has two consequences: the token is a secret needing the same handling as the DB credentials, and any run outliving an hour — every backfill — must refresh mid-run rather than acquire once at start.

**Still open:** the actual window ceiling. Three months works; the limit is unmeasured. Until it is, chunk conservatively and treat a 500 as "too much data" rather than a hard failure.

### Related

BDMS-1137 (corrector zoom/selection, Done — the consumer of this data, not part of this epic) · BDMS-1090 (Wellpy Revival Discovery) · BDMS-362 (WellPy Ocotillo) · `DataIntegrationGroup/Aqueduct` · OcotilloAPI `ADR4.md`, `db/transducer.py`, `db/engine.py`

---

# TASK 1 — Foundations: code location, GCS, DB connectivity

Nothing in this repo runs on a schedule today. This task creates the package, gets it deploying to Dagster+, provisions GCS, and proves the Dagster runtime can reach Ocotillo Postgres. Carries the workstream's two infrastructure risks: build size and serverless→Cloud SQL connectivity.

**Done when:** package loads in `dagster dev`; merge deploys to prod and PRs produce branch deployments; buckets exist with a least-privilege SA; a trivial asset reads Ocotillo Postgres from both deployments; pytest/ruff/mypy pass.

### 1.1 — Scaffold `automated_ingestion/` and the Dagster skeleton

```
automated_ingestion/
├── defs/           definitions.py (entry point), assets/, jobs/backfill.py
├── shared/         source_registry.py, backfill.py, gcs.py, http.py
├── ocotillo/       adapter base + Ocotillo structs
├── sources/san_acacia/   ingest / dlt_pipeline / adapter / transform / backfill
└── tests/
```

- Layout above created; `automated_ingestion` added to `[tool.setuptools] packages` (same fix as `f33cd063` for `domain`).
- Deps added: dagster, dagster-cloud, `dlt[filesystem,gs]`, gcsfs, pyarrow. `[tool.dagster] module_name = "automated_ingestion.defs.definitions"`.
- `dagster dev` loads the location with no import errors; ruff/mypy cover it; pytest still green.

Lives in this repo so the loader can import `db/` models and `domain/` rules rather than duplicate the schema. If the Dagster+ build proves too large, fall back to a `[project.optional-dependencies]` split.

### 1.2 — Register as a Dagster+ code location with CI deploy

Files written; nothing deployed yet — the secrets do not exist, so neither workflow has run.

- ✅ `dagster_cloud.yaml` declaring `ocotillo-automated-ingestion` → `automated_ingestion.defs.definitions`, build directory `./`. The build directory is the repository root, not `automated_ingestion/`, because the loader imports `db/` and `domain/`.
- ✅ `CD_dagster_prod.yml` and `CD_dagster_branch.yml`, both on `dagster-io/dagster-cloud-action@v1.13.18` — pinned to the same version as the installed dagster.
- ✅ Path-filtered to `automated_ingestion/**`, `dagster_cloud.yaml`, `pyproject.toml`, and `uv.lock`. The last two matter: the location's dependency set is exported from them, so a lockfile bump changes the built image even when no ingestion file moves.
- ⬜ `DAGSTER_CLOUD_API_TOKEN` as a repository **secret**, `DAGSTER_CLOUD_ORGANIZATION_ID` as a repository **variable**. The token is a CI credential the action uses to reach Dagster+, so it belongs with `CLOUD_DEPLOY_SERVICE_ACCOUNT_KEY` rather than in Secret Manager -- reading it from Secret Manager would still require a GitHub secret to authenticate to GCP first, adding a hop without removing a trust root. The organization ID is not sensitive; it appears in the Dagster+ console URL.
- ⬜ Runtime secrets are a different question and are **not** GitHub's. The Diver-HUB login (2.1), the ingestion service account (1.3), and the Postgres role (1.4) are read by the pipeline while it runs, not by the deploy, so they belong in Secret Manager on the `internal-ogc-api-keys` precedent, reached from Dagster+ at runtime.
- ⬜ Test PR yields a working branch deployment; merge to `production` yields a working prod location.

**Prod deploys from `production`, not `main`.** `main` was abandoned in July 2025 — it is 3,839 commits behind and is not part of the release flow (`docs/release-flow.md`). The `main` reference in the original draft was inherited from Aqueduct's layout without checking this repository's.

**PEX vs Docker — answered: Docker.** `serverless_prod_deploy` and `serverless_branch_deploy` build with `docker/build-push-action` and a copied Dockerfile template; there is no PEX fast-deploy path in these actions. So build time is a full image build, and the dependency set matters: the image installs all 197 exported packages (the 135 runtime ones plus dagster, dlt, gcsfs, pyarrow). `pymssql` and `psycopg2-binary` are in that set and compile from source on some base images — the first real build is where that surfaces.

**Ordering constraint, easy to break.** `utils/parse_workspace` runs its own `actions/checkout`, which cleans the working tree. It must run *before* `requirements.txt` is generated; putting the generation first silently deletes it, and the deploy fails on a missing file rather than on the real cause.

Both workflows generate `requirements.txt` with `uv export --group ingestion`, since Dagster+ builds from a requirements file and the repository does not keep one under version control.

### 1.3 — Provision GCS buckets and ingestion service account

Terraform written in `automated_ingestion/iac/`; **not applied**. `terraform validate` and `fmt` pass, but no GCP credentials were available, so no resource exists yet.

- ✅ `ocotillo-ingestion-production` and `-staging`, uniform bucket-level access, public access prevention enforced, `force_destroy = false`.
- ✅ Service account `ocotillo-ingestion` with `roles/storage.objectAdmin` bound **on the two buckets**, not at project level. `objectAdmin` rather than `objectCreator` because a Mode B replay overwrites an existing object.
- ✅ Lifecycle: NEARLINE at 30 days, COLDLINE at 365, and archived-version pruning past 3. Aged out rather than deleted — an old window is exactly what a historical replay reads.
- ✅ `INGESTION_GCS_BUCKET` resolved by `shared/gcs.raw_zone_bucket()`, which raises rather than defaulting and explicitly rejects a value equal to `GCS_BUCKET_NAME`. `services/gcs_helper.py` uses that variable for user uploads; the two being confused would write raw vendor payloads into the uploads bucket, and would otherwise do so silently.
- ⬜ `terraform apply`, then set `INGESTION_GCS_BUCKET` on the Dagster+ code location.

The dlt layout `{table_name}/year={YYYY}/month={MM}/day={DD}/{load_id}.{file_id}.{ext}` is asserted by a test, because Mode B replay selects a window by prefix — the date has to be in the path, not inside the file.

### 1.4 — DB connectivity from Dagster+ with a least-privilege role

Dagster+ Serverless is outside the VPC, so Cloud SQL's private IP is unreachable from it. Code written; **nothing run against a database**.

- ✅ `OcotilloDatabase` resource delegating to `db/engine.py`'s `DB_DRIVER=cloudsql` path rather than building a second engine. The import is lazy: `db.engine` builds its engine at import time, and a code location that needs a reachable database merely to *list* its assets breaks every time the database blips. A test asserts loading the definitions leaves `db.engine` unimported.
- ✅ `database_connectivity` asset, read-only. Connectivity and grants are separable problems, and a write here would leave test rows in a real table.
- ✅ Role DDL in `automated_ingestion/sql/ingestion_role.sql`, kept out of Alembic: roles and grants are per-environment infrastructure, not schema, and migrations do not run as a superuser.
- ⬜ Run the DDL per environment; set `DB_DRIVER`, `CLOUD_SQL_*` on the code location; materialize the asset from both a branch and prod deployment.

**The grant list is narrower than the draft assumed, and one part of it is non-obvious.** Writable: `transducer_observation`, `transducer_observation_block`, `deployment`, `sensor`, `parameter`. Read-only: `thing`, `thing_id_link`, `location`, and the three `lexicon_*` tables — `thing` and `location` deliberately *not* writable, because reconciling the 33 wells means matching rows that already exist. A well found missing is a decision for a human, not a row the pipeline invents.

`parameter` is versioned by sqlalchemy-continuum, so inserting one also writes to `parameter_version` and `transaction`. Without those two grants the write fails on a table the code never names — the kind of error that costs an afternoon. (`transducer_observation` itself is not versioned; only `aquifer_system`, `geologic_formation`, `location`, `observation`, `parameter`, `regulatory_limit`, and `thing` are.) Sequence `USAGE` is granted explicitly, and no default privileges are set: a table added later stays invisible until someone grants it deliberately.

Fallback if the connector path fails: Hybrid agent in GCP.

---

# TASK 2 — Source extraction: Van Essen → GCS raw zone

Land locations and readings untransformed in GCS as date-partitioned parquet. Raw storage is what makes Mode B replay possible — a mapping bug becomes a reprocess, not a re-fetch. Carries the external blocker.

**Done when:** both land at the documented paths; readings extraction is incremental; a per-entity failure doesn't abort the run; fixtures exist so downstream work needs no live API.

### 2.1 — Confirm the readings endpoint; finalize the source mapping

**Unblocked.** The endpoint works; the 500s were a wrong path plus an oversized window (see Blocker). Mapping details inferred from retired FROST data can now be checked against live responses and against the Diver-HUB swagger.

- Authenticate: POST credentials to the login endpoint, hold the 1-hour JWT, re-acquire on expiry or on a 401. Credentials and token never committed and never logged.
- Measure the window ceiling. Three months is known-good; find where it breaks so the chunk size is chosen rather than guessed. Record the number here.
- Confirmed against live responses: `ts` format and timezone; `gs` unit is feet; `approvedWaterLevelsGs` and `unApprovedWaterLevelsGs` are the complete, non-overlapping set; whether `groundSurfaceData` elevation is needed and how it's time-scoped.
- Reconcile the swagger against `docs/sources/san_acacia.md`: the locations endpoint and the `/api/api/` doubled segment were both taken from the old assumption and may not survive.
- `drillingDepth` centimetres (÷ 30.48) confirmed, not back-calculated.
- Fixture responses committed for tests, credentials scrubbed.
- `docs/sources/san_acacia.md` copied into OcotilloAPI and corrected.

Datum and vendor-flag questions are already settled in the Epic — `vrd` is not ingested, and the vendor flag does not map to `review_status`.

### 2.2 — dlt resource: locations → GCS

- `@dlt.resource(name="vanessen_locations")` on `GET /api/api/locations/sanacaciareach`; no pagination, all 33 in one response. `write_disposition="replace"`.
- HTTP layer: timeouts, bounded retries with backoff, clear failure message. Doubled `/api/api/` segment preserved — confirmed, not a typo.
- Asset `raw_san_acacia_locations` emits row-count metadata. Tested against fixture, no network.

### 2.3 — dlt resource: readings → GCS, incremental

- `@dlt.resource(name="vanessen_readings")` per monitoring point, dlt incremental cursor on reading timestamp, `write_disposition="append"`.
- **Windowed requests.** `DiverData/ByMonitoringPoint/{id}` takes `startTime`/`endTime` as Unix seconds and 500s on an oversized span, so a fetch is always a sequence of bounded windows — never one open-ended call. This is true of the daily incremental run too, not just backfill: an entity whose cursor has fallen months behind must walk forward in chunks.
- **Token refresh mid-run.** The JWT expires after an hour. Refresh on expiry and retry once on a 401; a multi-hour backfill must not die at minute 61.
- Treat a 500 on a windowed request as a signal to halve the window and retry, not as a dead entity — the endpoint reports "too much data" that way.
- `initial_start_date` in `.dlt/config.toml`, documented as a floor for entities with no cursor yet — never a backfill lever (`BACKFILL_STRATEGY.md` §2).
- Vendor approved/unapproved flag preserved per row.
- Per-entity failure doesn't abort the run; failures counted and surfaced as asset metadata.
- Asset `raw_san_acacia_readings` emits rows-ingested and entities-failed. Tested against fixtures.

---

# TASK 3 — Domain mapping and load into Ocotillo

Where this stops resembling Aqueduct: the destination is a relational database with constraints and transactions, and mapping rules belong in `domain/` per `ADR4.md`. Three risks — matching 33 wells without duplicating them, representing "public but provisional" when the schema can't, and making the write idempotent so backfill is safe.

**Done when:** mapping rules are pure functions tested without a database; 33 wells resolve with no duplicates; data is public and separately marked provisional; `transducer_observation` has a unique constraint and the loader upserts against it; loading the same window twice leaves the row count unchanged; the watermark comes from Postgres.

### 3.1 — Domain layer: Van Essen record → Ocotillo model

Per `ADR4.md`, `domain/` imports nothing from `api/`, `db/`, `schemas/`, `services/`, and no fastapi/sqlalchemy/pydantic/httpx.

`domain/van_essen.py`, pure functions:
- `drillingDepth` cm → ft (÷ 30.48), reusing `domain/units.py` where it fits
- reading timestamp → tz-aware UTC `datetime`
- `gs` reading → DTW below ground surface, feet (datum fixed — see Epic)
- `lat`/`lng` → WGS84 point (SRID 4326)
- deterministic external key per well and per series, so repeat runs resolve to the same records

Plus an adapter in Aqueduct's `BaseAdapter` shape, with the same per-record failure isolation: a bad record is logged and counted, never fatal. Domain errors subclass `ValueError`, matching the CSV importers' per-row contract. Tests need no database and no network. Every value the mapping *invents* rather than reads is listed in the module docstring with its justification.

### 3.2 — Bootstrap reference data: reconcile wells, seed parameter, sensor, deployments

Some of the 33 may already exist in Ocotillo under Bureau point IDs. Duplicates are the main risk — the `group_type` collision elsewhere in this database is the reminder that "looks new" isn't proof.

- Reconciliation report **first**: per well, whether a matching `Thing` exists — on name, on `monitoringPoints[].name` (e.g. `SO-0125`), and on coordinate proximity. Ambiguous matches escalate to a human, never auto-merge.
- Data migration (existing `data_migrations/` runner, already supports dry-run) creates missing `Location`/`Thing`, links existing ones. Idempotent, dry-run-clean before running for real.
- Lexicon terms, a DTW `Parameter`, and a `VanEssenDiver` `Sensor` created if absent.
- One `Deployment` per well (thing → sensor), `recording_interval` ~5 min where known.
- Van Essen `uid` (e.g. `sanacaciareach-40`) persisted as external identifier.
- `DataProvenance` recorded for Van Essen-sourced well attributes: depth, coordinates, installation date.

### 3.3 — Represent "public but provisional"

`release_status` is one scalar column and its lexicon category holds `public` and `provisional` as siblings, so both cannot be set. Visibility and maturity are orthogonal axes.

- Decide the representation. Recommended: keep `release_status = "public"` for visibility, add an explicit maturity field (`is_provisional` boolean, or a `data_maturity` lexicon term) on `TransducerObservation` / `TransducerObservationBlock`. Rejected alternative: overloading `review_status`, which means Bureau review and carries a `reviewer_id` FK.
- Follow the Model Change Workflow in `CLAUDE.md`: db model → schemas → alembic migration → tests → transfer scripts.
- Provisional state is visible wherever the data surfaces — API responses and the Hydrograph Corrector.
- Check the blast radius of `release_status = "public"` before shipping: `services/ngwmn_helper.py` filters `Thing.release_status == "public"` for NGWMN publication. Confirm San Acacia data becoming public is intended there too.
- Existing rows keep their current behavior; the migration has a defined default.

### 3.4 — Unique constraint on `transducer_observation` + idempotent upsert loader

`db/transducer.py` defines only an index — no unique constraint, so nothing prevents inserting the same reading twice. That absence is what forces Aqueduct's delete-then-repost in FROST.

- Alembic migration adds `UniqueConstraint(thing_id, parameter_id, observation_datetime)`. Existing duplicates found and resolved first — the migration must not fail on production data.
- Loader batches and issues `INSERT … ON CONFLICT … DO UPDATE`, through the `db/` SQLAlchemy models, not raw SQL. Batch size tuned and documented; a full backfill month fits in memory; each batch commits in its own transaction.
- `TransducerObservationBlock` rows created/extended for the loaded window, `review_status = "not reviewed"`.
- Loader reports rows inserted, rows updated, adapter failures as Dagster metadata.
- Test: loading the same window twice leaves the row count unchanged.

### 3.5 — Watermark from Postgres

- Keep Aqueduct's `WatermarkStore` interface; Postgres implementation returns `MAX(observation_datetime)` for a `(thing_id, parameter_id)`, read in the same session as the write. No GCS sidecar for normal runs.
- Backfill never advances the normal watermark implicitly — inherent with upsert, but asserted in a test.
- In-memory implementation kept for tests. First-ever run for a series falls back to the `initial_start_date` floor.
- Divergence from Aqueduct recorded in the module docstring, so it reads as a decision not an oversight.

---

# TASK 4 — Backfill and operations

A forward-only pipeline isn't enough. `BACKFILL_STRATEGY.md` §3 lists twelve situations demanding backfill; most come from ongoing operation, not onboarding — outage gaps, vendor corrections, adapter bugs found later, newly mapped properties.

**Done when:** both backfill jobs are registry-generated, unscheduled, default `dry_run: true`, chunk by month sequentially in one run, and resume from the last completed chunk; the daily pipeline is scheduled and alerts a human on failure; docs carry the runbook.

### 4.1 — Port shared backfill primitives from Aqueduct

- `month_chunks()`, `ChunkResult`, `sum_chunk_results()`, `parse_backfill_date()`, `validate_date_order()`, `attach_run_timestamp()`, `sanitize_run_key()`, `resolve_location_ids()`, `chunk_key()`, `BackfillCheckpointStore` → `automated_ingestion/shared/backfill.py`. `atomic_write_json_with_retry()` → `shared/gcs.py`.
- `ChunkResult` adjusted for Postgres: `rows_upserted` replaces `observations_posted`/`observations_deleted`.
- Aqueduct's tests ported alongside and passing.
- Each docstring notes provenance and what changed, so the two can be diffed later.

### 4.2 — Backfill Mode A (refetch)

Covers data never ingested: onboarding, a late-added well, an outage gap beyond the retry budget, a vendor correction, extending history past the original floor (§3A).

- `san_acacia_backfill_refetch`, generated from the registry via a factory so a second source needs a registry entry, not new wiring. No schedule; launched from the Launchpad.
- Run config: `location_ids` (empty = every location the API returns), `start_date`, `end_date`, `run_key`, `dry_run`.
- **`dry_run: true` default.** Logs the full plan — entities, range, chunk list, expected counts — making exactly one read-only API call to resolve and validate the entity list, writing nothing.
- An unknown `location_id` fails the run naming the bad IDs, rather than silently backfilling nothing.
- Calendar-month chunks, sequential within one Dagster run — one billed run regardless of chunk count.
- Ingest writes to `vanessen_backfill_readings` under isolated dlt pipeline state, so backfill can't roll back or race the scheduled cursor.
- A chunk checkpoints only after ingest + transform + load all succeed; same `run_key` resumes from the last completed chunk.
- Same idempotent upsert as normal load — no delete step, no window where data is missing.
- Metadata reports per-chunk and total rows ingested, rows upserted, adapter failures.

### 4.3 — Backfill Mode B (replay)

Covers raw already in GCS with only the mapping wrong: adapter or unit bug, newly mapped property, storage migration, upstream rename, Ocotillo-side loss with parquet intact (§3B). Aqueduct notes this is almost entirely generic — build it that way.

- `san_acacia_backfill_replay` from the same factory. Never contacts the Van Essen API.
- Reads raw parquet for an explicit range, filtered on event time, re-running the source's *current* adapter — so fixing a domain bug and replaying picks it up automatically.
- Same chunking, checkpointing, `dry_run: true` default, and upsert load path as Mode A.
- Source-agnostic: a second source gets replay free once it has an adapter and a registry entry. Anything that can't be generic is called out in the docstring.
- Test: a deliberately wrong mapping, once corrected, is fully repaired by a replay over the affected window.

### 4.4 — Schedule, observability, alerting

- `san_acacia_schedule` runs the daily pipeline; cron avoids contention with existing Dagster+ jobs in the org, recorded in the source registry.
- Dagster logs bridge into the repo's existing logging setup, so ingestion failures surface where the team already looks. Confirm which error-tracking destination is current before wiring this — do not assume the repo's existing integrations are live.
- A failed run notifies someone — not discovered via a stale hydrograph.
- Every run emits rows ingested, rows upserted, entities processed, entities failed, adapter failures, resulting watermark per series.
- A zero-new-rows run succeeds and is distinguishable in the logs from a failure.

### 4.5 — Documentation

- `docs/sources/san_acacia.md` — confirmed mapping.
- `docs/ingestion-storage-conventions.md` — bucket/dataset/table naming, date partitioning, control-file convention, checklist for adding a source or agency.
- `docs/ingestion-backfill.md` — Modes A and B, chunking, checkpoints, `dry_run` policy, and why Ocotillo upserts where Aqueduct deletes-then-reposts.
- `automated_ingestion/README.md` — architecture, local dev, deploy path. Runbook: launching each mode, reading a dry-run plan, recovering a failed run.
- `CLAUDE.md` section pointing at the above, in the style of the existing "Domain Rules" section.
- "Adding a new source" checklist usable without reading the San Acacia implementation.

---

## Open questions

1. **Provisional representation** (3.3) — new boolean, new lexicon category, or something else? Recommendation is in the sub-task.
2. **NGWMN** — `release_status = "public"` makes San Acacia wells eligible for NGWMN publication via `services/ngwmn_helper.py`. Intended?
3. **Epic name** — keep "Automated Ingestion Pipeline", or use "Hydrograph Corrector" as originally asked?
