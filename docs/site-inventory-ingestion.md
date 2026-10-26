# Plan: generalize well inventory ingestion to thing inventory ingestion (all `thing_type`s)

## Context

`oco well-inventory-csv` only imports things where `thing_type = "water well"`. The field team has started inventorying springs, streams, meteorological stations and other `thing_type`s. One spreadsheet will be used to ingest data for things of each `thing_type`. That spreadsheet has shared columns plus columns that apply to only one type. Decisions already made:
- A **`thing_type` column** on each row selects the type, and one CSV may mix types.
- **Every lexicon `thing_type`** is in scope. The type-specific fields are still being finalized.
- **Hard rename** of the CLI to `oco site-inventory-csv`, with no alias. "Site" is the user-facing name only. Internally the code keeps the `thing` naming: modules, functions, classes and the registry.

What the code looks like today:
- `Thing` is a single table with no inheritance (`db/thing.py:61`). Type-specific columns are grouped into sections marked by comments (the "Well-related columns" section starts at `db/thing.py:103`, and `spring_type` is at `db/thing.py:156`). New columns follow that pattern: a comment marks the section and the column name has no type prefix.
- The type is chosen per endpoint (`CreateWell`/`CreateSpring` in `schemas/thing.py`). `add_thing` gates the well child tables on `thing_type == "water well"` (`services/thing_helper.py:342`).
- The importer is `services/well_inventory_csv.py`. `_add_csv_row` (L629-937) hard-codes `CreateWell`, `thing_type="water well"`, `find_water_wells_by_name`, `activity_type="well inventory"`, and the water-level sample.
- The row schema is one flat `WellInventoryRow` (`schemas/well_inventory.py:226`). Extra columns are silently ignored. With mixed types, that would silently drop a well column filled in on a spring row.
- `docs/data-modeling-new-datasets.md` §3 already sets the rule: a new feature type is a `Thing` with a lexicon `thing_type`, not a new table. That rule decides the model shape below.

## Recommended approach

The work lands as **stacked PRs**. Each PR branches from the one before it, so it can be reviewed while the earlier one is still open, and they merge in order. Behaviour stays identical until a type is registered.

### PR 1: rename only, no behaviour change (breaking)
- CLI: `cli/cli.py:612` `@cli.command("well-inventory-csv")` becomes `"site-inventory-csv"`, and the Python function becomes `thing_inventory_csv`, following the internal naming. Rename `well_inventory_csv` in `cli/service_adapter.py:37` to `thing_inventory_csv`, and `WellInventoryResult` to `ThingInventoryResult`.
  - Update `[WELL INVENTORY IMPORT]` banner to `[SITE INVENTORY IMPORT]` banner at `cli/cli.py:640-642`.
- Delete `api/well_inventory.py`. The file is fully commented-out and serves no current purpose. Leaving that file in the codebase will add confusion and muddy repo-wide searches.
- Rename modules with `git mv` so history is kept:
  - `services/well_inventory_csv.py` becomes `services/thing_inventory_csv.py`, and `import_well_inventory_csv` becomes `import_thing_inventory_csv`.
  - `schemas/well_inventory.py` becomes `schemas/thing_inventory.py`.
  - `tests/test_well_inventory.py` becomes `tests/test_thing_inventory.py`.
- Split the PR into **two commits**:
  1. The `git mv` moves alone, with no edits inside the files.
  2. The renames inside the files: functions, imports, the CLI command name and messages.

  Git only detects a rename when the old and new files are similar, so this ensures each move shows as a rename on GitHub, and `git log --follow` and `git blame` still reach the old history.
- Update the callers in `tests/test_cli_commands.py:551,631`, `tests/features/steps/well-inventory-*.py`, `tests/test_data_migrations.py`, `tests/test_domain_units.py`, `tests/test_water_level_csv_service.py`, and the docstrings in `cli/ingest_report.py` and `services/ingest_result.py`.
- **Update the docs that name the old command or modules in the same PR:**
  - the root `README.md`, including its CLI section, which should list `oco site-inventory-csv`;
  - `CLAUDE.md` ("CSV importer field staff" section);
  - `docs/sample-collector-link.md` (L31-60);
  - `docs/data-modeling-new-datasets.md` §6 (L262 cites `well_inventory_csv.py`);
  - anything else under `docs/` that a `grep -rn "well-inventory\|well_inventory" docs README.md CLAUDE.md` turns up, except the release runbooks and `CHANGELOG.md`, which are historical.
- **Update the existing data migrations to reflect inventory lexicon term name change** (`data_migrations/migrations/20260914_*`, `20261001_*`). They describe history. Do _not_ change the name of the scripts.
- Commit as `feat(thing-inventory)!:` with a `BREAKING CHANGE:` footer so release-please flags the rename in `CHANGELOG.md`.

### PR 2: dispatch framework, with water well as the only registered type
1. **Domain** (new file `domain/thing_types.py`; plain functions, no imports from db, schemas or pydantic, per ADR4):
   - `require_known_thing_type(thing_type, known_thing_types) -> str` raises `UnknownThingType(ValueError)` when the value is not a `thing_type` lexicon term. Spreadsheets submit only exact lexicon terms, so it normalizes nothing: it returns the value unchanged or raises. The service passes in the known terms so the domain module stays free of database imports.
   - `foreign_columns(own_columns, all_known_columns, populated_columns) -> list[str]` raises `ForeignTypeColumns(ValueError)` when a row fills another type's columns. This replaces the silent drop.
   - The column sets are not hand-maintained. The service builds them from the **`...InventoryRow` classes**, not the `Create...` schemas. For each row it takes the columns of every registered row class (`model_fields` plus their aliases) and subtracts the ones the row's own class declares. Adding a field to a row class therefore updates the check automatically.
   - **Why not the Create schemas:** they describe the API and the database, not the spreadsheet, and the names differ:
     - CSV `total_well_depth_ft` is `well_depth` in `CreateWell`, and `casing_diameter_ft` is `well_casing_diameter`, stored in inches.
     - Many CSV columns have no Create field at all: the contact blocks, the water-level block, the permissions and the notes columns.
     - The check runs on the CSV headers, so it has to use the CSV names.
   - Because these are `ValueError`s, each one fails a single row and the import continues, which is the existing importer contract.
2. **Row schemas** (`schemas/thing_inventory.py`). There is **one row class per lexicon `thing_type` term**. Related terms share an intermediate base class that holds their common columns:
   ```
   BaseInventoryRow                          shared columns + thing_type, UTM/contact checks
   ├── BaseWellInventoryRow                  well columns + water-level block
   │   ├── WaterWellInventoryRow
   │   ├── ObservationWellInventoryRow
   │   ├── PiezometerInventoryRow
   │   └── ...                               one per well term
   ├── SpringInventoryRow                    spring columns (PR 4)
   ├── BaseStreamInventoryRow                stream columns
   │   ├── PerennialStreamInventoryRow
   │   └── EphemeralStreamInventoryRow
   ├── MeteorologicalStationInventoryRow
   └── ...                                   one per remaining term
   ```
   - `BaseInventoryRow` holds the shared columns: project, point id, `thing_type`, date_time, field_staff 1-3 and the sampler, UTM and elevation, the contact_1 and contact_2 blocks, directions, public_availability, permissions and the generic notes. It keeps the UTM and contact cross-checks from `validate_model` (L393-484) and the date_time and utm_zone normalizers.
   - `BaseWellInventoryRow(BaseInventoryRow)` takes the well columns, the water-level block, the `Complete` monitoring_frequency normalizer (L352) and the `depth_to_water_ft` rule (L414). In PR 2, `WaterWellInventoryRow` adds nothing to it.
   - **Give each subclass validator its own name** (for example `validate_well`). Pydantic replaces a parent validator when a subclass reuses its method name, so a second `validate_model` would quietly stop the UTM and contact checks running.
   - **Every `thing_type` has its own class, even if it only inherits from its family base class.** For example `class PiezometerInventoryRow(BaseWellInventoryRow): pass`, or `class OtherInventoryRow(BaseInventoryRow): pass` for a term with no family. Only these term classes are registered. Family base classes such as `BaseWellInventoryRow` never validate a row directly.
   - **Siblings share columns through their base class.** The foreign-column check treats a column as belonging to every class that declares or inherits it. A piezometer row may therefore fill `well_depth` columns, and a spring row may not.
   - **Measurement blocks are mixins**, not base fields. The water-level block becomes `WaterLevelMeasurementFields`, so another type that needs the same block can add it without inheriting well columns.
   - `WellInventoryRow` disappears in this PR. PR 1 only moves the file.
   - Point id: rename `well_name_point_id` to `point_id`, and keep `AliasChoices("point_id", "well_name_point_id")` so existing sheets still validate. Keep the existing aliases (`well_hole_status`, `measuring_person` and so on).
3. **Registry** (new file `services/thing_inventory_types.py`). Define one `ThingInventoryType` dataclass per type with these fields:
   - `row_model`
   - `build_create_payload(model, loc, group) -> dict`: the `CreateWell(...)` block currently at L710-737.
   - `notes_spec`: the `build_notes` tuple currently at L677-695.
   - `add_type_records(session, model, thing, fe, participants)`: the water-level Sample and Observation block currently at L805-870.
   - `permission_types`: "Datalogger Installation" is well-only.

   There is one registry entry per lexicon term. Hooks can be shared: every well term uses the same well hooks, every stream term the stream hooks. PR 2 registers only `"water well"`. Every value at registration time is copied from the current code, so this PR changes behaviour in only three ways: the type-specific note wording (step 5), names are checked across every `thing_type` (step 4), and a re-imported row is reported and counted as skipped rather than silently counted as imported (step 4).
4. **Service** (`services/thing_inventory_csv.py`):
   - In `_make_row_models` (L522), check `thing_type` with `require_known_thing_type`, look up the registry entry, then validate the row with that type's `row_model` and run `foreign_columns`. A value that isn't a lexicon term fails the row at the first step, so later steps never see an unrecognized value and nothing needs normalizing.
   - A lexicon term that has no registry entry yet becomes a row error: `f"thing_type {thing_type} not yet supported by inventory import"`.
   - `_add_csv_row` keeps its shared spine: the location and elevation provenance, `add_thing(thing_type=model.thing_type)`, the FieldEvent, `ensure_field_event_participants` (`services/field_event_participant_helper.py:61`), the FieldActivity, the contacts and the permissions. It calls the registry hooks for everything type-specific.
   - **Two checks before a row is written, in this order.** These are decisions made with the team; the behaviour can be relaxed later.
     - `thing.name` is *not* unique in the database: there is no constraint, and `db/thing.py:86` carries a `# TODO: should name be unique?`. The importer enforces uniqueness in code.
     - **Check 1, already imported → skip, and say so.**
       - `_find_existing_imported_well` (L485-519) becomes `_find_existing_imported_thing(session, model)`.
       - It matches on **name and inventory date**: `Thing.name == point_id`, `FieldEvent.event_date == model.date_time`, and `FieldActivity.activity_type ==` the inventory activity type. The activity type is what makes the match an earlier inventory import, rather than some other visit at the same moment.
       - Drop its second branch, the water-level sample-name match (L489-506). Every inventory import creates its FieldEvent with `event_date = date_time` (L777-781), so the date match already finds those rows.
       - Run it in the import loop, **before** the row's savepoint, rather than inside `_add_csv_row`.
       - On a match the row is **skipped, not imported and not an error**: the loop logs `f"Row {row_number} ('{point_id}', {date_time}) was already imported; skipping."` through `logging.info` and `progress_callback`, and appends it to a new `skipped` list.
       - Today such a row is returned as the existing well's name and counted as **imported** (L244-248), so the summary overstates imports and the operator is never told. Instead, add `total_rows_skipped` to the result `summary` (L330-336), show it in the CLI summary (`cli/ingest_report.py` `import_summary_rows`), and leave skips out of `total_rows_imported`. A run whose only outcomes are imports and skips exits 0.
       - If the match's `thing_type` differs from the row's, it is not a re-import of the same row. Fail the row with `f"Site '{point_id}' was already imported as {existing.thing_type}"` instead of skipping it, so a corrected type is never silently ignored.
     - **Check 2, name already taken → error.** For rows that passed check 1, a single `find_things_by_name(session, name)` call with **no type filter** replaces `find_water_wells_by_name`. Any existing thing with that name, of any `thing_type`, fails the row with `f"Site already exists in database for point_id '{name}'"`.
     - **What this means for operators:** re-running a CSV after fixing a few rejected rows skips the rows that already imported, with a "Row n was already imported" line for each, and imports the fixed ones. A row whose name matches a different site, or an earlier inventory on another date, is an error.
     - Update the error-to-field mapping in the import loop. It recognises the old message by its prefix (`"Well already exists in database for well_name_point_id "`, L271-274) to set `field = "well_name_point_id"`. It must match `"Site already exists in database for point_id "` and set `field = "point_id"`, or the error loses its column.
     - Put a comment at the `find_things_by_name` call in `services/thing_inventory_csv.py` saying that the cross-type rule is deliberate for now and can be relaxed later to uniqueness within a `thing_type`.
     - **No database constraint in this work.** Legacy transfers may already have produced the same name under different types. A unique index would first need an audit of existing duplicates and a cleanup data migration, so it belongs in a separate ticket, not here. Before PR 2 merges, run `SELECT name, array_agg(DISTINCT thing_type) FROM thing GROUP BY name HAVING count(*) > 1` on staging, so the team knows which existing names will now block an import.
   - Make the user-facing messages say **site**, not thing, to match the `site-inventory-csv` command: "Well already exists…" becomes `f"Site already exists in database for point_id '{name}'"`. Internal names stay `thing`.
5. **Remove the hard-coded `water well` from the import path.** First add a well family to `domain/thing_types.py`: a `WELL_THING_TYPES` frozenset (`water well`, `observation well`, `piezometer`, `monitoring well`, `production well`, `injection well`, `exploration well`, `test well`, `abandoned well`, `dry hole`, `artesian well`, `dug well`) and `is_well_thing_type(thing_type) -> bool`. Each import-path site then changes as follows:

   **a. `add_thing`, `services/thing_helper.py`**
   - *Today:* `if thing_type == WATER_WELL_THING_TYPE:` (L342) gates the measuring point, the well provenance, well purposes, casing materials and **all four status histories** (L342-452). Any other type silently loses them.
   - *Change:*
     - Gate on `is_well_thing_type(thing_type)`.
     - Move the **Monitoring Status** history (L442-452) into the universal section, beside `monitoring_frequencies` (L495), which is already universal. Open, Datalogger Suitability and Well Status stay well-only.
     - For readability, move their pops (`is_suitable_for_datalogger`, `is_open`, `well_status`, L298-300) out of the "UNIVERSAL THING RELATED TABLES" block and into the "WATER WELL SPECIFIC RELATED TABLES" block (L307-326). The pops still run for every type, because `Thing(**data)` (L329) would reject the extra keys. `monitoring_status` (L301) stays in the universal block, since its history is now universal.

   **b. `_add_csv_row`, the Thing payload, `services/well_inventory_csv.py:710,760`**
   - *Today:* `CreateWell(...)` and `add_thing(..., thing_type="water well")`.
   - *Change:* `registry[model.thing_type].build_create_payload(...)` and `add_thing(..., thing_type=model.thing_type)` (steps 3-4).

   **c. `_add_csv_row`, the well-only work around the Thing, `services/well_inventory_csv.py`**
   - *Today:* these run the same way for every row, whatever its type:
     - the notes spec, including the historic depth-to-water note (L673-695)
     - the measuring-point height (L706-708)
     - the groundwater-level FieldActivity, Sample and Observation, plus the "groundwater level" Parameter lookup (L805-870)
     - the "well inventory" wording in the FieldEvent and FieldActivity notes (L779, L801, L831)
     - the "Datalogger Installation" permission (L925)
   - *Change:*
     - Read the registry entry for `model.thing_type` and dispatch everything type-specific through its hooks: `notes_spec`, `add_type_records(session, model, thing, fe, participants)` for the related FieldActivities, Samples and Observations, and `permission_types`.
     - The well hooks take the current code unchanged, and every well kind shares them.
     - A type with no related records gets a no-op `add_type_records`, so a spring row never creates a groundwater-level activity.
     - Notes stay specific to the row's `thing_type`:
       - FieldEvent (L779): `f"Initial field event from {thing_type} inventory import"`
       - FieldActivity (L801): `f"{thing_type.capitalize()} inventory conducted during field event."`
       - the well hook's groundwater-level FieldActivity (L831): `f"Groundwater level measurement activity conducted during {thing_type} inventory field event."`

   **d. `_find_existing_imported_well`, `services/well_inventory_csv.py:499,514`**
   - *Today:* `Thing.thing_type == "water well"`.
   - *Change:* it becomes `_find_existing_imported_thing`, matching on name and inventory date across all types (step 4, check 1).

   **e. `find_water_wells_by_name`, `services/thing_helper.py:88-105`**
   - *Today:* `Thing.thing_type == WATER_WELL_THING_TYPE`.
   - *Change:* it becomes `find_things_by_name(session, name, thing_types=None)`. See step 4 for how the inventory import uses it to check names.

   **f. `oco water-levels` CSV, `services/water_level_csv.py:274,470`**
   - *Today:* it looks up wells by name, and finds existing samples, only for `"water well"`.
   - *Change:* call `find_things_by_name(..., thing_types=WELL_THING_TYPES)` and filter `Thing.thing_type.in_(WELL_THING_TYPES)`, so a piezometer imported by site inventory can also receive water levels.

   **g. `Thing.measuring_point_height` / `measuring_point_description`, `db/thing.py:527,548`**
   - *Today:* they return `None` unless `thing_type == "water well"`.
   - *Change:* use `is_well_thing_type`. The water-level import reads these, so without the change other well kinds would record a null measuring-point height.

   For `water well`, every change here is behaviour-neutral **except the note wording**. The name-check changes are covered in step 4. On the notes: new water-well imports say "water well inventory" where they said "well inventory". Rows already in the database keep their old notes. Update the assertion at `tests/test_thing_inventory.py:417`, and add one checking that a spring row's notes name `spring`.

   **Hard-coded on purpose, or off the import path; not changed here:**
   - `services/scoped_transfer.py:476,1387`: the legacy NM_Aquifer transfer, where every GW site is a water well.
   - API and read paths: `services/thing_helper.py:141,227` (eager-load options), `add_well_screen` (L535), `services/crud_helper.py:180`, `services/group_helper.py:34,54` (group well counts), `api/asset.py:366`, `api/search.py:105`, the `water_wells` OGC collection (`core/pygeoapi.py:22`) and the well materialized views.

   These belong with the later work on publishing well kinds (see "Well kinds other than `water well`…" below). Until then, an imported piezometer won't show up in group well counts, well search or the OGC layers.
6. **`thing_type` column is required.** A blank value or a missing column is a row error, never a silent default to water well. Add `thing_type` to every site fixture in `tests/features/data/site-inventory-*.csv`, and rename those fixtures to `site-inventory-*`.

### PR 3: one inventory activity type, `"site inventory"`
Every inventory import gets the same `FieldActivity.activity_type`, whatever the `thing_type`. The thing's own `thing_type`, reached through FieldEvent, already records what was inventoried, so a per-type term would store that fact twice.
**One Alembic migration renames the term in place, so `well inventory` is gone the moment PR 3 deploys.**
- **The migration:** The upgrade renames the `well inventory` lexicon term to `site inventory`, so the `ON UPDATE CASCADE` FKs rewrite every referencing row. The term keeps its id, so its category association carries over.
  - If `site inventory` already exists (a re-upgrade after a downgrade), the upgrade instead moves `field_activity` rows from `well inventory` to `site inventory`, then deletes `well inventory`.
  - The downgrade re-inserts `well inventory`, with its definition and `activity_type` category association. It then sets `activity_type = 'well inventory'` on `field_activity` rows whose `activity_type` is `site inventory` and whose FieldEvent's thing is a `water well`. It keeps `site inventory`, because non-well inventories have no earlier value to go back to.

```python
def upgrade():
    conn = op.get_bind()
    site_exists = conn.execute(
        sa.text("SELECT 1 FROM lexicon_term WHERE term = 'site inventory'")
    ).scalar()

    if not site_exists:
        # First upgrade: rename in place. CASCADE rewrites field_activity,
        # and the category association carries over with the id.
        conn.execute(sa.text(
            "UPDATE lexicon_term SET term = 'site inventory', definition = :d "
            "WHERE term = 'well inventory'"
        ), {"d": ...})
    else:
        # Re-upgrade after a downgrade: both terms exist. Move the rows,
        # then drop the old term (its category association cascades).
        conn.execute(sa.text(
            "UPDATE field_activity SET activity_type = 'site inventory' "
            "WHERE activity_type = 'well inventory'"
        ))
        conn.execute(sa.text("DELETE FROM lexicon_term WHERE term = 'well inventory'"))

```
- **Why one step clears every reference:**
  - Every `lexicon_term()` FK is `onupdate=CASCADE` (`db/base.py:87`), so Postgres rewrites every `field_activity.activity_type` row inside the same transaction.
  - The category association keys on `term_id`, not the term text (see the `b2c3d4e5f6a7` SQL), so it needs no change.
  - `field_activity` is not versioned, so no history table keeps the old text.
  - Nothing in `alembic/` or `db/` refers to `well inventory` by name.
- **Why Alembic and not a data migration:** the repo rule (`docs/data-modeling-new-datasets.md` §6) sends row changes to data migrations. But deploys run only `alembic upgrade head` (`.github/workflows/CD_*.yml`), and a data migration waits until someone runs it by hand. If the rename were a data migration, either the new code would deploy before `site inventory` existed, and every import would fail the FK, or both terms would stay live until someone ran it. This is the same exception `b2c3d4e5f6a7_transducer_data_maturity.py` made when it backfilled rows its schema change needed (L100-107). Say so in the migration docstring.
- **Before writing it,** confirm with `\d+ field_activity` on staging that the activity_type FK really has `ON UPDATE CASCADE`. Models declare it, but older tables may predate the declaration. If it is missing, the migration first runs `UPDATE field_activity SET activity_type = 'site inventory' WHERE activity_type = 'well inventory'` inside the same transaction, with the FK deferred or temporarily dropped.
- `core/lexicon.json:1850-1851` becomes `"site inventory"`, and so does the category description at L5. Otherwise `oco initialize-lexicon` would recreate the old term on fresh databases.
- Code: replace the hard-coded `activity_type="well inventory"` (was L800), and the activity-type filter in `_find_existing_imported_thing` (was L516), with the module constant `INVENTORY_ACTIVITY_TYPE = "site inventory"`. It is not a registry field, because it is the same for every type. Update the test assertions at `tests/test_thing_inventory.py:432,708`.
- **Data migrations** `20260914_0001` and `20261001_0001` find imported wells with `WELL_INVENTORY_ACTIVITY_TYPE = "well inventory"`. Change that constant, and the `tests/test_data_migrations.py:1552-1608` helpers, to `"site inventory"`. Otherwise a re-run after the rename silently matches nothing. Their docstrings, which describe history, stay as they are.
- **Test:** after `alembic upgrade head`, no `lexicon_term` row and no `field_activity` row holds `well inventory`, and a seeded well-inventory `field_activity` row now reads `site inventory`. Then `alembic downgrade -1` restores it. Then upgrade again: there is exactly one `site inventory` term, still in the `activity_type` category, and no row holds `well inventory`.

### PR 4 to PR n: one PR per thing_type, starting with **spring** (it already has schemas and an API)
Each type PR follows the same checklist, which will also live in the docs:
1. **Classify each new column** using `docs/data-modeling-new-datasets.md` §3-4 before writing any code:
   - A static attribute of the feature becomes a nullable column on `thing`, or a `lexicon_term()` FK for controlled vocabularies. Name it without a type prefix.
   - A value measured on the visit (spring discharge, stream flow, temperature) becomes **Sample and Observation**, following the water-level pattern, not a column.
   - A value that changes over time goes into a history table such as StatusHistory or MonitoringFrequencyHistory.
   - An alternate id goes into `ThingIdLink`.
2. **Model:** add the columns to the appropriate section of `db/thing.py`, for example spring columns in the spring section next to `spring_type`. If the type has no section yet, start one under a comment header in the same style as "Well-related columns".
3. **Migration:** use the idempotent template `alembic/versions/f1a2b3c4d5e6_add_nma_formation_zone_to_thing.py`, which adds to **both `thing` and `thing_version`**. Revise the current head (check with `alembic heads`).
4. **Lexicon:** add new categories and terms to `core/lexicon.json`. If a deployed database needs them before `oco initialize-lexicon` runs, also add an alembic insert, as in `b2c3d4e5f6a7_transducer_data_maturity.py`.
5. **`add_thing`:** add a branch for any type-specific child tables, alongside the existing `WATER_WELL_THING_TYPE` gate.
6. **Importer:** add the term's `<Term>InventoryRow`, under a shared base class if sibling terms have the same columns. The foreign-column check picks up the new fields on its own.
7. **Registry entry:** yes, every type needs one, with all four hooks filled in for that type:
   - **`build_create_payload(model, loc, group) -> dict`** maps the row's CSV columns onto `thing` columns, for example `spring_type`, plus the shared fields every payload carries: `location_id`, `group_id`, `name`, `release_status`, `first_visit_date`, `notes`, `alternate_ids`, `monitoring_frequencies` and `monitoring_status`. Do any unit conversion here, the way the well payload converts casing diameter from feet to inches (`convert_ft_to_in`).
     - The API schemas are deferred until the UI needs them (see below), so the payload is a **plain dict**, not a `CreateSpring`. The `<Term>InventoryRow` has already validated the values, and `add_thing` accepts a dict.
     - Use the shared fields straight from `BaseInventoryRow`, through a small helper, so each type's payload adds only its own columns.
   - **`notes_spec`:** which CSV note columns become which Thing note types.
   - **`add_type_records`:** any FieldActivities, Samples and Observations for values measured on the visit (from step 1), or the no-op.
   - **`permission_types`:** which permission columns apply to the type.

   Terms that share a family share hooks. A family's first PR writes them, and its later terms only add a registry entry that points at them. All the well kinds can therefore be registered together in one small PR using the water-well hooks from PR 2.
8. **Tests:** see below.

**Not in these PRs; done later, when the UI needs them:**
- The Thing API schemas in `schemas/thing.py`: extending `CreateSpring` / `SpringResponse` / `UpdateSpring`, adding equivalents for other types, and the `ThingResponse` union (L347).
- Per-type API routes such as `/thing/spring`. Each type needs a route whose name identifies it. Today the type is derived from the path (`api/thing.py:162,305`), which cannot produce `diversion of surface water, etc.` or `lake, pond or reservoir`. Replace that derivation with an explicit slug-to-term map that reuses the OGC collection ids from `core/pygeoapi.py` (for example `/thing/diversions-surface-water` and `/thing/lakes-ponds-reservoirs`).
- Publishing the new columns in OGC. Every non-well type already has its own view and collection: public `ogc_<id>` and internal `ogc_internal_<id>`, defined in `core/pygeoapi.py` `THING_COLLECTIONS`. Migrations `a2b3c4d5e6f7` and `b3c4d5e6f7a9` already removed the well columns from them. The views list their columns explicitly, so a new `thing` column breaks nothing; it just isn't published. When a layer should show it, add a view migration in the `b3c4d5e6f7a9` pattern and a `core/ogc-field-descriptions.yml` entry.

The importer needs none of these: it builds its payload in the registry's `build_create_payload` and passes it to `add_thing`.

**Well kinds other than `water well` are registered but not yet published.** Piezometer, observation well and the rest import through `BaseWellInventoryRow`. However, the `water_wells` OGC layer and the well materialized views (water elevation, depth-to-water trend, well summary, NGWMN) all filter on `thing_type = 'water well'`, so these rows appear on no layer. The same goes for the API read paths listed in PR 2 step 5 (group well counts, well search). `docs/thing-inventory-csv.md` must say so. Widening those views is a separate, later piece of work.

## Tests
- `tests/test_domain_thing_types.py` (new, database-free): `require_known_thing_type` accepts every lexicon term and raises `UnknownThingType` for anything else (including near-misses such as `Water Well`); foreign-column detection; `is_well_thing_type` is true for every well term and false for the rest; every `WELL_THING_TYPES` member is a `thing_type` term in `core/lexicon.json`.
- `add_thing` (in `tests/test_thing.py` or a new `tests/test_thing_helper.py`):
  - A `piezometer` gets the measuring point, well provenance, purposes and the Open, Datalogger and Well Status histories, exactly as a `water well` does.
  - A `spring` given a `monitoring_status` gets a Monitoring Status history.
- `tests/test_water_level_csv_service.py`: a water-level row for a `piezometer` imports, and a row for a `spring` with the same name is still rejected.
- `tests/test_thing_inventory.py`:
  - The existing well cases stay **unchanged** (regression). In particular, the database-contents test at L72 must still pass with only the fixture rename. **Two exceptions, both from the re-import change:**
    - `test_rerunning_same_well_inventory_csv_is_idempotent` (L929) also asserts the new reporting on the second run: every row is in `skipped`, with its "Row n was already imported" message, `total_rows_skipped` equals the row count, `total_rows_imported` is 0, no rows are added, and the exit code is 0.
    - `test_rerunning_import_keeps_the_original_sample_participant` (L634) keeps its assertion, and also checks that the row is reported as skipped.
  - New name-check cases:
    - Same name, different inventory date: fails with "Site already exists".
    - Same name and date, different `thing_type`: fails with "…was already imported as…".
    - A file containing both a skipped row and a new row: the new row imports and the summary counts one of each.
    - The "Site already exists" error carries `field = "point_id"`.
  - New cases: a mixed-type CSV imports each row to the right `thing_type`; a spring row with `total_well_depth_ft` filled is a row error; an unregistered type is a row error; a missing `thing_type` column is rejected; a point id already used by a thing of another type is rejected with the "Site already exists…" message; a legacy `well_name_point_id` header still works; a non-well row creates only the inventory FieldActivity, with no groundwater-level FieldActivity, Sample or Observation and no "Datalogger Installation" permission.
  - Per type: one database-contents test, parametrized over the registry where the assertions match.
- `tests/test_cli_commands.py`: the command name, plus the reporting of validation errors.
- BDD: `tests/features/thing-inventory-csv.feature` with mixed-type scenarios, written directly in this repo.

## Documentation
1. **New `docs/thing-inventory-csv.md`**, the operator and developer reference:
   - The column dictionary in three tables: shared columns, then type-specific columns per type, with required/optional, aliases, units and the target table and column.
   - How dispatch works: `thing_type`, then the registry, then the row model.
   - The foreign-column rule.
   - The "how to add a thing_type" checklist above.
   - A **"Design decisions"** section, here in `docs/` rather than in an ADR. It records:
     - why the design keeps one `thing` table, with type-specific columns grouped under comment headers and no name prefixes, rather than per-type tables (following data-modeling §3);
     - why there is one row class per lexicon term, with shared base classes;
     - why types are dispatched through a registry rather than a Pydantic discriminated union (the comma-containing terms and the shared hooks);
     - why the foreign-column sets come from the row classes and not the Create schemas;
     - why foreign columns are rejected;
     - why the CLI was hard-renamed.
   - This doc starts in PR 2 and grows by one section per type PR.
2. **Later doc updates:** PR 1 handles the renames (see above). PR 2 adds a short *Thing inventory importer* section to `CLAUDE.md` that points to the new doc. Leave historical documents unchanged: ADR4, the release runbooks and `CHANGELOG.md`.
3. **Release notes:** PR 1's says the old command is gone. PR 2's says spreadsheets now need a `thing_type` column. PR 3's says the activity type `well inventory` is now `site inventory`, so anyone querying on the old term needs to update. Existing rows are renamed automatically on deploy, so there is no manual step.
4. **CHANGELOG:** generated automatically from conventional commits; use the `thing-inventory` scope.

## Open item (blocks PR 4 onward, not PRs 1-3)
The per-type column list for the spreadsheet is still needed. Each field gets classified with the step-1 rules above (thing column, observation, history table or id link) before any migration is written.

## Verification
- `uv run pytest tests/test_domain_thing_types.py tests/test_thing_inventory.py tests/test_cli_commands.py tests/test_thing.py tests/test_water_level_csv_service.py`, and then the full `uv run pytest`.
- `uv run behave tests/features --tags="@backend and @production"`.
- `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head` again for each new migration.
- Manual run: `oco site-inventory-csv tests/features/data/thing-inventory-valid-mixed.csv` against a local database. Then check `select thing_type, count(*) from thing group by 1` and confirm the new columns and observations are populated.
- Regression: after PR 2, importing the old valid well fixture (with the added `thing_type` column) produces the same rows as on `staging`, apart from the FieldEvent and FieldActivity note text. Importing it a second time skips every row, prints a "Row n was already imported" line for each, writes nothing, and exits 0.
