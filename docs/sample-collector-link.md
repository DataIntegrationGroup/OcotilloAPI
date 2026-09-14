# Who collected the sample — `sample.field_event_participant_id`

`Sample.field_event_participant_id` points at the one `FieldEventParticipant`
who took the measurement, out of the one to three people on the visit. It is the
only structured record of who collected a result: the importers deliberately
stopped writing staff names into `field_activity.notes`, so a null here means
the attribution is gone, not that it lives somewhere else.

Both CSV importers set it. The persistence is shared in
`services/field_event_participant_helper.py`; the naming and role rules that
need no database are in `domain/field_staff.py`.

## The two CSV formats

They carry the same staff columns, and the second is an alias of the first in
both:

| Purpose | Column | Alias |
| --- | --- | --- |
| Lead | `field_staff` | — |
| Other crew | `field_staff_2`, `field_staff_3` | — |
| Collector | `measuring_person` | `sampler` |

They differ in how strict the collector column is.

**Water levels** (`services/water_level_csv.py`) require `measuring_person`, and
`schemas/water_level_csv.py` rejects a value that is not one of the three staff
names. `resolve_measuring_participant` is the backstop: no match or an ambiguous
match raises, and the row fails.

**Well inventory** (`services/well_inventory_csv.py`) leaves it optional, and
operators leave it blank. It is empty in every row of
`tests/features/data/well-inventory-real-user-entered-data.csv`. So
`_resolve_sample_participant` applies the stricter rule only when there is a
value to apply it to:

- `measuring_person` set → `resolve_measuring_participant`, same as water
  levels. A name nobody on the crew matches fails the row, which rolls the whole
  well back rather than importing it with a silently unattributed sample.
- `measuring_person` blank → the `field_staff` lead. A visit that names staff
  has an identifiable collector even when the operator skipped the column, and
  when the row names one person the water level format's own rule says it can
  only be them.

## The gap: samples imported before this rule existed

Between the first well inventory import and 2026-09-14, the importer parsed
`sampler` into `WellInventoryRow` and then never read it. Every groundwater
level sample it created has a null link, and the name the operator typed was
written nowhere — not to the sample, not to the activity, not to an audit
column. On `ocotillo-staging` as of 2026-09-14 that is 201 samples:

| Imported | Samples | Events with 1 participant |
| --- | --- | --- |
| 2026-03-23 | 115 | 64 |
| 2026-08-24 | 78 | 58 |
| 2026-08-28 | 8 | 8 |

All three batches carry identical boilerplate notes
("Groundwater level measurement activity conducted during well inventory field
event.") and an empty `created_by_name`, so nothing in the row distinguishes one
visit from another.

### Why the database cannot repair itself

The participant list is the only thing left, and it is a derived artifact: it
was built from the same `field_staff` columns, so reading the collector back out
of it is circular for the 71 multi-participant events and merely probable for
the 130 single-participant ones. A migration that linked the lone participant
would be writing an inference into a column whose whole purpose is to record a
fact.

### What a backfill needs

The original CSV files, which the data owner still holds. Given those, a
`data_migrations/` migration (not Alembic — see the framework in
`data_migrations/`) can recover the real value:

1. Join each CSV row to its sample on `sample_name`, which
   `domain.samples.water_level_sample_name` builds deterministically from
   `well_name_point_id` and the measurement timestamp. The importer already uses
   that name for idempotency, so the join is exact.
2. Resolve `measuring_person` against the event's participants with
   `resolve_measuring_participant`, the same function the importer uses.
3. Where the CSV left `measuring_person` blank, apply the lead fallback above,
   so the backfilled rows and any re-import agree.
4. Skip anything that does not resolve, and report it. Leaving a null is
   recoverable; writing a guess is not.

Deliberately not done here: the files were not available when the importer was
fixed, and the fix is worth shipping without them.
