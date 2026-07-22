# Release Flow

How code moves from a feature branch to production, how versions are cut, and
how hotfixes work. The mechanics live in `.github/workflows/`; this doc is the
map.

## Branch roles

| Branch | Role | Deploys to | Versioning |
|---|---|---|---|
| `jir*` | feature / ticket branches | `ocotillo-api-testing` (every push) | none |
| `staging` | integration branch (default) | `ocotillo-api-staging` (every push) | `vX.Y.Z-rc.N` prereleases via release-please |
| `production` | release branch | `ocotillo-api` (on release tag) | `vX.Y.Z` stable releases via release-please |
| `hotfix/vX.Y.Z` | emergency patch off a release tag | `ocotillo-api` (on release tag) | `vX.Y.Z` patch release via release-please |

## The flow

```
feature (jir*) ──PR──▶ staging ──promotion PR──▶ production ──release PR──▶ tag vX.Y.Z ──▶ prod deploy
   │                     │                            ▲                            │
   ▼                     ▼                            │ auto forward-merge PR      ▼ auto back-merge PR
testing svc        staging svc deploy           hotfix/vX.Y.(Z+1)            production → staging
                   + RC release PR              (off tag, via                (syncs staging manifest)
                   → tag vX.Y.Z-rc.N            hotfix-start.yml)
```

### 1. Feature → staging (RC line)

1. Branch `jir*` off `staging`; every push deploys the testing service
   (`CD_testing.yml`).
2. Merge the PR into `staging` (Conventional Commit title — `feat:`, `fix:`,
   etc.; enforced by `pr-title-lint.yml`).
3. Every push to `staging` deploys the staging service (`CD_staging.yml`) —
   continuous, unversioned, date-stamped tag.
4. release-please (staging config) maintains an **RC Release PR**
   (`chore(staging): release X.Y.Z-rc.N`). Merging it tags `vX.Y.Z-rc.N` and
   publishes a GitHub **prerelease**. This is a versioned checkpoint of what's
   on staging — it never deploys production.
5. Successive merges after an RC bump only the `rc.N` counter
   (`versioning: prerelease`), so the target version is stable until promoted.

Cut an RC (merge the RC Release PR) when staging is in a state you intend to
promote — the RC tag is the thing you tested.

### 2. Staging → production (stable release)

1. Open a **promotion PR** `staging → production` (manual; this is the
   "we want to ship what's on staging" decision).
2. Merging it makes release-please (production config) open a **Release PR**
   (`chore(production): release X.Y.Z`).
3. Merging the Release PR tags `vX.Y.Z`, publishes the GitHub release, and the
   same workflow run invokes `CD_production.yml` via `workflow_call`
   (releases created with `GITHUB_TOKEN` don't emit events that trigger other
   workflows, hence the inline call).
4. `forward-merge.yml` then opens an automatic **back-merge PR
   `production → staging`**, which also syncs
   `.release-please-manifest.staging.json` to the released version so the next
   RC computes from the new stable baseline. Merge it promptly.

### 3. Hotfix

1. Run the `hotfix-start` workflow (optionally pinning `base_tag`). It creates
   `hotfix/vX.Y.(Z+1)` off the release tag.
2. Open a fix PR targeting the hotfix branch (`fix:` title).
3. release-please (production config, hotfix branch) opens a Release PR;
   merging it tags `vX.Y.(Z+1)` and deploys production.
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
| `.release-please-manifest.staging.json` | release-please on `staging`; synced by back-merge PRs | staging |
| `pyproject.toml` version | release-please stable releases only (python release-type) | production |
| `CHANGELOG.md` | stable releases | production |
| `CHANGELOG-rc.md` | RC releases | staging |
| `version.txt` | RC releases (simple release-type bookkeeping) | staging |

RC releases deliberately do **not** touch `pyproject.toml`: `1.2.0-rc.1` is
not a valid PEP 440 version and would break `uv export` during staging
deploys, and skipping it avoids promotion-merge conflicts.

**Conflict rule:** if any of these files conflict during a merge, accept
either side and move on — release-please rewrites them on the next Release PR.
The manifests are the only state that matters, and the back-merge PR syncs the
staging one explicitly.

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
- **Tag visibility:** the staging release-please needs the last stable tag's
  commit in `staging` history to bound its commit scan — another reason to
  merge back-merge PRs promptly after each release.
