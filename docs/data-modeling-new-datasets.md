# Modelling a New Dataset

**Audience:** developers and Claude sessions taking on a dataset the system
does not yet hold — a spreadsheet from a project, a partner agency's export, a
logger feed, a legacy database.

**What this answers:** where the data belongs in the existing model, what to
build in what order, and which conventions are not guessable from the code.

**What it does not answer:** how to run a specific past ingest. Those live in
their own runbooks — see [Related documents](#related-documents).

---

## 1. The spine

Everything observational hangs off one chain:

```
Location            a place on the ground (PostGIS Point, SRID 4326)
  └── Thing         a monitored feature at that place: well, spring, gauge
      └── FieldEvent        one visit to that Thing on one date
          └── FieldActivity what was done during the visit
              └── Sample    material or reading taken during the activity
                  └── Observation   one value: parameter + value + unit
```

Files: [db/location.py](../db/location.py), [db/thing.py](../db/thing.py),
[db/field.py](../db/field.py), [db/sample.py](../db/sample.py),
[db/observation.py](../db/observation.py).

Two facts about the spine that surprise people:

- **`Location` and `Thing` are separate on purpose.** A `Thing` reaches its
  geometry through `LocationThingAssociation`, so a monitoring point can be
  re-surveyed without rewriting its history. Do not add a geometry column to a
  new Thing-like table.
- **`Sample` is mandatory even when nothing was physically collected.** A
  manual depth-to-water reading is a `Sample` with an auto-generated name (see
  `domain.samples.water_level_sample_name`) carrying one `Observation`. Do not
  invent a sample-free observation path.

Continuous instrument data does **not** use this chain:

```
Thing ── Deployment ── Sensor          the instrument, and when it was down the well
  └── TransducerObservation            the logged series
  └── TransducerObservationBlock       a reviewed/corrected span of that series
```

Files: [db/deployment.py](../db/deployment.py), [db/sensor.py](../db/sensor.py),
[db/transducer.py](../db/transducer.py).

`Observation` is for values produced by a visit. `TransducerObservation` is for
values produced by an instrument on an interval. Choosing wrong here is the
single most expensive modelling mistake in this repo — it decides which
importers, which OGC layers, and which correction workflow apply.

---

## 2. Before writing any code

Answer these about the dataset. If you cannot, the answer is upstream, from the
data provider, not from a design decision.

| Question | Why it decides something |
|---|---|
| What is one row? | A place, a feature, a visit, a value, or an attribute — each lands in a different table |
| Does each row have coordinates, and in what CRS/datum? | Determines whether new `Location`s are created; UTM sources need conversion (`domain.wells.srid_for_utm_zone`) |
| Do the features already exist in `thing`? | Matching to existing Things is a reconciliation problem, not an insert |
| What identifies a feature in the source? | Becomes a `ThingIdLink` row (`relation`, `alternate_id`, `alternate_organization`) — never a new column on `thing` |
| Are values instantaneous, or a series on an interval? | `Observation` vs `TransducerObservation` |
| What are the units, per column? | See [Units](#units-are-per-column) — assume nothing |
| Does an attribute change over time? | History table, not a column — see [History tables](#attributes-that-change-get-history-tables) |
| Is any of it public? | `release_status`, and whether it can appear on the public OGC mount |
| Does it carry PII or landowner permissions? | Internal mount only — see [docs/water-well-field-operations-layer.md](water-well-field-operations-layer.md) |
| One-time load, or a recurring feed? | A one-off backfill should not be hardened into a pipeline, and vice versa |

Write the answers down. `docs/sources/san_acacia.md` is the shape to copy for a
recurring external source: endpoints, auth, field mapping, and what was
explicitly *not* ingested.

---

## 3. Where does it go?

Work down this list and stop at the first match.

**1. It is a place with no monitored feature.** → `Location`. Rare on its own;
usually you want a Thing too.

**2. It is a monitored feature.** → `Thing`, with `thing_type` set to a
`lexicon_term`. If the type is new, add the term to
[core/lexicon.json](../core/lexicon.json) under the `thing_type` category rather
than adding a table. A new `thing_type` is cheap; a new feature table is not.

**3. It is an alternate identifier for a feature.** → `ThingIdLink`. Source
system IDs, OSE well record numbers, partner agency IDs all go here.

**4. It is a visit or a thing done during a visit.** → `FieldEvent` +
`FieldActivity`, with `activity_type` from the lexicon. People on the visit are
`FieldEventParticipant` rows pointing at `Contact`.

**5. It is a measured value from a visit.** → `Sample` + `Observation`. The
measured quantity is a `Parameter` ([db/parameter.py](../db/parameter.py)); add it
to the parameter seed rather than encoding the quantity in a column name.
Depth-resolved values use `Sample.depth_top` / `depth_bottom`.

**6. It is an instrument series.** → `Sensor` + `Deployment` +
`TransducerObservation`. A reviewed/corrected span is a
`TransducerObservationBlock`; read
[docs/hydrograph-correction-publish.md](hydrograph-correction-publish.md)
before touching that path.

**7. It is an attribute of a feature that changes over time.** → a history
table (`StatusHistory`, `MeasuringPointHistory`, `MonitoringFrequencyHistory`,
`PermissionHistory`), not a column.

**8. It is metadata *about* a value or record.** → one of the polymorphic
tables, via the mixin:
  - where a value came from and how accurate it is → `DataProvenance`
    ([db/data_provenance.py](../db/data_provenance.py)), keyed by
    `target_table` + `target_id` + `field_name`
  - free text → `Notes` ([db/notes.py](../db/notes.py)), not a `notes` column
  - who may sample or install → `Permission` ([db/permission.py](../db/permission.py))

**9. It is a grouping of features.** → `Group` + `GroupThingAssociation`, with
`group_type` from the lexicon. `Group.project_area` holds an optional polygon.
Note: `group_type` is a label, **not** provenance — a group typed
`Geographic Area` may itself be a legacy project, and the two must not be
merged on type alone.

**10. It is a large foreign schema you do not yet fully understand.** → a
1:1 staging mirror first, transform second. That is the `NMW_*` pattern in
[db/nmw_legacy.py](../db/nmw_legacy.py): faithful column-for-column copy, original
source column names preserved as the first positional arg to `mapped_column()`,
snake_case Python attributes. Mirror, load, *then* map into the spine. Do not
transform on the way in.

**11. None of the above.** Now, and only now, a domain-specific table. Keep it
narrow and key it to the spine — `GeochronologyAge`
([db/geochronology.py](../db/geochronology.py)) is one column of payload plus a
`location_id` and a lexicon-backed `method`. If your new table is starting to
grow its own name, date, geometry, and notes columns, it is a `Thing` variant
and you took a wrong turn.

---

## 4. Conventions that are not guessable

### Controlled vocabulary, not free text

Any field with a fixed set of values uses `lexicon_term()` from
[db/base.py](../db/base.py) — a `String(100)` FK to `lexicon_term.term`. Terms and
their categories are seeded from [core/lexicon.json](../core/lexicon.json) by
`core.initializers.init_lexicon` (`oco initialize-lexicon`). Adding a value
means adding it to that file, in the right category, with a definition. The
seed is idempotent and preserves descriptions edited through `/lexicon`.

Free-text `String` columns are for names, identifiers, and prose only.

### Units are per-column

There is **no** repo-wide SI rule. `Location.elevation` is metres (NAVD88);
`Thing.well_depth`, `hole_depth`, `well_casing_depth`, and `well_pump_depth`
are **feet**; `well_casing_diameter` is inches. `Observation` carries its own
`unit` as a lexicon term.

Read the column `comment=` before writing a value. Convert with
`domain.units` (`convert_ft_to_m`, `convert_m_to_ft`, `convert_cm_to_ft`) —
never with an inline literal, and not via `services/util.py`, whose
re-exports are a transition aid.

### Spatial

SRID 4326 everywhere (`core.constants.SRID_WGS84`), PostGIS `Point` for
locations, `spatial_index=True`. UTM sources convert on the way in;
`domain.wells.utm_zone_number` / `srid_for_utm_zone` do the zone arithmetic.
Vertical datum is NAVD88, metres.

### Attributes that change get history tables

A status, a monitoring frequency, a measuring-point height, or a landowner
permission is a `(value, start_date, end_date)` row, not a column on `thing`.
When you then read "the current one" in a view, honour the window:

```sql
WHERE h.start_date <= CURRENT_DATE
  AND (h.end_date IS NULL OR h.end_date >= CURRENT_DATE)
ORDER BY h.start_date DESC, h.id DESC
```

`ogc_actively_monitored_wells` ignores `end_date` and is kept that way only
because changing it would move rows in a published layer. New work follows the
form above. See "Current-record semantics" in
[docs/ogc_conventions.md](ogc_conventions.md).

### `nma_` / `nmw_` prefixes are reserved

A column prefixed `nma_` or `nmw_` means "verbatim from the legacy system,
kept for audit". Do not use those prefixes for new fields, and do not read them
as the authoritative value.

### `properties` JSONB is not a schema escape hatch

`PropertiesMixin` exists for genuinely open-ended extras. A field you know the
name and meaning of gets a column and a migration.

### Mixins carry real behaviour

`AutoBaseMixin` gives snake_case table naming and an integer PK.
`AuditMixin` gives `created_at` / `created_by_*` / `updated_by_*`.
`ReleaseMixin` gives `release_status` (default `"draft"`).
`__versioned__ = {}` opts a model into sqlalchemy-continuum history.
Match what sibling models do rather than picking a subset.

---

## 5. Build order

1. **Model** — add to `db/`, using the mixins above. Match a neighbouring model
   for nullability, comments, and relationship style.
2. **Schemas** — `schemas/`. `Create`: `<type>` for non-nullable,
   `<type> | None = None` for nullable. `Update`: everything optional.
   `Response`: `<type> | None` for nullable. Input validation (422) goes in
   Pydantic validators; database-constraint violations (409) are manual checks
   raising `PydanticStyleException`.
3. **Migration** — `alembic revision --autogenerate -m "..."`. Read the
   generated file; autogenerate misses server defaults, view changes, and
   partial indexes. Keep model nullability and migration DDL aligned.
4. **Rules** — anything that is unit conversion, cross-column validation, or
   deterministic naming goes in `domain/` as a plain function over plain
   values. No `db`, `schemas`, `services`, `fastapi`, `sqlalchemy`, `pydantic`,
   or `httpx` imports. Domain errors subclass `ValueError` because importers
   treat a row-level `ValueError` as a per-row failure. Read
   [ADR4.md](../ADR4.md); extraction is opportunistic, not mandatory.
5. **Service** — `services/` loads rows, calls the domain rule, persists,
   translates errors.
6. **API** — `api/`, one file per resource. Authorization is **opt-in per
   endpoint**, as a type annotation: `user: viewer_dependency`, never
   `user=viewer_dependency` (the latter silently becomes a query parameter).
   Omitting it produces a public endpoint with no error;
   `tests/test_authorization.py` holds the allowlist of intentionally anonymous
   routes and fails on anything else.
7. **Tests** — fixtures in `tests/conftest.py`, POST/PATCH/GET coverage,
   `cleanup_post_test` / `cleanup_patch_test` (both in `tests/__init__.py`).
   Domain rules get database-free unit tests. Cross-cutting behaviour gets a
   `.feature` file in `tests/features/`.
8. **Ingest** — see [Loading the data](#6-loading-the-data).
9. **Publish** — see [Exposing it](#7-exposing-it-via-ogc), if it should be.
10. **Document** — a `docs/sources/<name>.md` for a recurring source; a note in
    `CLAUDE.md` if a future session could get it wrong.

---

## 6. Loading the data

Pick the mechanism by what the load *is*:

| Situation | Mechanism |
|---|---|
| Users upload a CSV | A service under `services/` following `well_inventory_csv.py` / `water_level_csv.py`: parse row, call domain rule, `ValueError` = row rejected, run continues |
| One-time transform of rows already in the database | A **data migration** — `data_migrations/migrations/`, not Alembic |
| Recurring pull from an external API | An ingestion source with its own client and credentials in Secret Manager; document it in `docs/sources/` |
| A legacy SQL Server schema | Staging mirror then transform (see decision 10) |
| A one-off boundary/geometry import | A CLI command, e.g. `cli/project_area_import.py`. Leave it as a script — do not harden a backfill into a pipeline |

### Data migrations

Alembic changes schema. Anything that changes *rows* — a backfill, a
re-parenting, a de-duplication — is a `DataMigration`
([data_migrations/base.py](../data_migrations/base.py)), one module per migration
in `data_migrations/migrations/`, discovered by exporting a module-level
`MIGRATION`. Start from `_template.py`.

- Pin `alembic_revision` to the schema revision the migration assumes.
- Anything that deletes rows or re-points foreign keys **must** supply
  `dry_run` — a read-only preview that does not commit.
- `is_repeatable=True` only if re-running is genuinely safe.
- Use SQLAlchemy Core for large batches: `session.execute(insert(Model), rows)`.

**They do not run on deploy.** CD runs `alembic upgrade head` and nothing else,
so a registered data migration sits unapplied until someone runs it — locally
with `oco data-migrations run <id>`, or against staging/production through the
manually dispatched `Data Migrations` workflow
([.github/workflows/data_migrations.yml](../.github/workflows/data_migrations.yml)).
Start with `action = status`.

---

## 7. Exposing it via OGC

Only if external or desktop-GIS consumers need it.

1. **A view, not a table.** OGC collections read `ogc_*` (public) and
   `ogc_internal_*` (internal) views, created in Alembic migrations. The public
   view carries the `release_status = 'public'` predicate; the internal twin
   drops it. Materialize only if query cost demands it — see
   [docs/pg_cron-nightly-refresh.md](pg_cron-nightly-refresh.md) for how
   materialized views get refreshed.
2. **Register the collection.** Thing-type layers are entries in
   `THING_COLLECTIONS` in [core/pygeoapi.py](../core/pygeoapi.py); analytic layers
   live in `core/pygeoapi-config.yml`; internal-only layers in
   `core/pygeoapi-config-internal.yml` (or `internal_only: True` on a
   thing-type entry). EDR collections are `EDR_COLLECTIONS` — read
   [ADR3.md](../ADR3.md) first.
3. **Name it under the convention.** Layer IDs are a public URL contract and
   renaming breaks consumers silently. Check the do/don't rules in
   [docs/ogc_conventions.md](ogc_conventions.md) **before** merging, and
   add the layer to that doc's inventory.
4. **Describe every field.** Per-column `title` / `description` / unit go in
   [core/ogc-field-descriptions.yml](../core/ogc-field-descriptions.yml), keyed by
   backing relation with the `ogc_`/`ogc_internal_` prefix stripped. Say what
   the value means and its datum — not how the view is assembled. Read
   [docs/ogc-field-descriptions.md](ogc-field-descriptions.md); the
   feature depends on unpinned pygeoapi behaviour.
5. **Decide public vs internal deliberately.** PII, landowner contacts, and
   staff access notes are internal-only with no public twin.

---

## 8. Anti-patterns seen in past ingests

- **Trusting an inherited mapping document.** The San Acacia notes carried a
  well count, an endpoint path, an auth claim, and a payload shape from a
  retired stack — all four wrong against the live API. Verify against the
  source, then supersede the old document explicitly.
- **Matching on the wrong key.** Two field-staff contact lookups differed by a
  `contact_type` filter; the stricter one missed existing contacts and then
  failed on the duplicate insert. Establish the match key once and share it.
- **Silent row loss in a transform.** A continuous-data transfer dropped
  ~391k readings by matching readings to deployment windows; nothing on the
  target side indicated a problem. Count rows in and rows out, and reconcile
  the difference explicitly.
- **Merging on a type label.** `group_type` describes a group's kind, not where
  it came from. Merging by type collapsed records that had to stay distinct.
- **Two sheets that disagree.** A provider's GIS sheet and data sheet each held
  values the other lacked. Reconcile before ingest; do not pick one and hope.
- **Assuming units.** Depths in feet, elevations in metres, in the same table.
- **A new column where a history row belonged.** Works until the value changes
  and the old value is gone.

---

## 9. Pre-merge checklist

- [ ] Every controlled-vocabulary value exists in `core/lexicon.json`, in a
      category, with a definition
- [ ] Units documented in each column's `comment=`, conversions via
      `domain.units`
- [ ] Geometry is SRID 4326; elevations NAVD88 metres
- [ ] Time-varying attributes are history rows, not columns
- [ ] Migration reviewed by hand, not just autogenerated
- [ ] Every new endpoint has an explicit `user: <role>_dependency` annotation,
      or a deliberate entry in `tests/test_authorization.py`
- [ ] `uv run pytest` passes; new domain rules have database-free tests
- [ ] Row counts reconciled: source rows in vs. rows landed, difference
      explained
- [ ] If published: view has the right `release_status` predicate, layer name
      checked against `docs/ogc_conventions.md`, every field described in
      `core/ogc-field-descriptions.yml`, inventory table updated
- [ ] If it carries PII: internal mount only, no public twin
- [ ] A `docs/sources/<name>.md` exists for any recurring source

---

## Related documents

| Document | When |
|---|---|
| [ADR1.md](../ADR1.md) | Why one unified system exists |
| [ADR3.md](../ADR3.md) | Serving observations via OGC API - EDR |
| [ADR4.md](../ADR4.md) | The `domain/` layer and what belongs in it |
| [docs/ogc_conventions.md](ogc_conventions.md) | Layer naming; current-record semantics |
| [docs/ogc-field-descriptions.md](ogc-field-descriptions.md) | Per-field metadata |
| [docs/internal-ogc-desktop-gis.md](internal-ogc-desktop-gis.md) | The internal mount and its credentials |
| [docs/water-well-field-operations-layer.md](water-well-field-operations-layer.md) | PII-carrying layer; the pattern to follow |
| [docs/refine-json-filters-and-virtual-fields.md](refine-json-filters-and-virtual-fields.md) | List filtering and virtual fields in the UI |
| [docs/hydrograph-correction-publish.md](hydrograph-correction-publish.md) | Transducer correction and publish path |
| [docs/sources/san_acacia.md](sources/san_acacia.md) | Worked example of a source document |
| [transfers/README.md](../transfers/README.md) | The deprecated legacy transfer drivers |
