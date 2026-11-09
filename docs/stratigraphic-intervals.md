# Stratigraphic intervals and `NGWMN_Lithology`

## The model

`stratigraphic_interval` is a well's stratigraphic log. Each row is one depth
interval, and it mirrors a legacy NM_Aquifer `Stratigraphy` row:

| Column | Legacy `Stratigraphy` | Notes |
| --- | --- | --- |
| `thing_id` | `PointID` | |
| `top_depth`, `bottom_depth` | `StratTop`, `StratBottom` | feet below ground surface |
| `geologic_formation_id` | `UnitIdentifier` | nullable; null when the code names no formation |
| `lithology` | `Lithology` via `LU_Lithology` | lexicon term |
| `lithologic_modifier` | `LithologicModifier` | free text |
| `contributing_unit` | `ContributingUnit` | boolean |
| `source` | `StratSource` | free text; published as NGWMN `StratSource` |
| notes (`Notes`, type `General`) | `StratNotes` | |
| `nma_pk_stratigraphy` | `GlobalID` | |

Until BDMS-1554 the table was `thing_geologic_formation_association`. It held
only the depths and the formation, so it could not record an interval with a
lithology but no formation. It also could not record lithology varying within
a formation. Revision `7480e4ee69dc` renamed it and kept its rows and ids.

## Where `NGWMN_Lithology` gets its lithology

```
stratigraphic_interval.lithology
```

The view publishes only the lithology logged for the interval. It does not
fall back to `geologic_formation.lithology`: an interval with no logged code
is not exported, even when its formation has a lithology. The formation
values were set by the transfer from the first code it saw, so they do not
represent the formation's uncoded intervals. An interval with no formation is
still exported when it has a lithology, as it was in the legacy view.

Before this change the view read only `geologic_formation.lithology`, which
allows one rock type per formation. Eight formations on staging carry more
than one legacy code. For example, `211DKOT` has SNDS 55 and SDSL 4; its SDSL
intervals now report "Sandstone and shale".

Both `Lithology` and `TERM` carry the lexicon term. The legacy view put the
`LU_Lithology` abbreviation in `Lithology`. The endpoint reads only `TERM`.

## Backfill

The data migration `20261105_0001_backfill_stratigraphic_intervals` loads
`NMA_Stratigraphy` into `stratigraphic_interval`. It covers two gaps:

- BDMS-1551: the intervals that the transfer's 1000-well limit dropped.
- BDMS-1554: the interval fields the transfer never carried.

The 993 transferred intervals are adopted rather than duplicated. An adopted
interval's empty fields are filled and its legacy `GlobalID` is recorded. A
value that is already set is never overwritten. The module docstring lists
every rule. Run it after `alembic upgrade head`:

```bash
oco data-migrations run 20261105_0001_backfill_stratigraphic_intervals --dry-run
oco data-migrations run 20261105_0001_backfill_stratigraphic_intervals
```

The dry run reports these values, which are left unconverted:

- lithology codes not in `LU_Lithology`;
- `ContributingUnit` values other than Y/N and their variants;
- `UnitIdentifier` codes that name no formation.

## Row counts against the legacy view

`NMA_view_NGWMN_Lithology` holds the legacy view's rows. This query lists the
wells whose row counts differ:

```sql
WITH legacy AS (
    SELECT "PointID", count(*) AS n FROM "NMA_view_NGWMN_Lithology" GROUP BY 1
), current AS (
    SELECT "PointID", count(*) AS n FROM "NGWMN_Lithology" GROUP BY 1
)
SELECT "PointID", legacy.n AS legacy_rows, current.n AS current_rows
FROM legacy FULL JOIN current USING ("PointID")
WHERE legacy.n IS DISTINCT FROM current.n
ORDER BY 1;
```

These are the known differences:

- **Invalid depths are dropped.** A legacy interval with a negative top, or a
  top at or below its bottom (unless both are zero), is not migrated. These
  are the transfer's own rules.
- **Some lithology codes don't map.** When a code is not in `LU_Lithology`, or
  its term is not in `lexicon_term`, the interval gets no lithology and is not
  exported.
- **Uncoded intervals are not exported.** An interval with no logged code is
  left out, whatever its formation's lithology. On staging this excludes 808
  uncoded `110ALVM` intervals on public wells, which a fallback would have
  published as Gravel, and one `120SRVB` interval (Basalt).
- **Only public wells are exported.** The view is gated on
  `thing.release_status = 'public'`.

The staging comparison has not been run yet. Run the query above after the
migration, and record any other differences here.
