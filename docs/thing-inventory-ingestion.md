# Plan: generalize well inventory ingestion to thing inventory ingestion (all `thing_type`s)

## Context

`oco well-inventory-csv` only imports things where `thing_type = "water well"`. The field team has started inventorying springs, streams, meteorological stations and other `thing_type`s. One spreadsheet will be used to ingest data for things of each `thing_type`. That spreadsheet has shared columns plus columns that apply to only one type. Decisions already made:
- A **`thing_type` column** on each row selects the type, and one CSV may mix types.
- **Every lexicon `thing_type`** is in scope. The type-specific fields are still being finalized.
- **Hard rename** of the CLI to `oco thing-inventory-csv`, with no alias.

What the code looks like today:
- `Thing` is a single table with no inheritance (`db/thing.py:61`). Type-specific columns are grouped into sections marked by comments (the "Well-related columns" section starts at `db/thing.py:103`, and `spring_type` is at `db/thing.py:156`). New columns follow that pattern: a comment marks the section and the column name has no type prefix.
- The type is chosen per endpoint (`CreateWell`/`CreateSpring` in `schemas/thing.py`). `add_thing` gates the well child tables on `thing_type == "water well"` (`services/thing_helper.py:342`).
- The importer is `services/well_inventory_csv.py`. `_add_csv_row` (L629-937) hard-codes `CreateWell`, `thing_type="water well"`, `find_water_wells_by_name`, `activity_type="well inventory"`, and the water-level sample.
- The row schema is one flat `WellInventoryRow` (`schemas/well_inventory.py:226`). Extra columns are silently ignored. With mixed types, that would silently drop a well column filled in on a spring row.
- `docs/data-modeling-new-datasets.md` §3 already sets the rule: a new feature type is a `Thing` with a lexicon `thing_type`, not a new table. That rule decides the model shape below.

## Recommended approach

The work lands as **stacked PRs**. Each PR branches from the one before it, so it can be reviewed while the earlier one is still open, and they merge in order. Behaviour stays identical until a type is registered.

### PR 1: rename only, no behaviour change (breaking)
- CLI: `cli/cli.py:612` `@cli.command("well-inventory-csv")` becomes `"thing-inventory-csv"`, and the function is renamed to match. Rename `well_inventory_csv` in `cli/service_adapter.py:37` to `thing_inventory_csv`, and `WellInventoryResult` to `ThingInventoryResult`.
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
  - the root `README.md`, including its CLI section, which should list `oco thing-inventory-csv`;
  - `CLAUDE.md` ("CSV importer field staff" section);
  - `docs/sample-collector-link.md` (L31-60);
  - `docs/data-modeling-new-datasets.md` §6 (L262 cites `well_inventory_csv.py`);
  - anything else under `docs/` that a `grep -rn "well-inventory\|well_inventory" docs README.md CLAUDE.md` turns up, except the release runbooks and `CHANGELOG.md`, which are historical.
- **Leave the existing data migrations unchanged** (`data_migrations/migrations/20260914_*`, `20261001_*`). They describe history.
- **BDD caveat:** `run_bdd.sh` syncs `tests/features/` from the external **OcotilloBDD** repo. The feature and step renames must land there too, or the next sync will undo them.
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

   There is one registry entry per lexicon term. Hooks can be shared: every well term uses the same well hooks, every stream term the stream hooks. PR 2 registers only `"water well"`. Because every value at registration time is copied from the current code, this PR changes no behaviour.
4. **Service** (`services/thing_inventory_csv.py`):
   - In `_make_row_models` (L522), check `thing_type` with `require_known_thing_type`, look up the registry entry, then validate the row with that type's `row_model` and run `foreign_columns`. A value that isn't a lexicon term fails the row at the first step, so later steps never see an unrecognized value and nothing needs normalizing.
   - A lexicon term that has no registry entry yet becomes a row error: `f"thing_type {thing_type} not yet supported by inventory import"`.
   - `_add_csv_row` keeps its shared spine: the location and elevation provenance, `add_thing(thing_type=model.thing_type)`, the FieldEvent, `ensure_field_event_participants` (`services/field_event_participant_helper.py:61`), the FieldActivity, the contacts and the permissions. It calls the registry hooks for everything type-specific.
   - Generalize the two lookups, in this order:
     1. `_find_existing_imported_well` (L485, hard-coded "water well" at L499 and L514) becomes `_find_existing_imported_thing(session, model)`, which matches on `model.thing_type`.
     2. Then `find_water_wells_by_name` (`services/thing_helper.py:88`) becomes `find_things_by_name(session, name, thing_type=None)`.
   - **Point-id uniqueness is global across thing types**, so a spring cannot share a name with a well.
   - Rename the user-facing messages ("Well already exists…" becomes "Thing already exists…").
5. **`thing_type` column is required.** A blank value or a missing column is a row error, never a silent default to water well. Add `thing_type` to every well fixture in `tests/features/data/well-inventory-*.csv`, and rename those fixtures to `thing-inventory-*`.

### PR 3: one inventory activity type, `"site inventory"`
Every inventory import gets the same `FieldActivity.activity_type`, whatever the `thing_type`. The thing's own `thing_type`, reached through FieldEvent, already records what was inventoried, so a per-type term would store that fact twice.
- **Alembic migration:** rename the lexicon term in place: `UPDATE lexicon_term SET term = 'site inventory' WHERE term = 'well inventory'`, plus the definition. `lexicon_term()` FKs are `onupdate=CASCADE` (`db/base.py:75-89`), so existing `field_activity` rows follow automatically, and `field_activity` is not versioned. The downgrade reverses it. Use `b2c3d4e5f6a7_transducer_data_maturity.py` as the lexicon-migration precedent. Before writing it, check that the lexicon category association rows key on the term and also cascade.
- `core/lexicon.json:1850` becomes `"site inventory"`. Otherwise `oco initialize-lexicon` would recreate the old term.
- Code: replace the hard-coded `activity_type="well inventory"` (was L800) with a module constant, `INVENTORY_ACTIVITY_TYPE = "site inventory"`. It is not a registry field, because it is the same for every type. Also update the `_find_existing_imported_thing` filter (was L516) and the test assertions at `tests/test_thing_inventory.py:432,708`.
- **Data migrations** `20260914_0001` and `20261001_0001` find imported wells with `WELL_INVENTORY_ACTIVITY_TYPE = "well inventory"`. Change that constant, and the `tests/test_data_migrations.py:1552-1608` helpers, to `"site inventory"`. Otherwise a re-run after the rename silently matches nothing. Their docstrings, which describe history, stay as they are.

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
6. **Importer:** add the term's `<Term>InventoryRow`, under a shared base class if sibling terms have the same columns, and register it. The foreign-column check picks up the new fields on its own.
7. **Tests:** see below.

**Not in these PRs; done later, when the UI needs them:**
- The Thing API schemas in `schemas/thing.py`: extending `CreateSpring` / `SpringResponse` / `UpdateSpring`, adding equivalents for other types, and the `ThingResponse` union (L347).
- Per-type API routes such as `/thing/spring`. Each type needs a route whose name identifies it. Today the type is derived from the path (`api/thing.py:162,305`), which cannot produce `diversion of surface water, etc.` or `lake, pond or reservoir`. Replace that derivation with an explicit slug-to-term map that reuses the OGC collection ids from `core/pygeoapi.py` (for example `/thing/diversions-surface-water` and `/thing/lakes-ponds-reservoirs`).
- Publishing the new columns in OGC. Every non-well type already has its own view and collection: public `ogc_<id>` and internal `ogc_internal_<id>`, defined in `core/pygeoapi.py` `THING_COLLECTIONS`. Migrations `a2b3c4d5e6f7` and `b3c4d5e6f7a9` already removed the well columns from them. The views list their columns explicitly, so a new `thing` column breaks nothing; it just isn't published. When a layer should show it, add a view migration in the `b3c4d5e6f7a9` pattern and a `core/ogc-field-descriptions.yml` entry.

The importer needs none of these: it builds its payload in the registry's `build_create_payload` and passes it to `add_thing`.

**Well kinds other than `water well` are registered but not yet published.** Piezometer, observation well and the rest import through `BaseWellInventoryRow`. However, the `water_wells` OGC layer and the well materialized views (water elevation, depth-to-water trend, well summary, NGWMN) all filter on `thing_type = 'water well'`, so these rows appear on no layer. `docs/thing-inventory-csv.md` must say so. Widening those views is a separate, later piece of work.

## Tests
- `tests/test_domain_thing_types.py` (new, database-free): `require_known_thing_type` accepts every lexicon term and raises `UnknownThingType` for anything else (including near-misses such as `Water Well`); foreign-column detection.
- `tests/test_thing_inventory.py`:
  - The existing well cases stay **unchanged** (regression). In particular, the database-contents test at L72 must still pass with only the fixture rename.
  - New cases: a mixed-type CSV imports each row to the right `thing_type`; a spring row with `total_well_depth_ft` filled is a row error; an unregistered type is a row error; a missing `thing_type` column is rejected; a duplicate point id across types is rejected; a legacy `well_name_point_id` header still works.
  - Per type: one database-contents test, parametrized over the registry where the assertions match.
- `tests/test_cli_commands.py`: the command name, plus the reporting of validation errors.
- BDD: `thing-inventory-csv.feature` with mixed-type scenarios, written in **OcotilloBDD** and synced here.

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
3. **Release notes:** PR 1's says the old command is gone. PR 2's says spreadsheets now need a `thing_type` column. PR 3's says the activity type `well inventory` is now `site inventory`, so anyone querying on the old term needs to update.
4. **CHANGELOG:** generated automatically from conventional commits; use the `thing-inventory` scope.

## Open item (blocks PR 4 onward, not PRs 1-3)
The per-type column list for the spreadsheet is still needed. Each field gets classified with the step-1 rules above (thing column, observation, history table or id link) before any migration is written.

## Verification
- `uv run pytest tests/test_domain_thing_types.py tests/test_thing_inventory.py tests/test_cli_commands.py`, and then the full `uv run pytest`.
- `uv run behave tests/features --tags="@backend and @production"`.
- `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head` again for each new migration.
- Manual run: `oco thing-inventory-csv tests/features/data/thing-inventory-valid-mixed.csv` against a local database. Then check `select thing_type, count(*) from thing group by 1` and confirm the new columns and observations are populated.
- Regression: after PR 2, importing the old valid well fixture (with the added `thing_type` column) produces exactly the same rows as on `staging`.
