# Group consolidation and study-area import: runbook

Operational steps to reconcile the `group` table against the Aquifer Mapping Study
Areas webmap, and to verify it worked.

- Migration: `data_migrations/migrations/20260810_0001_consolidate_geographic_area_groups.py`
- Importer: `cli/project_area_import.py` (`oco import-project-area-boundaries`)
- Jira: [BDMS-1143](https://nmbgmr.atlassian.net/browse/BDMS-1143)
- Affected views: `ogc_project_areas`, `ogc_actively_monitored_wells` (both plain views)

**Order matters: migration first, importer second.** The importer claims features by
OBJECTID and writes to whichever group owns the mapped name, and those names are the
post-consolidation ones. Running it second lands each boundary on the surviving row.
Running it first is not destructive, but the project row gets its boundary while the
Geographic Area still holds a stale copy, and the migration then reports that pair as a
conflict and skips it.

**This migration deletes rows and there is no down path.** Data migrations have no
`downgrade`, and both foreign keys into `group` are `ON DELETE CASCADE`. Take a backup
before applying to anything you cannot rebuild.

**Ids differ between environments.** On staging `water Level Network` is id 126; on
production 126 is `Copper Replacement Deposits`. Every operation in the migration is keyed
on `(name, group_type)` for that reason, and every verification query below selects on
name. Do not translate these steps into id-based SQL.

---

## 0. Prerequisites

- [ ] `uv sync --locked`, and the branch is rebased onto `staging` (the migration's
      alembic gate walks the deployed head back through this checkout's revision files;
      a head the checkout has never seen raises `ResolutionError`).
- [ ] Snapshot of the target database taken. See below.
- [ ] The merge pairs have been reviewed and signed off. The dry run is that review.

### Take a snapshot

`gcloud sql backups create` is the fuller option, but it needs an authenticated
`gcloud` session. Without one, a two-table dump is still a complete restore source for
everything in this runbook: only `group_thing_association.group_id` and
`group.parent_group_id` reference `group.id`, and neither the migration nor the importer
writes anywhere else. Both tables are small, and neither carries PII.

```bash
set -a; source .env; set +a
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -p 5432 \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -t 'public."group"' -t public.group_thing_association \
  --no-owner --no-acl -f "groups-$(date +%Y%m%dT%H%M%S).sql"
```

A dump you have not checked is not a backup. Confirm it holds both schema and data, and
that the row counts match the live table:

```bash
grep -c 'CREATE TABLE public' groups-*.sql          # expect 2
awk '/^COPY public."group" /,/^\\\.$/' groups-*.sql | sed '1d;$d' | wc -l
```

The second number must equal `select count(*) from "group"` from section 1.

### Confirm the database target first

On a developer machine the Cloud SQL proxy and the local Docker container can **both**
hold port 5432: the proxy binds `127.0.0.1:5432` and Docker binds the IPv6 wildcard
`*:5432`, so neither bind fails and `localhost` silently resolves to one of them. A
successful connection is not evidence you reached the intended database.

```bash
POSTGRES_HOST=127.0.0.1 uv run python -c "from db.engine import session_ctx; from sqlalchemy import text; s=session_ctx().__enter__(); print(s.execute(text('select current_database(), current_user')).one())"
```

Every command below assumes an explicit `POSTGRES_HOST`.

---

## 1. Capture the before state

```sql
select count(*) from "group";
select count(*) from "group" where group_type = 'Geographic Area';
select count(*) from ogc_project_areas;
select count(*) from ogc_actively_monitored_wells;
select count(*) from "group" where project_area is not null and release_status = 'draft';
```

On staging as of 2026-09-03 these were 97, 46, 56, 222 and 0.

The last one matters: it is the invariant `20260714_0001_publish_project_areas`
established, that every group holding a boundary is public. It must still read 0 at the
end of section 7.

---

## 2. Dry run and review

```bash
POSTGRES_HOST=127.0.0.1 uv run oco data-migrations run 20260810_0001_consolidate_geographic_area_groups --dry-run
```

Writes nothing. `dry_run_migration` rolls back in a `finally` and never touches
`data_migration_history`, and the migration's own preview applies the first pass inside a
SAVEPOINT that is always rolled back. That SAVEPOINT is what makes the preview honest:
the `Tiffany Fire` merge only exists once the rename has happened, so a preview that
skipped it would under-report.

The report comes in two blocks.

Everything below was measured on staging on 2026-09-03. Compare the report against it
line by line; a difference means the data has moved since, not that the table is wrong to
care.

**Duplicate project operations** (the hand-reviewed table, `DUPLICATE_PLAN_OPERATIONS`).
Expect `4 operation(s), 0 refused, 0 already applied`: three merges plus one rename-only.

| keep | delete | membership | links | rename to |
|---|---|---|---|---|
| 20 `Tiffany Fire Restoration` | 47 `Tiffany Fire Recovery` | identical | 0 moved, 277 dropped | `Tiffany Fire` |
| 5 `Sacramento Mtns` | 8 `SM Watershed` | superset | 0 moved, 492 dropped | `Sacramento Mountains` |
| 39 `Water Level Network` | 126 `water Level Network` | disjoint | 1 moved, 0 dropped | |
| 56 `San Acacia` | | none | | `San Acacia Reach` |

Ids are advisory. They are the staging values and are reported only when they disagree
with what the review recorded, because ids differ between environments.

**Geographic Area merges: 15 merges, 9 protected, 0 conflicts, 0 ambiguous, 22
unmatched**, with 14 reporting `publishes the target`. That is the 14/9/0/0/23 this
migration produced before the first pass existed, plus `Arroyo Hondo Area` entering the
merge list, minus `Sacramento Mountains Watershed Study` leaving it, plus `Tiffany Fire`
becoming resolvable once the first pass renames its target.

Three lines are worth reading closely, because they are the ones the first pass makes
possible:

- `merge group 119 ('Tiffany Fire') into 20 ('Tiffany Fire', type=Monitoring Plan)
  [normalized name]` confirms the rename happened before the match was attempted.
- `merge group 92 ('Southern Sacramento Mountains') into 5 ('Sacramento Mountains')
  [manual]` confirms the retargeted `MANUAL_MATCHES` entry resolves post-rename.
- `Animas River` is the only merge **not** publishing its target, because both rows
  already hold identical geometry and group 27 is already public. That is the one
  `ogc_project_areas` row consolidation costs.

Anything in `refused`, `conflicts` or `ambiguous` is a stop, not a warning. Those are
cases the migration will not guess at. A `refused` line quotes the actual membership it
found, so it tells you whether the pair has diverged since the review or the row simply
is not there.

---

## 3. Apply

```bash
POSTGRES_HOST=127.0.0.1 uv run oco data-migrations run 20260810_0001_consolidate_geographic_area_groups
```

### Do not use `run-all`

`oco data-migrations run-all` will produce a broken state if the publication behaviour
is ever taken back out of this migration. Registry order is filename-alphabetical, so
`20260714_0001_publish_project_areas` sorts *before* `20260810_0001_consolidate_...`,
and `run_all` skips non-repeatable migrations that are already applied. It would run the
consolidation and never republish. Run this migration by id.

---

## 4. Verify the consolidation

Re-run the queries from step 1. The "after" column is derived from the measured dry run,
not observed post-apply, so treat a mismatch as worth investigating rather than as proof
the table is stale.

| Check | Before | After |
|---|---|---|
| `group` rows | 97 | **79** |
| Geographic Area rows | 46 | **31** |
| `ogc_project_areas` rows | 56 | **55** |
| `ogc_actively_monitored_wells` rows | 222 | **471** |
| groups with a boundary and `release_status = 'draft'` | 0 | **0** |

97 − 3 first-pass deletions − 15 merges = 79. The single lost view row is the
`Animas River` duplicate, whose two rows held identical geometry; that is the intended
outcome, not a regression. Any other number means stop and investigate.

Then the row-level checks:

```sql
select g.name, g.group_type, g.release_status, g.project_area is not null as has_area,
       (select count(*) from group_thing_association a where a.group_id = g.id) as things
from "group" g
where g.name in ('Tiffany Fire', 'Water Level Network', 'Sacramento Mountains',
                 'San Acacia Reach', 'Arroyo Hondo',
                 'Sacramento Mountains Watershed Study')
order by g.name;
```

Expect exactly one row each:

- `Tiffany Fire`, Monitoring Plan, public, has a boundary, **277** things
- `Water Level Network`, Monitoring Plan, draft, no boundary, **487** things
- `Sacramento Mountains`, Monitoring Plan, public, has a boundary, **493** things
- `San Acacia Reach`, Monitoring Plan, draft, no boundary yet, 47 things
- `Arroyo Hondo`, public, has a boundary, 54 things
- `Sacramento Mountains Watershed Study`, still a public Geographic Area, untouched

And that the old names are gone:

```sql
select name from "group"
where name in ('Tiffany Fire Recovery', 'Tiffany Fire Restoration', 'SM Watershed',
               'water Level Network', 'Sacramento Mtns', 'San Acacia');
```

### About the wells layer jump

222 to 471 is expected. `ogc_actively_monitored_wells` inner-joins group memberships
filtered to `release_status = 'public'`, so a well only appears if it belongs to at least
one public group; publishing 14 merge targets brings their wells in. This is not new
exposure. The wells come from `ogc_water_well_summary`, which is transitively restricted
to public things (its `wl_agg` join requires water-level observations, and that CTE
filters `thing.release_status = 'public'`), so what changes is that already-published
wells now show their project membership. Record the before and after counts anyway.

No view needs refreshing. Every relation that reads `group` or
`group_thing_association` is a plain view: `ogc_project_areas`,
`ogc_internal_project_areas`, `ogc_actively_monitored_wells`,
`ogc_internal_actively_monitored_wells`, `ogc_internal_water_well_field_operations`.
None is materialized, and there is no `group_version` table.

---

## 5. Import the study areas

```bash
POSTGRES_HOST=127.0.0.1 uv run oco import-project-area-boundaries --dry-run
```

Pulls layer **18** of the `maps.nmt.edu/.../Water_Resources/MapServer` service. Layer 17,
which the importer used to target, was retired and now returns
`{"error":{"code":404,"message":"Layer not found"}}`.

Expected on staging: 44 fetched, **10 created, 2 updated, 32 unchanged, 0 skipped**.

The 10 created are the new study areas, all as public Geographic Areas:

`Albuquerque Water Table`, `Estancia Basin (AEM)`, `Gila-Animas 1 (AEM)`,
`Gila-Animas 2 (AEM)`, `Lower Rio Grande (AEM)`, `Middle Rio Grande (AEM)`,
`Middle Rio Grande Aquifer Storage and Recovery`, `Mimbres Basin (AEM)`,
`Rio Arriba County`, `Taos`.

The 2 updated are `Carrizozo` and `San Acacia Reach`, both Monitoring Plans that had no
boundary; each gains one and is published so the draft-boundary invariant holds. The 32
unchanged are areas whose upstream geometry has not moved since they were last imported.

**Any skip is a stop.** The two reasons that matter:

- *"mapped name is not present, and this entry is not allowed to create it"* usually means
  section 3 has not run. Only the 10 genuinely new areas carry `create_if_missing`.
- *"name is owned by N groups"* means two rows share a name, and the importer refuses to
  pick one rather than overwriting both.

Then apply:

```bash
POSTGRES_HOST=127.0.0.1 uv run oco import-project-area-boundaries
```

Final state: `ogc_project_areas` 67, `ogc_actively_monitored_wells` 476, Geographic Areas
41, `group` rows 89, and groups with a boundary and `release_status = 'draft'` back to 0.

---

## 6. Why re-importing no longer undoes the consolidation

The importer used to match on the feature's `location` attribute filtered to
`group_type = 'Geographic Area'`, and create a row when it missed. That is what recreated
every Geographic Area this migration deletes, and it could not have imported the current
layer at all: `location` is not unique there (OBJECTIDs 9 and 42 are both
`Estancia Basin`, 6 and 39 both `Mimbres Basin`, 40 and 41 both `Gila-Animas`), so it
would have overwritten the legacy `Estancia Basin` and `Mimbres Basin` boundaries with
AEM polygons and violated `uq_group_name_type` on the `Gila-Animas` pair.

It now claims features by OBJECTID through `PROJECT_AREA_MAPPINGS`, which records the
group that owns each boundary after consolidation, drops the `group_type` filter so a
Monitoring Plan can own one, and creates only where an entry says it may. A feature whose
OBJECTID is not in the map is reported and skipped.

Two consequences worth knowing:

- Adding a study area to the layer will not import it until someone adds a map entry.
  That is deliberate: silence is safer than a guessed name.
- `oco data-migrations run 20260714_0001_publish_project_areas --force` remains a blunt
  instrument. It is `UPDATE "group" SET release_status = 'public' WHERE project_area IS
  NOT NULL`, with no status predicate and no dry run (`dry_run=None`, and `--dry-run`
  short-circuits before `--force`), and it writes a second `data_migration_history` row.
  Check what it would touch first:

  ```sql
  select id, name, group_type, release_status
  from "group"
  where project_area is not null and release_status is distinct from 'public';
  ```
