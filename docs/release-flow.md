# Release Flow

How code moves from a feature branch to production, how versions are cut, and
how hotfixes work. The mechanics live in `.github/workflows/`; this doc is the
map.

## Branch roles

| Branch | Role | Deploys to | Versioning |
|---|---|---|---|
| `jir*` | feature / ticket branches | `ocotillo-api-testing` (every push) | none |
| `staging` | integration branch (default) | `ocotillo-api-staging` (every push) | none |
| `production` | release branch | `ocotillo-api` (on release tag) | `vX.Y.Z` stable releases via release-please |
| `hotfix/vX.Y.Z` | emergency patch off a release tag | `ocotillo-api` (on release tag) | `vX.Y.Z` patch release via release-please |

## The flow

```
feature (jir*) ──PR──▶ staging ──promotion PR──▶ production ──auto Release PR──▶ tag vX.Y.Z ──▶ prod deploy
   │                     │                            ▲                                 │
   ▼                     ▼                            │ auto forward-merge PR           ▼ auto back-merge PR
testing svc        staging svc deploy           hotfix/vX.Y.(Z+1)                 production → staging
                   (unversioned)                (off tag, via
                                                hotfix-start.yml)
```

**One version line.** `staging` is not versioned: it deploys every push and is
the thing you test against. Only `production` and `hotfix/v*` cut tags.

Staging used to carry an rc line of its own — `vX.Y.Z-rc.N` prereleases with a
second release-please config, manifest and changelog. It was removed: cutting
an rc was a third PR to merge per release, nothing was tested against the rc
tag (v1.4.0-rc was cut and then 97 commits landed before the promotion), and
the back-merge PR had to sync the rc manifest on every release.

### 1. Feature → staging

1. Branch `jir*` off `staging`; every push deploys the testing service
   (`CD_testing.yml`).
2. Merge the PR into `staging` (Conventional Commit title — `feat:`, `fix:`,
   etc.; enforced by `pr-title-lint.yml`).
3. Every push to `staging` deploys the staging service (`CD_staging.yml`) —
   continuous, unversioned, date-stamped tag. The deploy smoke-tests itself
   (`scripts/smoke_test.py`) and warns about unapplied data migrations.

### 2. Staging → production (stable release)

1. Open a **promotion PR** `staging → production` (manual; this is the
   "we want to ship what's on staging" decision).
2. Merging it makes release-please open a **Release PR**
   (`chore(production): release X.Y.Z`) and **merge it automatically**, using
   `FORWARD_MERGE_TOKEN`. The promotion PR was the decision; the Release PR
   only carries the version bump and changelog.
3. That tags `vX.Y.Z`, publishes the GitHub release, and the same workflow run
   invokes `CD_production.yml` via `workflow_call` (releases created with
   `GITHUB_TOKEN` don't emit events that trigger other workflows, hence the
   inline call).
4. The `production` environment requires a Deployer's approval before the
   deploy runs, and sets `prevent_self_review`. Merging the Release PR from
   the workflow is what keeps that workable: the triggering actor is
   `FORWARD_MERGE_TOKEN`'s owner rather than whoever promoted, so every
   Deployer can approve. **If that token belongs to a human who is also a
   Deployer, they become the one person who cannot approve** — use a machine
   account.
5. The deploy runs `alembic upgrade head`, smoke-tests the result, and warns
   about unapplied data migrations. Data migrations themselves are still a
   deliberate manual dispatch (`data_migrations.yml`).
6. `forward-merge.yml` then opens an automatic **back-merge PR
   `production → staging`**, carrying the release commit and tag history.
   Merge it promptly.

### 3. Hotfix

1. Run the `hotfix-start` workflow (optionally pinning `base_tag`). It creates
   `hotfix/vX.Y.(Z+1)` off the release tag.
2. Open a fix PR targeting the hotfix branch (`fix:` title).
3. release-please opens a Release PR on the hotfix branch and merges it; that
   tags `vX.Y.(Z+1)` and deploys production.
4. `forward-merge.yml` automatically opens **`hotfix/vX.Y.(Z+1)` →
   `production`**. Merge it. No new release is cut (the release commit is
   already in the branch).
5. Propagate to staging: run the `forward-merge` workflow manually with
   `source_branch=production` and the hotfix tag (the hotfix merge doesn't cut
   a release on production, so the automatic trigger doesn't fire).

## Version-file ownership

| File | Written by | Lives meaningfully on |
|---|---|---|
| `.release-please-manifest.json` | release-please on `production` / `hotfix/v*` | production |
| `pyproject.toml` version | release-please (python release-type) | production |
| `CHANGELOG.md` | releases | production |
| `uv.lock` | re-locked by the back-merge PR after a version bump | both |

**Conflict rule:** if any of these conflict during a merge, accept either side
and move on — release-please rewrites them on the next Release PR. The
manifest is the only state that matters.

## Caveats

- **CI on automated PRs:** PRs created with the default `GITHUB_TOKEN` do not
  trigger `pull_request` workflows. Set the `FORWARD_MERGE_TOKEN` repo secret
  (fine-grained PAT or GitHub App token, `contents: write` +
  `pull-requests: write`) so back-merge/forward-merge PRs get CI. Without it,
  close and reopen the PR to kick CI.
- **Workflow changes go live per branch:** release-please and the deploy
  workflows resolve at the pushed branch's commit. A workflow fix merged to
  `staging` does nothing for production releases until it reaches
  `production`.
- **Tag visibility:** release-please bounds its commit scan at the last tag it
  can see, so merge back-merge PRs promptly — a `staging` that has drifted far
  from the last release makes the next Release PR's changelog harder to read.
