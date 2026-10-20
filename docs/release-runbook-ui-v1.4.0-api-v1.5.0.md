# Release runbook: Release 1.4 (OcotilloUI v1.4.0 + OcotilloAPI v1.5.0)

This is the step-by-step checklist for Release 1.4. It is written for someone
who has **never run a release here before**. Follow it top to bottom, in order.
Do not skip a step because it looks obvious, and do not reorder steps.

The whole engineering team is on call for this release. **If anything does not
match what this document says will happen, stop and ask in the release channel
before doing anything else.** Stopping costs nothing. Guessing in production
can cost a lot.

For background on how the branches and workflows fit together, read
[`release-flow.md`](release-flow.md) once before release day. The previous
runbook, [`release-runbook-v1.4.0.md`](release-runbook-v1.4.0.md), is a
historical record of the last API release. Do not follow it, because the flow has
changed since then.

---

## 0. What is shipping, and why the version numbers differ

| Repo | Production now | Shipping | How the version is set |
|---|---|---|---|
| OcotilloUI | `1.3.0` | **`1.4.0`** | By hand, in a PR that edits `package.json` ([OcotilloUI#425](https://github.com/DataIntegrationGroup/OcotilloUI/pull/425)) |
| OcotilloAPI | `v1.4.0` | **`v1.5.0`** | Automatically, by release-please, from the commit titles |

**"Release 1.4" is the UI's version.** The API is already at `v1.4.0`: that
shipped on 2026-09-23. The API cannot ship as 1.4 again. release-please picks
the next number itself from the Conventional Commit types since the last tag.
There are 15 `feat:` commits since `v1.4.0`, so it will cut **`v1.5.0`**. If the
Release PR in step 4.3 shows any number other than `1.5.0`, stop and ask.

### UI changes (`staging` vs `production`, 212 commits)

- New **public landing page** and **signup request page** (`/signup`, with a
  "send via Gmail" button and a copy-email button)
- The hydrograph corrector is **renamed to HydroSync** (BDMS-1441), and it gains:
  - value-axis-only zoom (BDMS-1447), and zoom moved from ctrl+scroll to
    shift+scroll (BDMS-1442)
  - a user-defined zoom box (BDMS-1408)
  - progress for publish, overwrite, and delete (BDMS-1446)
  - delete selected readings before publishing (BDMS-1405)
  - a drift-correction confirmation (BDMS-1409)
  - the well id and publish status stay pinned in view (BDMS-1403)
  - the automated clean tools are **temporarily hidden** (BDMS-1443). This is
    intentional.
- **Chemistry report**: drinking water standards are now read from the API, and
  there is a long list of report corrections (BDMS-1440). Exceedances render in
  bold red.
- Map fix: `queryRenderedFeaturesSafely`. PostHog upgrade.

### API changes (`staging` vs `production`, 96 commits)

- **Chemistry ingest**: isotope results ingest (`oco water-chemistry
  isotope-upload` / `isotope-sync-sheet`), LIMS sample adoption, stricter
  sample matching, failed-row reports
- **HydroSync publish fix**: transducer block inserts are batched to stop
  publish timeouts (BDMS-1445). The UI's new publish progress pairs with this.
- **Well inventory**: the importer now sets the well's release status
  (fixes wells hidden as `draft`), plus OLWC well depth / MP height corrections
- New CLI commands: `db-info`, `--failed-rows`, `--loadable`
- Lexicon: two new organization terms
- Dependency upgrades (FastAPI, aiohttp, authlib, cryptography, asyncpg, etc.)
- Release tooling: the rc line is gone, the Release PR merges itself, and the
  production deploy now smoke-tests itself and reports pending data migrations

### What this release does *not* have (good news)

- **No new Alembic (schema) revisions.** The deploy's `alembic upgrade head`
  should be a no-op.
- **No new secrets and no new environment variables** in either repo. The UI's
  new `VITE_SIGNUP_RECIPIENT`, `VITE_WEAVER_PUBLIC_APP_URL` and
  `VITE_OCOTILLO_PUBLIC_APP_URL` all fall back to the correct production values
  when unset.
- **No Authentik group changes.**
- **The new UI calls no API endpoint that production lacks.** Every path in the
  UI's `openapi-auth.json` already exists in API `v1.4.0`.

### What this release *does* have that needs care

1. **Two new data migrations** (section 6). They change data, they cannot be
   undone with a downgrade, and they are applied by hand.
2. **This is the first release on the new release-please flow.** The Release PR
   is supposed to merge itself, and the deploy smoke-tests itself. Nobody has
   watched this happen in production yet, so watch it closely.
3. **Merging the UI promotion PR ships to production immediately.** There is no
   approval gate and no version check on the UI side.

---

## 1. Roles

Fill these in before release day.

| Role | Who | What they do |
|---|---|---|
| Release driver | `<you>` | Runs every step in this document and posts each step in the release channel |
| Deployer (approver) | `<senior engineer>` | Approves the production API deploy in GitHub (step 4.5). Must be in the `production` environment's required reviewers. |
| Database owner | `<senior engineer>` | Takes the Cloud SQL backup (2.4) and makes the dry-run call on the data migrations (6.1) |
| Rollback decider | `<lead>` | Makes the call to roll back (section 9). The release driver never rolls back alone. |

Release channel: `<#channel>`. Post a one-line message at the start and end of
every numbered section, e.g. "Starting 4. API promotion" / "4 done, v1.5.0 live".
This gives the on-call team a timeline to follow, and gives you a record.

---

## 2. The day before

### 2.1 Check your access

You need all of these before release day. If any one fails, ask for access now,
not on the day.

- [ ] **GitHub**: you can merge PRs into `staging` and `production` in both
      `DataIntegrationGroup/OcotilloUI` and `DataIntegrationGroup/OcotilloAPI`.
- [ ] **GitHub Actions**: you can run workflows manually (the "Run workflow"
      button) in OcotilloAPI. You need this for the Data Migrations workflow.
- [ ] **gcloud**: you are logged in and can list App Engine versions:

      ```bash
      gcloud auth login
      gcloud app versions list --service=ocotillo-api --project=waterdatainitiative-271000
      gcloud app versions list --service=ocotillo     --project=waterdatainitiative-271000
      ```

      Both services live in the GCP project `waterdatainitiative-271000`.
      If either command returns a permission error, ask the Deployer for
      App Engine viewer access on that project.

- [ ] **Accounts for testing**: you can sign in to staging and production
      Ocotillo, and you know of at least one user in `AMP.Admin` who can test
      a HydroSync publish (step 8.2).

### 2.2 Confirm the release-please merge token exists

The Release PR merges itself using the `FORWARD_MERGE_TOKEN` repo secret. Ask
the Deployer to confirm it exists under OcotilloAPI **Settings → Secrets and
variables → Actions → Repository secrets**, and that it belongs to a machine
account, **not** to a person who is also a Deployer (see
[`release-flow.md`](release-flow.md) step 2.4 for why that matters).

If it does not exist, the release still works, but step 4.3 becomes manual and
the person who merges the Release PR **cannot** approve the deploy. Plan for
two Deployers to be available.

### 2.3 Write down what is serving now (your rollback targets)

Run both of these and paste the output into the release channel. These are the
versions you roll back to if something goes wrong.

```bash
gcloud app versions list --service=ocotillo-api --project=waterdatainitiative-271000 \
  --sort-by=~version.createTime --limit=5
gcloud app versions list --service=ocotillo --project=waterdatainitiative-271000 \
  --sort-by=~version.createTime --limit=5
```

The row with `TRAFFIC_SPLIT` = `1.00` is the one serving. Record it:

- API serving version: `______`
- UI serving version: `______`

Both deploy workflows **delete old versions** automatically. The UI workflow
deletes the oldest version on every deploy. Check that the version you just
recorded will still exist after one more deploy. If it is the oldest one in
the list, tell the Deployer before release day.

### 2.4 Database backup (Database owner)

The data migrations in section 6 have no undo. The backup is the only way back.
Ask the Database owner to run:

```bash
gcloud sql backups create --instance=dataservices \
  --project=waterdatainitiative-271000 \
  --description="pre-release-1.4 (API v1.5.0)"
```

Do this **on release day, right before section 4**, not the day before, so the
backup includes yesterday's data. Record the backup id: `______`.

### 2.5 Check the last release's data migrations

The v1.4.0 release left four data migrations to apply by hand. Confirm they
were applied before you add two more.

1. Open OcotilloAPI → **Actions** → **Data Migrations** → **Run workflow**.
2. Set **Use workflow from** = `production`, **environment** = `production`,
   **action** = `status`. Leave everything else at its default.
3. Click **Run workflow**, open the run, and read the "Status before" step.

Expect these four to show as **applied**:

```
20260901_0001_backfill_lexicon_category_descriptions
20260914_0001_convert_well_inventory_casing_diameter
20260916_0001_seed_epa_regulatory_limits
20260905_0003_group_table_parity_with_staging
```

If any of them show as **pending**, stop and tell the Database owner. Do not
apply them as part of this release without a decision.

`status` applies nothing. It is always safe to run.

### 2.6 Announce the freeze

Post in the release channel: "Merge freeze on `staging` in OcotilloUI and
OcotilloAPI from `<time>` until Release 1.4 is done." Anything merged into
`staging` after you verify it (section 3) would ship without having been
tested.

---

## 3. Release day: verify staging

Staging is the release candidate. What is on `staging` right now is exactly
what will ship.

### 3.1 Merge the UI version bump

1. Open [OcotilloUI#425](https://github.com/DataIntegrationGroup/OcotilloUI/pull/425)
   (`chore(release): bump version to 1.4.0`).
2. The diff should show **only** `package.json` and `package-lock.json`, each
   changing `1.3.0` → `1.4.0`. If you see anything else, stop.
3. Check that all checks are green: Lint, Vitest, Cypress, PR Build Test, PR
   Title. (PR Title passes because the PR has the `skip-bdms-check` label.)
4. Get one approving review, then merge it.
5. In the UI repo **Actions** tab, watch the `CD deploy staging to GAE` run for
   the merge commit until it finishes green.

**Why this goes first:** the app footer shows the version from `package.json`.
If the UI promotes without this, production shows `v1.3.0`. That happened in
the last release, which needed an extra PR to fix it.

### 3.2 Confirm CI is green on both `staging` branches

- OcotilloUI: open <https://github.com/DataIntegrationGroup/OcotilloUI/commits/staging>.
  The top commit should be the merge of #425 with a green check.
- OcotilloAPI: open <https://github.com/DataIntegrationGroup/OcotilloAPI/commits/staging>.
  The top commit should have a green check, and its `CD_staging` run should be green.

If either is red, stop. Do not release over red CI.

### 3.3 Smoke test the staging API

The API repo has a read-only smoke test script. From an OcotilloAPI checkout of
`staging`, with your `.env` set up (see the API README):

```bash
git fetch origin && git checkout origin/staging
uv sync --locked
uv run python -m scripts.smoke_test \
  --base-url https://ocotillo-api-staging.newmexicowaterdata.org
```

It exits non-zero on any failure. Checks it has no credentials for are
**skipped**, not failed. Read the summary line at the end and paste it into the
channel. Any `FAIL` means stop.

### 3.4 Click through the staging UI

Find the staging UI URL:

```bash
gcloud app services browse ocotillo-staging --project=waterdatainitiative-271000 --no-launch-browser
```

Then check each of these and tick them off in the channel:

- [ ] The footer of the side navigation reads **v1.4.0**
- [ ] Landing page loads, and the light/dark toggle works
- [ ] `/signup` loads, and the "send via Gmail" and copy-email buttons work
- [ ] Sign in works and lands on the dashboard
- [ ] A well detail page loads, and its map renders
- [ ] **HydroSync** (the renamed hydrograph corrector) opens. The heading says
      HydroSync. Shift+scroll zooms the chart. The automated clean tools are
      **not** shown (that is intended).
- [ ] A chemistry report for a well with chemistry data generates and shows
      drinking water standards
- [ ] The Settings page loads

Do **not** publish HydroSync data on staging just to test it. Publishing writes
real observations.

---

## 4. Ship the API (`v1.5.0`)

The API ships first. The UI's HydroSync publish progress is built against the
batched-insert fix in this API release (BDMS-1445). The UI works against
`v1.4.0`, but publishing large files is the thing that fix repairs.

Post "Starting 4. API promotion" in the channel.

### 4.1 Take the backup

Ask the Database owner to run the backup in 2.4 now, and wait until they post
the backup id.

### 4.2 Open and merge the promotion PR

1. Go to <https://github.com/DataIntegrationGroup/OcotilloAPI/compare/production...staging>.
2. Click **Create pull request**.
3. Title it exactly:

   ```
   chore: merge staging into production
   ```

   The title must match the pattern exactly. The `pr-title-lint` workflow
   requires a Jira key **unless** the title has this form. Any other title
   without `BDMS-####` fails the check.

4. Body: "Release 1.4 — promotes staging to production. release-please will cut
   v1.5.0. Runbook: `docs/release-runbook-ui-v1.4.0-api-v1.5.0.md`."
5. Check the **Files changed** tab. Expect about 58 files. You should see:
   - **two** new files under `data_migrations/migrations/`
     (`20261001_0001_…` and `20261002_0001_…`)
   - **no** new files under `alembic/versions/`
   - `release-please-config.staging.json` and
     `.release-please-manifest.staging.json` **deleted**

   If you see Alembic revisions, stop. This runbook assumes there are none.
6. Wait for all checks to be green.
7. Get one approving review.
8. Merge with **Create a merge commit**. Do **not** squash: squashing a
   promotion rewrites staging's history into one commit and breaks the next
   back-merge. If the merge button only offers squash or rebase, stop and ask.

### 4.3 Watch release-please open and merge the Release PR

Merging pushes to `production`, which starts the **release-please** workflow.
Open OcotilloAPI → **Actions** → **release-please** and watch the newest run.
This is what should happen, in order:

1. **Run 1** (from your merge): release-please opens a PR titled
   `chore(production): release 1.5.0`, then the "Merge the Release PR" step
   squash-merges it. Open the PR from the **Pull requests** tab (it will show as
   merged) and check:
   - the title says **1.5.0**
   - `CHANGELOG.md` gains a `1.5.0` section
   - `pyproject.toml` and `.release-please-manifest.json` change to `1.5.0`
2. **Run 2** (from the Release PR merge): release-please creates the tag
   `v1.5.0` and a GitHub Release, then starts two jobs:
   `deploy-production` and `forward-merge`.

**If the "Merge the Release PR" step prints the warning
`FORWARD_MERGE_TOKEN is not set; merge the Release PR by hand`:** merge the
Release PR yourself (squash is fine for this one). After that, **you cannot
approve the deploy in 4.5.** A different Deployer must approve it.

**If no Release PR appears within ~5 minutes of the merge:** stop and ask.
Do not create a tag or a release by hand.

### 4.4 Check the tag

Open <https://github.com/DataIntegrationGroup/OcotilloAPI/releases>. `v1.5.0`
should be the latest release. Post the link in the channel.

### 4.5 Approve the deploy (Deployer)

The `deploy-production` job pauses with **"Waiting for review"**. This is
expected: the `production` environment requires a Deployer to approve.

- Ask the Deployer to open the run, click **Review deployments**, tick
  `production`, and click **Approve and deploy**.
- Wait. Do not approve it yourself unless you are a Deployer *and* you did not
  merge the Release PR by hand.

### 4.6 Watch the deploy steps

In the `production-deploy` job, watch these steps in order:

| Step | What it does | If it fails |
|---|---|---|
| Validate release tag matches version pattern | checks the tag looks like `v1.5.0` | stop, ask |
| Run Alembic migrations on production database (`alembic upgrade head`) | schema migrations. Expected to be a **no-op** this release. | Old version keeps serving. Stop and ask. Nothing is broken yet. |
| Report pending data migrations | **warns**, never fails | Expect a yellow warning naming the two new data migrations. That is correct. You apply them in section 6. |
| Deploy to Google Cloud | `gcloud app deploy`. This takes several minutes. | stop, ask |
| Clean up oldest versions | deletes one old non-serving version | not release-blocking; tell the Deployer |
| Smoke test the deployed service | waits up to 180 s for a cold start, then checks `/health`, `/docs`, the OGC collections, that `/ogcapi-internal` refuses anonymous callers, and that `/health` reports version **1.5.0** | go to section 9 and tell the rollback decider |

If the smoke test fails, **the new version is already serving traffic.** Treat
a smoke failure as a production incident, not a flaky test.

### 4.7 Check production yourself

```bash
curl -s https://ocotillo-api.newmexicowaterdata.org/health
```

Expect JSON that reports `1.5.0` and a healthy database. Then:

```bash
gcloud app versions list --service=ocotillo-api --project=waterdatainitiative-271000 \
  --sort-by=~version.createTime --limit=3
```

The newest version should have `TRAFFIC_SPLIT` `1.00`.

Also open <https://ocotillo-api.newmexicowaterdata.org/docs> and check the
version shown at the top is `1.5.0`.

Post "4 done, API v1.5.0 live" in the channel.

---

## 5. API back-merge (`production → staging`)

The `forward-merge` job from 4.3 opens a PR **`production → staging`** titled
`chore: merge … into staging`. It carries the release commit and the `v1.5.0`
tag history back to `staging`, and re-locks `uv.lock` to the new version.

1. Find it in OcotilloAPI → **Pull requests**.
2. Wait for CI to be green. If CI never starts (no checks listed at all), the
   PR was opened without the token. Close and reopen it once to start CI.
3. If it shows a **merge conflict** in `CHANGELOG.md`, `pyproject.toml`,
   `.release-please-manifest.json`, or `uv.lock`, ask for help resolving it.
   The rule is in [`release-flow.md`](release-flow.md) → "Version-file
   ownership". Conflicts in any **other** file mean something unexpected
   happened, so stop.
4. Merge with **Create a merge commit**.

This can happen in parallel with section 6. Do not leave it open overnight.

---

## 6. API data migrations (manual)

Data migrations change rows, not tables. The deploy does **not** run them. You
run them by hand with the **Data Migrations** workflow. Two are new in this
release:

| Id | What it changes | How big |
|---|---|---|
| `20261001_0001_backfill_well_inventory_thing_release_status` | Wells created by the well-inventory CSV importer that are still `draft` get their Location's release status (`public` / `private`). Fixes wells that stayed hidden after the owner agreed to make them public. | Every importer-created well still at `draft` |
| `20261002_0001_correct_olwc_well_depth_and_mp_height` | Fixes six OLWC well depths and the measuring-point heights of a handful of OLWC wells (`OG-0016`, `OG-0042`, `OG-0066`, `OG-0072`, …) | Small, named wells only |

Both mutate versioned rows through the ORM, so the old values land in
`thing_version` / `observation_version`. Neither has an automatic undo.

### 6.1 Decide about the dry run (Database owner, before you run anything)

Both migrations' docstrings say to **review a dry run before applying**. The
Data Migrations workflow has **no dry-run option**. A dry run needs local Cloud
SQL credentials, which the Database owner has and you probably do not:

```bash
# Database owner, from an OcotilloAPI checkout of production, pointed at prod
uv run oco data-migrations run 20261001_0001_backfill_well_inventory_thing_release_status --dry-run
uv run oco data-migrations run 20261002_0001_correct_olwc_well_depth_and_mp_height --dry-run
```

Each dry run writes a change report CSV under `reports/`. The Database owner
reads it and posts "go" or "no go" for each migration in the channel. **Do not
start 6.2 without a "go".**

Two known risks for the reviewer:

- The release-status backfill also overwrites any well that someone set back
  to `draft` **on purpose**. It cannot tell the two apart. Check the report for
  wells that should stay hidden.
- The OLWC migration checks that every value it changes still holds the
  expected old value. If production differs from staging, it **refuses to run
  and lists every problem**. That is a "no go", not something to work around.

### 6.2 Run status first

OcotilloAPI → **Actions** → **Data Migrations** → **Run workflow**:

- Use workflow from: `production`
- environment: `production`
- action: `status`

Confirm the two new ids are listed as **pending** and the four from 2.5 are
**applied**.

### 6.3 Run each migration, one at a time

Dispatch the workflow **twice**, once per migration, and wait for each run to
finish before starting the next:

- Use workflow from: `production`
- environment: `production`
- action: **`run`**
- migration_id: (paste the id exactly)
- include_repeatable: **unchecked**
- force: **unchecked**. Never tick `force` without the Database owner saying
  so. It re-runs a migration that is already applied.

Order:

1. `20261001_0001_backfill_well_inventory_thing_release_status`
2. `20261002_0001_correct_olwc_well_depth_and_mp_height`

Do **not** use `run-all`. Running by id gives one log per migration, and it
cannot pick up anything else that happens to be pending.

**Save the logs.** The change report CSV is written on the GitHub runner and
is thrown away when the run ends. The "Apply migrations" step's log lines
(counts, skipped items, and the report path) are the only record left. For each
run, open the "Apply migrations" step, copy the whole log, and paste it into
the release ticket or channel. For the OLWC migration this matters more:
`measuring_point_history` is not versioned, so that log is the only record of
its old values.

If a run fails, **do not re-run it.** Post the log and stop. The OLWC
migration is safe to finish after a partial run, but only once someone has
read why it failed.

### 6.4 Verify

1. Dispatch `status` again. Both new ids should now show as **applied**.
2. Spot-check in the production UI (after section 8) or via the API:
   - pick a well-inventory well that the dry-run report listed, and confirm it
     is now visible with the expected release status
   - open `OG-0042` and confirm its MP height is **negative**

Post "6 done, data migrations applied" in the channel.

---

## 7. Ship the UI (`v1.4.0`)

Only start this after section 4 is done and the API is healthy.

> **Merging the UI promotion PR deploys to production immediately.** There is no
> approval step and no version check. Be sure before you click merge.

Post "Starting 7. UI promotion" in the channel.

### 7.1 Open and merge the promotion PR

1. Go to <https://github.com/DataIntegrationGroup/OcotilloUI/compare/production...staging>.
2. Click **Create pull request**.
3. Title:

   ```
   Release v1.4.0: promote staging to production
   ```

4. Add the label **`skip-bdms-check`**. Without it, the PR Title check fails
   because there is no BDMS key in the title.
5. Body: "Release 1.4 — promotes staging (v1.4.0) to production. API v1.5.0 is
   already live. Runbook: OcotilloAPI
   `docs/release-runbook-ui-v1.4.0-api-v1.5.0.md`."
6. Check the **Files changed** tab:
   - `package.json` shows `"version": "1.4.0"`. If it still says `1.3.0`, #425
     was not merged. Stop and go back to 3.1.
   - Expect about 122 files changed. The UI's `production` has two extra merge
     commits from past promotions that `staging` does not. They carry no file
     changes, so they do not show up in the diff.
7. Wait for all checks to be green: Lint, Vitest, Cypress, PR Build Test, PR
   Title.
8. Get one approving review.
9. Tell the channel "merging UI promotion now", then merge with **Create a
   merge commit**.

### 7.2 Watch the deploy

OcotilloUI → **Actions** → **CD deploy production to GAE**. Steps, in order:
install & build (`npm run build:ci`), deploy to App Engine with `promote: true`,
clean up the oldest version, then tag the commit `ocotillodev-deploy-<timestamp>`.

If the job pauses with "Waiting for review", ask a Deployer to approve it, as
in 4.5.

If **install & build** fails, nothing has shipped, and production still serves
v1.3.0. Stop and ask. If **deploy** fails, check with `gcloud app versions list`
(section 2.3) which version is serving before doing anything else.

---

## 8. Verify production

### 8.1 UI checks

Open <https://ocotillo.newmexicowaterdata.org> in a **private/incognito
window**, so you do not get a cached old build. Tick each one off in the channel:

- [ ] The landing page loads (this is new, so production users see it for the
      first time)
- [ ] `/signup` loads, and the email address shown is `ocotillo-nmbg@nmt.edu`
- [ ] Sign in works end to end
- [ ] The side navigation footer reads **v1.4.0** and the environment badge
      reads production
- [ ] A well detail page loads with its map
- [ ] HydroSync opens and shows the HydroSync heading
- [ ] A chemistry report generates and shows drinking water standards (these
      come from the API's regulatory limits)
- [ ] The Settings page loads
- [ ] The browser console has no red errors on any page above (open DevTools →
      Console)

Users already signed in keep the old build until the app notices
`/version.json` changed and prompts them to refresh. That is expected.

### 8.2 HydroSync publish (with an `AMP.Admin` user)

This is the end-to-end check of the API batch fix (BDMS-1445) together with the
UI progress (BDMS-1446). It writes production data, so **only do this if the
AMP team has a real file ready to publish today.** Do not publish test data.
Ask them to publish one file and confirm that the progress shows and the publish
completes without a timeout. If no real file is ready, skip this check and
say so in the channel.

### 8.3 Watch for 30 minutes

For 30 minutes after the UI deploy, keep an eye on:

- the release channel and the user support channel for reports
- App Engine → Logs for `ocotillo-api` (5xx errors)
- Sentry for new issues tagged with the new release

Post "Release 1.4 done: UI v1.4.0, API v1.5.0" in the channel.

---

## 9. Rollback

**The rollback decider makes the call, not the release driver.** Your job is
to report clearly what broke, when, and which step you were on.

### Roll back the UI (fast, safe)

Send all traffic back to the version you recorded in 2.3:

```bash
gcloud app services set-traffic ocotillo \
  --splits=<UI_PREVIOUS_VERSION>=1 \
  --project=waterdatainitiative-271000
```

This takes effect in about a minute and changes no data. It does not change
the `production` branch: the next push to `production` redeploys v1.4.0. Fix
forward with a hotfix (section 10) before merging anything else to UI
`production`.

### Roll back the API

```bash
gcloud app services set-traffic ocotillo-api \
  --splits=<API_PREVIOUS_VERSION>=1 \
  --project=waterdatainitiative-271000
```

That gets `v1.4.0` code serving again. This release has no schema migrations,
so v1.4.0 code works against the database unchanged.

**Data migrations do not roll back** with traffic. If a data migration is the
problem, the options are a narrow corrective data migration (each migration's
docstring explains how) or restoring the 2.4 backup. Both are the Database
owner's decision. Never restore a backup on your own.

If you roll back the API, roll back the UI too unless the decider says
otherwise. The new UI works against v1.4.0, but HydroSync publish of large
files will time out again.

---

## 10. If a fix is needed after release

Do **not** fix forward through `staging`. That would drag in whatever merges
next.

- **API:** run the `hotfix-start` workflow with `base_tag = v1.5.0`. It creates
  `hotfix/v1.5.1`. Open a `fix:` PR against it. The rest is automatic up to the
  forward-merge PR into `production`, which you merge. Then run `forward-merge`
  by hand with `source_branch = production` to bring it into `staging`. Details
  are in [`release-flow.md`](release-flow.md) → "Hotfix".
- **UI:** branch `hotfix/v1.4.1` off `origin/production`, bump `package.json`
  to `1.4.1` in the same PR, and target `production`. After it ships, open a PR
  `production → staging` to carry it back.

---

## 11. After the release

- [ ] API back-merge PR `production → staging` merged (section 5)
- [ ] Data migration logs saved to the release ticket (6.3)
- [ ] Post "Merge freeze lifted" in the release channel
- [ ] Release notes circulated to users: the new landing and signup pages, the
      HydroSync rename and what changed in it, chemistry report standards, and
      wells from the field inventory now appearing as public
- [ ] Note anything in this runbook that was wrong or unclear, and open a PR to
      fix `release-flow.md` so the next release driver doesn't hit it. Two known
      gaps to raise: the Data Migrations workflow has no `dry_run` input, and it
      does not upload the change-report CSVs as artifacts.

## Release log

Fill this in as you go. It is the record of what actually happened.

| Step | Time | Who | Result / link |
|---|---|---|---|
| 2.3 API serving version | | | |
| 2.3 UI serving version | | | |
| 2.4 Backup id | | | |
| 3.1 #425 merged | | | |
| 4.2 API promotion PR | | | |
| 4.3 Release PR (1.5.0) | | | |
| 4.5 Deploy approved by | | | |
| 4.6 Smoke test | | | |
| 5 Back-merge PR | | | |
| 6.1 Dry run go/no go | | | |
| 6.3 Migration 1 run | | | |
| 6.3 Migration 2 run | | | |
| 7.1 UI promotion PR | | | |
| 8 Production verified | | | |
