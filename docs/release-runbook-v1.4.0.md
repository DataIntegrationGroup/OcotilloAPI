# Release runbook: API v1.4.0 + UI production promotion

Operational steps for the next production release. The mechanics of the branch
flow live in [`docs/release-flow.md`](release-flow.md); this runbook is the
ordered checklist for *this* release, with the prerequisites and manual steps
that the pipeline does not do for you.

| | Current production | Shipping |
|---|---|---|
| OcotilloAPI | `v1.3.0` | `v1.4.0` |
| OcotilloUI | `production` @ current | `staging` → `production` (unversioned) |

- API: 116 commits ahead of `production` (22 `feat`, 15 `fix`, 1 `perf`)
- API: 9 new Alembic revisions, 7 new data migrations
- UI: 27 commits ahead of `production` (7 `feat`)
- Open RC PR: `chore(staging): release 1.4.0-rc.1` (#905)

## Read this first: three things that can break the release

**1. The Authentik group names changed.** `LexiconAdmin` → `Lexicon.Admin`,
`LexiconEditor` → `Lexicon.Editor`, `OGCInternal` → `OGC.Internal` (PR #922),
and the whole AMP family: `AMPAdmin` → `AMP.Admin`, `AMPEditor` → `AMP.Editor`,
`AMPViewer` → `AMP.Viewer`. The moment `v1.4.0` deploys, every lexicon editor,
every internal-OGC consumer, and **every AMP user at every tier** loses access
until the groups exist with their members carried over. This is the one
prerequisite that must be done *before* the production deploy, not after. The
standalone `AMP.Staging` group is gone — the hydrograph corrector's writes now
sit on `AMP.Admin`.

**2. Data migrations do not run in CD.** `CD_production.yml` runs
`alembic upgrade head` and nothing else. The seven new data migrations sit
unapplied until someone dispatches `data_migrations.yml` by hand. Until they
run, the EPA regulatory limits table is empty, casing diameters are still in
feet, and the `group` table is unconsolidated.

**3. The group table comes from the parity snapshot, not from a replay.** The
staging `group` table reached its current state through a one-off sequence
(consolidation → layer-18 import → parenting → orphan cleanup) that is not
deterministic elsewhere. Those three migrations now live in
`data_migrations/migrations/_superseded/` and are no longer in the registry, so
neither `run-all` nor `run` can reach them.
`20260905_0003_group_table_parity_with_staging` is the only registered path to
that end state and carries a snapshot of the result.

## Ordering

API ships first, UI second. The UI's new Settings page calls `/api_key`, which
does not exist in production until `v1.4.0` is live. Promoting the UI first
gives users a settings card that 404s.

```
Authentik groups ──▶ DB backup ──▶ API RC ──▶ API promotion ──▶ API release tag
                                                                      │
                                                     data migrations ◀┘
                                                                      │
                                                       UI promotion ◀──┘
```

---

## 1. Prerequisites (before any merge)

### 1.1 Authentik groups

In production Authentik, create `Lexicon.Admin`, `Lexicon.Editor`,
`OGC.Internal`, `AMP.Admin`, `AMP.Editor`, and `AMP.Viewer`, and copy the
membership of `LexiconAdmin`, `LexiconEditor`, `OGCInternal`, `AMPAdmin`,
`AMPEditor`, and `AMPViewer` into them. OcotilloUI already gates on the three
dotted AMP names, so those groups may exist already — check each one's
membership matches its undotted predecessor rather than assuming. Keep the old groups in place through the
release — they are inert to `v1.4.0` and are the rollback path if you have to
redeploy `v1.3.0`. Retire them only after the release has settled.

Verify a token actually carries the new claim before promoting: sign in as a
lexicon editor and as an AMP user at each tier, and confirm the dotted group
names appear in the tokens' groups.

### 1.2 Database backup

Take a Cloud SQL backup of the production database and note the backup id here
before starting. Data migrations have no `downgrade`, both foreign keys into
`group` are `ON DELETE CASCADE`, and the parity migration deletes rows. Alembic
revisions can be downgraded; the data migrations cannot.

```bash
gcloud sql backups create --instance=<PROD_INSTANCE> \
  --description="pre-v1.4.0 release"
```

### 1.3 Secrets and config

No new secrets. `INTERNAL_OGC_API_KEYS` (Secret Manager `internal-ogc-api-keys`)
is already wired into `CD_production.yml` on both branches. Confirm the secret
still has a version — the deploy renders `app.yaml` from it and a missing secret
fails the deploy, not the request path.

### 1.4 Freeze

Stop merging into `staging` once you cut the RC. Anything merged after the RC tag
is in the promotion diff but not in the thing you tested.

---

## 2. API: cut the RC

1. Confirm CI is green on `staging`.
2. Merge PR #905, `chore(staging): release 1.4.0-rc.1`.
3. Confirm the `v1.4.0-rc.1` tag and GitHub prerelease appear.

This is the versioned checkpoint of what you are promoting. Test against
`ocotillo-api-staging` at this tag, not at some later `staging` commit.

### Smoke the RC on staging

- `GET /health` returns OK
- `GET /docs` loads
- `GET /ogcapi/collections` lists the renamed collections
- `GET /ogcapi-internal/collections` with an Authentik token carrying
  `OGC.Internal` — and again with a static API key as a bearer token
- `POST /api_key` mints a key; `GET /api_key` lists it; revoke it and confirm
  the next request with it fails
- `GET /ogcapi-internal/collections/water_well_field_operations/items?limit=1`
  returns rows and is refused without a credential

---

## 3. API: promote to production

1. Open the promotion PR `staging → production`, titled
   `chore(release): promote staging to production for v1.4.0`.
2. Merge it. release-please opens `chore(production): release 1.4.0`.
3. Merge the Release PR. That tags `v1.4.0`, publishes the release, and invokes
   `CD_production.yml` in the same run.
4. Watch the run. `alembic upgrade head` runs against production before the App
   Engine deploy, so a failed migration means a failed deploy with the old
   version still serving.

### Schema migrations applied automatically

```
3f9c1b7d2a64  chemistry views keyed on collection date
4730aa951398  rename data provenance origin type
a2b3c4d5e6f7  split springs view to drop well columns
b3c4d5e6f7a9  split remaining non-well thing views
c5d6e7f8a9b0  project areas views, layer-18 parent
d0e1f2a3b4c5  add api_key table
d6e7f8a9b0c1  add AEM project areas views
e1f2a3b4c5d6  add water_well_field_operations layer
e7f8a9b0c1d2  index WWFO per-row lookups
```

### After the deploy

- `GET /health` on the production service
- Check `/docs` reports the new version
- `gcloud app versions list --service=ocotillo-api` shows the new version at
  100% traffic
- Lexicon editing works for a `Lexicon.Editor` member, and an `AMP.Admin`
  member can reach an AMP admin route (these are the checks that step 1.1
  actually landed)

Merge the automatic back-merge PR `production → staging` promptly. It syncs
`.release-please-manifest.staging.json` so the next RC computes from `1.4.0`.

---

## 4. API: data migrations (manual)

Run these *after* the promotion merge, from the `production` branch — the
migration files only exist on `production` once the promotion has merged.

Use the **Data Migrations** workflow (`workflow_dispatch`), ref `production`,
`environment = production`.

### 4.1 Status first

Dispatch with `action = status`. It applies nothing and prints what is registered
and what has already been applied. (It does call `ensure_history_table()`, so a
database that has never run one gets an empty `data_migration_history` table.)

### 4.2 Run these, by id, one at a time

`action = run`, one `migration_id` per dispatch:

```
20260901_0001_backfill_lexicon_category_descriptions
20260914_0001_convert_well_inventory_casing_diameter
20260916_0001_seed_epa_regulatory_limits
20260905_0003_group_table_parity_with_staging
```

`run-all` reaches the same end state — the three migrations that made it unsafe
are now unregistered, and registry order puts the parity pass after
`publish_project_areas`. Running by id is still preferred here: it gives one
workflow run per migration to read, and the parity pass deletes rows.

### 4.3 What the parity pass does

`data_migrations/migrations/20260905_0003_group_table_parity_with_staging.py`
upserts every snapshot group by name, re-parents by parent name, and prunes only
groups that are absent from the snapshot **and** safe (no thing associations, no
children) **and** either a reviewed orphan-duplicate name or an exact-boundary
duplicate of a snapshot group. Production keeps any genuine extras it has —
under-reaching is the deliberate direction.

The staging-only path it replaces
(`20260810_0001_consolidate_geographic_area_groups`,
`20260905_0001_parent_project_areas_under_layer18`,
`20260905_0002_parent_aem_project_areas`) now sits in
`data_migrations/migrations/_superseded/`. See
[`docs/bdms-1143-geographic-area-consolidation-runbook.md`](bdms-1143-geographic-area-consolidation-runbook.md)
for what it did and why it is not reproducible elsewhere.

Databases that already ran one of those keep their `data_migration_history` row.
`status` reports per registered migration, so the row simply stops being listed.
That is expected, not drift.

### 4.4 Known gap: no dry run from the workflow

`oco data-migrations run --dry-run` exists in the CLI, but `data_migrations.yml`
exposes no `dry_run` input. To preview the parity migration against production
you need local Cloud SQL credentials, or the workflow needs the input added
first. Given that the parity migration deletes rows, adding the input is worth
doing before this release rather than after.

The migration now has test coverage (`tests/test_data_migrations.py`, the
"Group table parity with staging" section), including the two cascade guards —
a snapshot-absent group carrying wells or children is kept, never deleted.

### 4.5 Verify

Re-dispatch `action = status` and confirm the four ids are recorded as applied.
Then spot-check:

- `group` row count and typed Geographic Area count against staging's
- `GET /ogcapi/collections/ogc_project_areas/items?limit=1` returns rows
- The regulatory limits endpoint returns seeded EPA rows
- A well inventory record shows casing diameter in inches, not feet

---

## 5. UI: promote to production

Only after the API is live and step 4 is done.

1. Confirm CI green on `staging` (Lint, Vitest, Cypress, production build).
2. Open and merge the promotion PR `staging → production`.
3. The push to `production` triggers `CD_production.yml`: build with production
   Vite vars, deploy to the `ocotillo` App Engine service with `promote: true`,
   delete the oldest version, push an `ocotillodev-deploy-<timestamp>` tag.

There is no version gate and no release PR — **merging to `production` ships
immediately**.

### Feature flag state

`SHOW_GIS_DOWNLOADS` (`src/config/features.ts`) defaults **off** in production
and on in dev/preview/staging. The datasets table view ships; the desktop GIS
downloads panel, column, and per-card links stay hidden, and the `/gis`
catalogue fetch is skipped entirely. To turn it on later without a code change,
set `VITE_ENABLE_GIS_DOWNLOADS` in the production environment and redeploy.

### After the deploy

- <https://ocotillo.newmexicowaterdata.org> loads and the environment badge reads
  production
- Sign in works end to end (Authentik redirect URI unchanged)
- Settings page renders; a user in `OGC.Internal` sees the API keys card, issues
  a key, renames it, revokes it
- Collections page shows the table view by default, the internal OGC tab for
  entitled users, the JSON schema modal, and **no** desktop GIS downloads
- A user not in `OGC.Internal` does not see the API keys card

---

## 6. Rollback

**API.** Redeploy the previous version rather than reverting commits:

```bash
gcloud app versions list --service=ocotillo-api --project=<PROJECT>
gcloud app services set-traffic ocotillo-api --splits=<PREVIOUS_VERSION>=1 --project=<PROJECT>
```

Schema changes stay applied. The 9 revisions are additive (new tables, new
views, view redefinitions) so `v1.3.0` code tolerates them, with one exception to
check: the chemistry and springs view redefinitions change what `v1.3.0`'s OGC
layers read. If the rollback has to persist, `alembic downgrade` to the `v1.3.0`
head and redeploy.

Data migrations do not roll back. Restore the backup from step 1.2 if the parity
migration produced a group table you cannot live with — that is the only path.

If the rollback is because of the Authentik rename, the old groups still exist
(step 1.1 said to keep them), so `v1.3.0` authorizes normally.

**UI.** Same pattern, service `ocotillo`:

```bash
gcloud app versions list --service=ocotillo --project=<PROJECT>
gcloud app services set-traffic ocotillo --splits=<PREVIOUS_VERSION>=1 --project=<PROJECT>
```

Note that `CD_production.yml` deletes the oldest version on every deploy, so the
rollback target is not guaranteed to be there indefinitely. Confirm it exists
before you need it.

---

## 7. Hotfix, if it comes to that

Do not fix forward through `staging` — that drags the whole next RC line into
production. Run the `hotfix-start` workflow (pin `base_tag=v1.4.0`), open a
`fix:` PR against `hotfix/v1.4.1`, merge the Release PR it produces, merge the
automatic forward-merge into `production`, then run `forward-merge` manually with
`source_branch=production` to carry it to `staging`. The manual step is required:
the hotfix merge into `production` cuts no release, so the automatic trigger does
not fire.

UI hotfixes branch off `production` directly and merge back to `production`, then
get carried to `staging` by hand.

---

## Post-release

- [ ] Back-merge PR `production → staging` merged (API)
- [ ] `staging` unfrozen
- [ ] Old Authentik groups (`LexiconAdmin`, `LexiconEditor`, `OGCInternal`,
      `AMPAdmin`, `AMPEditor`, `AMPViewer`, `AMP.Staging`) retired once the
      release has settled
- [ ] `dry_run` input added to `data_migrations.yml` (see 4.4)
- [ ] Parity dry run reviewed against production before 4.2 is run
- [ ] Release notes circulated — API keys, the field operations layer and its
      PII handling, the internal OGC tab, and the casing-diameter unit change
