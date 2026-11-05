# `NGWMN_Lithology`: per-interval lithology

`/ngwmn/lithology/{point_id}` reads the `NGWMN_Lithology` view. Each row is one
`thing_geologic_formation_association` interval on a public well.

## Where the lithology comes from

```
COALESCE(thing_geologic_formation_association.lithology,
         geologic_formation.lithology)
```

The interval's own `lithology` comes first. The formation's is a fallback for
intervals that have none. Rows where both are null are not exported.
`geologic_formation_id` may be null: an interval with a lithology but no
formation is still exported, as it was in the legacy view.

Before BDMS-1554 the view read only `geologic_formation.lithology`, which
allowed one rock type per formation. The legacy `view_NGWMN_Lithology` joined
each `Stratigraphy` row to `LU_Lithology`, so every interval had its own
lithology. Eight formations on staging carry more than one legacy code, for
example `211DKOT` with SNDS 55 and SDSL 4. The SDSL intervals now report
"Sandstone and shale" instead of the formation's "Sandstone".

Both `Lithology` and `TERM` carry the lexicon term. The legacy view put the
`LU_Lithology` abbreviation in `Lithology`. The endpoint reads only `TERM`,
so the XML output is unchanged.

## Backfill

The data migration `20261105_0001_backfill_stratigraphy_interval_lithology`
loads `NMA_Stratigraphy` into the associations. It covers both BDMS-1551, the
intervals that the transfer's 1000-well limit dropped, and BDMS-1554, the
per-interval lithology. The module docstring lists the rules. Run it after
`alembic upgrade head`:

```bash
oco data-migrations run 20261105_0001_backfill_stratigraphy_interval_lithology --dry-run
oco data-migrations run 20261105_0001_backfill_stratigraphy_interval_lithology
```

It never overwrites an interval lithology that is already set, and it leaves
`geologic_formation.lithology` alone.

## Row counts against the legacy view

`NMA_view_NGWMN_Lithology` holds the legacy view's rows. To list wells whose
counts differ:

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

The backfill leaves these known differences:

- **Duplicate intervals collapse.** A legacy row with the same well, formation,
  top and bottom as an earlier one is skipped, and the lowest legacy id wins.
- **Invalid depths are dropped.** A negative top, or a top at or below the
  bottom (unless both are zero), is skipped. These are the stratigraphy
  transfer's own rules.
- **Codes that don't map are dropped.** A code that is not in `LU_Lithology`,
  or whose term is not in `lexicon_term`, gives the interval no lithology. Such
  an interval is exported only if its formation has a lithology. The migration
  prints the unmapped codes.
- **Uncoded intervals inherit the formation's lithology.** An interval with a
  formation but no code is exported when the formation has a lithology. Today
  that is only `110ALVM` (Gravel) and `120SRVB` (Basalt), both set by the
  original transfer.
- **Only public wells are exported.** The view is gated on
  `thing.release_status = 'public'`.

The staging comparison has not been run yet. Run the query above after the
migration and record any other differences here.
