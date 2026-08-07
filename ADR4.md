# ADR4: A Domain Layer for Import Rules

## Status

Accepted, partially applied. The `domain/` package exists and the two CSV
importers use it. The rest of `services/` is untouched and stays that way until
someone has a reason to open those files.

## Context

`services/` is documented as "business logic and database interactions", and it
does both in the same functions. The clearest example is
`services/well_inventory_csv.py`: a single call to `_add_csv_row` mixed unit
conversion, cross-column validation, note formatting, and `session.add(...)`.

Three consequences:

1. **Rules could not be tested without a database.** Verifying that a
   measuring point height conflict is rejected meant standing up PostGIS,
   building a `Thing`, and running an import.
2. **Rules drifted between callers.** The groundwater-level sample name was
   written out three times across two files. The foot/meter conversion was
   duplicated until BDMS-284 consolidated it. Field staff contact lookup had
   two different WHERE clauses, one of which was wrong (see below).
3. **There was no obvious home for a new rule.** `services/util.py` had quietly
   become one — it holds the unit conversions — but nothing named it as such, so
   the next rule went wherever it was first needed.

## Decision

Add a `domain/` package holding business rules as plain functions over plain
values. Modules there import nothing from `api/`, `db/`, `schemas/`, or
`services/`, and no `fastapi`, `sqlalchemy`, `pydantic`, or `httpx`.

`services/` keeps its orchestration role: load rows, call the rule, persist the
result, translate errors into the transport's shape.

Domain errors subclass `ValueError`, because the importers already treat a
`ValueError` raised while handling a row as a per-row validation failure rather
than an aborted run.

### What we did *not* decide

This is not an adoption of hexagonal architecture or DDD. There are no entities,
repositories, aggregates, or mapping layers, and `services/` still talks to
SQLAlchemy models directly. The cost of a full restructure is not justified at
this size, and a half-applied one — domain objects that quietly hold a session —
is worse than none.

Extraction is opportunistic: when you open an importer to change a rule, move
the rule. There is no migration plan for the remaining service modules.

## Consequences

**Good.** The extracted rules have 67 tests that need no database and run in
seconds. `services/util.py` no longer has to be imported to convert feet to
meters, which previously dragged in `httpx`, `pyproj`, and SQLAlchemy.

**Cost.** One more package, and a rule now lives one call away from where it is
used. For a rule with a single caller this is pure overhead; extract when a rule
is shared, subtle, or expensive to test in place, not by default.

**Watch for.** `services/util.py` re-exports the unit conversions for backwards
compatibility. That re-export is a transition aid, not a pattern — new code
should import from `domain.units`.

## Notes

Aligning the two field-staff contact lookups surfaced a real defect.
`services/water_level_csv.py` looked contacts up on `(name, organization)` with a
comment explaining that `Contact` enforces uniqueness on exactly that pair, while
`services/well_inventory_csv.py` also filtered on `contact_type`. The second form
misses an existing contact created with a different type and then fails on the
duplicate insert. Both now use the `(name, organization)` key.

Two remaining copies of the enum-unwrapping idiom in
`services/well_inventory_csv.py` (`groundwater_level_reason`, `nma_data_quality`)
were left alone: each treats a falsy non-enum value slightly differently from
`domain.values.enum_value`, and reconciling them is a behavior change that wants
its own ticket.
