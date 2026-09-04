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

Running it first is not destructive, but it can leave work behind. The project record gets
its boundary while the Geographic Area still holds a copy, and what the merge pass does
next depends on whether those two polygons match. Identical, and it merges anyway, since
that is also what a half-applied run looks like. Different, because upstream has drifted
since the last import, and it reports a conflict and skips the pair, leaving two rows
holding two boundaries for someone to reconcile by hand.

**This migration deletes rows and there is no down path.** Data migrations have no
`downgrade`, and both foreign keys into `group` are `ON DELETE CASCADE`. Take a backup
before applying to anything you cannot rebuild.

**The webmap is the source of truth for boundaries.** A group that came from the webmap and
is no longer in the layer is deleted. A legacy group in the same position keeps its row but
loses its boundary and drops to draft, because a legacy project is not the webmap's to
delete. Both halves are driven by hand-reviewed name lists rather than by a general rule, so
the migration can only touch rows somebody looked at.

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

The instance already has daily automated backups and point-in-time recovery, so the
question is not whether a safety net exists. It is how quickly you can undo *this* change
without disturbing anything else.

**Record the UTC timestamp immediately before you apply.** PITR can rewind to any moment,
but only if somebody knows which moment to ask for, and "sometime Thursday afternoon" is
not a recovery plan.

```bash
date -u +%Y-%m-%dT%H:%M:%SZ | tee applied-at.txt
```

Then take the targeted dump below anyway. The three options do different jobs:

| | covers | cost to restore |
|---|---|---|
| two-table dump | `group`, `group_thing_association` | truncate and reload, seconds |
| PITR | everything, to the second | clones to a **new** instance, then extract |
| daily backup | everything, up to 24h stale | full instance restore |

PITR and the daily backup are instance-wide, and Cloud SQL restores them to a new instance
rather than in place. Undoing eight bad boundary strips that way means cloning, extracting
two tables, and copying them back, or rolling back everything anyone else did to
`ocotillo-staging` in the meantime. The dump makes the likely failure, "the removals did
the wrong thing to a handful of rows", a two-minute fix.

A two-table dump is a complete restore source for everything in this runbook: only
`group_thing_association.group_id` and `group.parent_group_id` reference `group.id`, and
neither the migration nor the importer writes anywhere else. Both tables are small, and
neither carries PII. Reload order matters, since `group_thing_association` has a foreign
key to `thing`.

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

On staging as of 2026-09-04 these were 97, 46, 56, 222 and 0.

The last one matters: it is the invariant `20260714_0001_publish_project_areas`
established, that every group holding a boundary is public. It must still read 0 after the
import in section 5, and it is the one number the removal pass could plausibly break, since
stripping a boundary and setting draft has to happen together or not at all.

---

## 2. Dry run and review

```bash
POSTGRES_HOST=127.0.0.1 uv run oco data-migrations run 20260810_0001_consolidate_geographic_area_groups --dry-run
```

Writes nothing that survives. `dry_run_migration` rolls back in a `finally` and never
touches `data_migration_history`, and the migration's own preview applies all three passes
inside a SAVEPOINT that is always rolled back.

That SAVEPOINT is what makes the preview honest, because each pass reads what the one
before it produced. The `Tiffany Fire` merge only exists once the rename has happened, and
the removals only know what to delete once the merges have moved their boundaries. A preview
that skipped the writes would under-report the first and over-report the second.

It does mean a dry run takes brief row locks on `group` and `group_thing_association`. A
second or two, and nothing persists even if the connection drops, since Postgres aborts an
uncommitted transaction server-side.

The report comes in three blocks. Everything below was measured on staging on 2026-09-04.
Compare the report against it line by line; a difference means the data has moved since,
not that the table is wrong to care.

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

**Geographic Area merges: 11 merges, 9 protected, 0 conflicts, 0 ambiguous, 26
unmatched**, with 10 reporting `publishes the target`.

Two lines are worth reading closely. `merge group 119 ('Tiffany Fire') into 20
('Tiffany Fire', type=Monitoring Plan) [normalized name]` confirms the rename happened
before the match was attempted, which is the whole reason the first pass exists.
`Animas River` is the only merge **not** publishing its target, because both rows already
hold identical geometry and group 27 is already public.

Every one of the 11 sources is still in the webmap. That is not a coincidence: four pairs
were dropped from `MANUAL_MATCHES` when the layer lost their areas, so `Pueblo of Picuris`,
`Arroyo Seco Area`, `Arroyo Hondo Area` and `Southern Sacramento Mountains` now fall through
to the removal pass instead of donating boundaries. That is why `Sacramento Mountains`,
`Picuris Pueblo`, `Arroyo Seco` and `Arroyo Hondo` all end up draft with no boundary.

**Webmap removals: 15 deletions, 8 boundary strips, 0 refused.**

The 15 deletions are webmap rows the layer no longer has. Only `Ambrosia Lake` carries any
membership, reported as `3 thing link(s) lost`; the wells themselves survive, because
`thing` has no foreign key to `group` and the cascade can only reach the association rows.

| deleted | | |
|---|---|---|
| `Ambrosia Lake` | `Arroyo Chico-Torreon Wash` | `Arroyo Hondo Area` |
| `Arroyo Seco Area` | `central and western Dona Ana County` | `De Baca County` |
| `Grant County` | `Guadalupe County` | `Hydrogeology of Aztec Quadrangle` |
| `Lea County` | `north-eastern Socorro County` | `Pueblo of Picuris` |
| `Sandia and northern Manzano Mountains` | `Southern Sacramento Mountains` | `eastern Valencia County` |

The 8 strips are legacy rows that keep their identity and lose a boundary nothing backs.
Six of them are also in `PROTECTED_NAMES`, which looks alarming in the report and is
correct. Protection stops a row being **deleted**, because its name is a legacy project
name and deleting it would cascade away that project's wells. It has never had anything to
say about boundaries.

| protected and boundary removed | boundary removed, not protected | protected, keeps boundary |
|---|---|---|
| `Albuquerque Basin` | `El Morro` | `Eastern Tularosa Basin` |
| `Colfax County` | `Placitas` | `Mimbres Basin` |
| `Eddy County` | | `Rio Rancho` |
| `Quay County` | | |
| `San Miguel County` | | |
| `Torrance County` | | |

The third column keeps its boundaries because those three areas are still in the webmap,
not because they are protected. Everything in the first two columns loses its polygon for
the same single reason: the project no longer exists in the current webmap, and the webmap
is the source of truth for boundaries.

Confirmed with the layer owner on 2026-09-04: those six should leave the public layer.

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

Re-run the queries from step 1. The "after migration" and "after import" columns were
measured on staging on 2026-09-04 by applying all three passes inside a savepoint and
counting before rolling back, so they are observations rather than arithmetic. A mismatch
is worth investigating rather than proof the table is stale.

| | before | after migration | after import |
|---|---|---|---|
| `group` rows | 97 | **68** | **78** |
| typed Geographic Area | 46 | **20** | **30** |
| `release_status = 'public'` | 56 | **32** | **44** |
| `release_status = 'draft'` | 41 | **36** | **34** |
| `ogc_project_areas` rows | 56 | **32** | **44** |
| holding a boundary while draft | 0 | **0** | **0** |
| `ogc_actively_monitored_wells` rows | 222 | **453** | **458** |

29 rows go: 3 duplicate Monitoring Plans, 11 Geographic Areas merged away, 15 removed. Ten
arrive from the import. Public and `ogc_project_areas` track each other exactly, both
before and after, because a group is public precisely when it holds a boundary. If those
two ever diverge, that is the thing to chase, not the totals.

Then the row-level checks:

```sql
select g.name, g.group_type, g.release_status, g.project_area is not null as has_area,
       (select count(*) from group_thing_association a where a.group_id = g.id) as things
from "group" g
where g.name in ('Tiffany Fire', 'Water Level Network', 'Sacramento Mountains',
                 'San Acacia Reach', 'Arroyo Hondo', 'El Morro',
                 'Sacramento Mountains Watershed Study')
order by g.name;
```

Expect exactly one row each:

- `Tiffany Fire`, Monitoring Plan, public, has a boundary, **277** things
- `Water Level Network`, Monitoring Plan, draft, no boundary, **487** things
- `Sacramento Mountains`, Monitoring Plan, **draft, no boundary**, **493** things. The area
  that would have supplied one is gone from the webmap.
- `San Acacia Reach`, Monitoring Plan, draft with no boundary until the import, then public
  with one, 47 things
- `Arroyo Hondo`, draft, no boundary, 54 things
- `El Morro`, Monitoring Plan, **draft, no boundary**, 18 things. The row survives the
  strip; only the boundary goes.
- `Sacramento Mountains Watershed Study`, still a public Geographic Area, untouched

And that the deleted names are gone. This should return no rows:

```sql
select name from "group"
where name in ('Tiffany Fire Recovery', 'Tiffany Fire Restoration', 'SM Watershed',
               'water Level Network', 'Sacramento Mtns', 'San Acacia',
               'Ambrosia Lake', 'Grant County', 'Southern Sacramento Mountains');
```

`Ambrosia Lake` is the only deleted group holding wells, and they are meant to survive it.
Capture its membership **before** applying, because afterwards there is nothing left to
join through:

```sql
select thing_id from group_thing_association
where group_id = (select id from "group" where name = 'Ambrosia Lake');
```

Then confirm those three things still exist and simply have no group:

```sql
select t.id, t.name,
       (select count(*) from group_thing_association a where a.thing_id = t.id) as groups
from thing t
where t.id in (<the three ids>);
```

Three rows, `groups` = 0. On production this check is moot: `Ambrosia Lake` has no members
there.

### About the wells layer jump

222 to 453 is expected, and it is a net of two opposing effects.
`ogc_actively_monitored_wells` inner-joins group memberships filtered to
`release_status = 'public'`, so a well appears only if it belongs to at least one public
group. Publishing 10 merge targets brings their wells in. The removals push the other way,
deleting 15 public groups and demoting 8 more to draft, which takes their memberships back
out. The import then adds 5 more by publishing `Carrizozo` and `San Acacia Reach`.

None of this is new exposure. The wells come from `ogc_water_well_summary`, which is
transitively restricted to public things: its `wl_agg` join requires water-level
observations, and that CTE filters `thing.release_status = 'public'`. Verified on staging,
the view holds zero non-public things. So what changes is that already-published wells now
show their project membership. Record the before and after counts anyway.

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

Final state: `group` rows 78, Geographic Areas 30, `ogc_project_areas` 44,
`ogc_actively_monitored_wells` 458, and groups with a boundary and
`release_status = 'draft'` still 0.

The removals do not change what the importer does. All 34 mapped names that already exist
own a live feature, which is precisely why none of them was removed, so the same 32 come back
unchanged and the same 2 are updated.

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

  After the removals this is sharper than it used to be. Eight rows were deliberately left
  draft with their boundary removed, so if one somehow keeps a boundary, `--force` would
  republish exactly what the removal pass just retired.

---

## 7. What the removal pass will and will not touch

Removals are driven by two hand-reviewed name lists in the migration, not by a general
rule, and that is deliberate.

`WEBMAP_ORIGIN_NAMES` holds the 37 groups that came from the webmap, taken from the
`group name origin` column of `before-after-STAGING-kas2`. Nothing in the `group` table
records provenance, so this cannot be derived. `STALE_BOUNDARY_NAMES` holds the 8 legacy
rows whose boundary is retired.

The tempting version is a rule: *strip any boundary from any group that owns no live
feature*. It describes the same 8 rows today. It also describes any group somebody creates
between now and the day this runs on production, and a one-time migration should not be
able to retire a boundary nobody reviewed. If the layer changes again, the lists get
re-derived from a fresh sheet and re-reviewed. That is the intended maintenance path.

Two consequences:

- A webmap area added and then removed *after* this review will not be removed. It is not in
  the list, so the migration leaves it, and someone has to notice.
- Running this against a database whose group names differ from staging's will remove less
  than expected rather than more. Under-reaching is the safe direction, and the dry run
  shows the shortfall as missing lines rather than as an error.
