# Deployment Runbook

The short version of a production release. For how the branches and workflows
fit together, see [`release-flow.md`](release-flow.md). The slide deck
[`deployment-runbook.pptx`](deployment-runbook.pptx) covers the same material.

⚠ marks a step that has failed before or can fail without anyone noticing.

## Environments

| Push to | Workflow | Service | Gate |
|---|---|---|---|
| `jir*` | `CD_testing.yml` | `ocotillo-api-testing` | none |
| `staging` | `CD_staging.yml` | `ocotillo-api-staging` | none |
| release tag `vX.Y.Z` | `release-please.yml` → `CD_production.yml` | `ocotillo-api` | Deployer approval |

## Release

### Before

- [ ] CI is green on `staging`, and the staging deploy's smoke test passed on
      the commit you are shipping.
- [ ] ⚠ **Freeze `staging`.** Anything merged after you tested ships untested.
- [ ] ⚠ Out-of-code prerequisites are in place: Authentik groups, Secret
      Manager secrets, Cloud SQL flags. The deploy assumes they exist.
- [ ] If the release carries data migrations, take a Cloud SQL backup and note
      the id. Data migrations cannot be rolled back.
      `gcloud sql backups create --instance=<PROD_INSTANCE> --description="pre-vX.Y.Z"`
- [ ] Note the serving version (your rollback target):
      `gcloud app versions list --service=ocotillo-api --project=<PROJECT>`

### Ship

1. Open a promotion PR `staging → production` and merge it. This is the
   decision to ship.
2. release-please opens the Release PR (`chore(production): release X.Y.Z`)
   and merges it itself.
   ⚠ If `FORWARD_MERGE_TOKEN` is unset, it only logs a warning and the PR sits
   there. Merge it by hand, and then someone else has to approve the deploy.
3. The tag `vX.Y.Z` is cut and `CD_production` starts.
   ⚠ Check that the `deploy-production` job **ran** and was not **skipped**.
   An empty tag skips it and the run still looks green.
4. A Deployer approves the `production` environment. Whoever triggered the run
   cannot approve it (`prevent_self_review`).
5. Watch the run: migrations → data-migration report → deploy → cleanup →
   smoke test.

### After

6. Read the "Report pending data migrations" step. If anything is pending, run
   `data_migrations.yml` with `environment=production`, `action=status` first,
   then `run-all` or `run`.
7. Merge the automatic back-merge PR `production → staging` promptly.
8. If OcotilloUI depends on the new API, promote the UI now. Ship the API first,
   the UI second.

## What `CD_production` does, in order

| Step | If it fails |
|---|---|
| Fetch Secret Manager secrets | Stops. Nothing changed. |
| `alembic upgrade head` on prod DB | Stops before the deploy. Check `alembic current`. |
| Report pending data migrations | Warning only. Never fails the run. |
| `gcloud app deploy` | ⚠ **New schema, old code.** Migrations already ran. |
| Delete oldest non-serving version | ⚠ Can delete your rollback target. |
| Smoke test (`scripts/smoke_test.py`) | ⚠ **The new version is already live.** Treat as an incident. |

## Failure points

| Where | What goes wrong | What to do |
|---|---|---|
| Promotion | `staging` moved after you tested it | Freeze `staging` until the promotion merges |
| Release PR | Not auto-merged (token missing) | Merge by hand; a second Deployer approves |
| Tag | Empty tag silently skips the deploy | Confirm `deploy-production` ran |
| Approval | Run sits waiting; the person who triggered it cannot approve | Line up a second Deployer before you start |
| Secrets | Missing secret or missing accessor role | Add the secret version, re-run |
| Migrations | Schema now ahead of serving code | Keep migrations additive so old code tolerates them |
| App start | OOM (8 workers need F4_1G), or auth config aborts startup | See [`app-engine-oom-instance-churn.md`](app-engine-oom-instance-churn.md) |
| Smoke test | Fails after traffic has moved | Roll back (below) |
| Version cleanup | Previous version deleted, so no warm rollback | Check it exists before you deploy |
| Data migrations | Never run, so features ship with empty data | Read the report step every release |
| Back-merge | Left open, so `staging` drifts and the next changelog is a mess | Merge it the same day |
| Workflow edits | A fix merged to `staging` does nothing for production | It goes live when it reaches `production` |

## Rollback

**Code.** Move traffic back to the previous version:

```bash
gcloud app versions list --service=ocotillo-api --project=<PROJECT>
gcloud app services set-traffic ocotillo-api --splits=<PREVIOUS_VERSION>=1 --project=<PROJECT>
```

If the cleanup step already deleted that version, ship a revert through the
hotfix flow below.

**Schema.** Stays applied after a traffic switch. Run `alembic downgrade` only
if the rollback has to persist and the old code cannot read the new schema.

**Data migrations.** Have no downgrade. The only path back is restoring the
backup.

## Hotfix

1. Run `hotfix-start` (optional `base_tag`). It creates `hotfix/vX.Y.(Z+1)` off
   the release tag.
2. Open a `fix:` PR into the hotfix branch and merge it.
3. release-please tags `vX.Y.(Z+1)` and deploys production, with the same
   approval gate.
4. Merge the automatic `hotfix/... → production` PR.
5. ⚠ Run `forward-merge` by hand (`source_branch=production`, the hotfix tag)
   to carry the fix to `staging`. Nothing does this automatically.
