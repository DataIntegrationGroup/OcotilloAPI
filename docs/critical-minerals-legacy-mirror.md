# Critical minerals legacy mirror (`CM_legacy`)

Staging mirror of the Earth MRI critical-minerals chemistry workbook
(`McLemoreMasterChem`, compiled by V.T. McLemore et al., NMBGMR) into the
`CM_*` tables. Phase 1 only: the workbook lands in PostgreSQL unchanged. The
transform into the Ocotillo data model (Location / Thing / FieldEvent /
FieldActivity / Sample / Observation) is not designed yet.

Code: [`db/cm_legacy.py`](../db/cm_legacy.py),
[`services/cm_legacy_mirror.py`](../services/cm_legacy_mirror.py),
migration `d4e5f6a7b8c9`.

## Loading

```bash
oco load-critical-minerals-workbook --file /path/to/McLemoreMasterChem_9-18-25.xlsx
```

The load is idempotent per sheet: each sheet's rows are deleted and re-inserted,
so a revised workbook can be reloaded without duplicating rows or wiping the
rest of the mirror. The command wraps the whole load in one transaction — a
failure part way through leaves the mirror untouched.

Row counts from the 2025-09-17 revision:

| Sheet | Mirror table | Rows |
|---|---|---|
| ChemicalData | `CM_ChemicalData` (`source_sheet='ChemicalData'`) | 4867 |
| GIS | `CM_ChemicalData` (`source_sheet='GIS'`) | 4848 |
| QAQC | `CM_ChemicalData` (`source_sheet='QAQC'`) | 8 |
| DetectionLimits | `CM_DetectionLimits` | 61 |
| References | `CM_References` | 81 |
| MineralSystems | `CM_MineralSystems` | 169 |
| world | `CM_WorldComparisons` | 7 |
| world_ref | `CM_WorldReferences` | 4 |
| General Information / MetaData / DefinitionOfFields | `CM_WorkbookMetadata` | 24 / 9 / 22 |

## Three sheets, one table

`ChemicalData`, `GIS` and `QAQC` share a column set, so they mirror into one
table keyed by a `source_sheet` discriminator:

- `ChemicalData` and `GIS` are byte-identical in header text and order — 118
  columns each. Only the layout differs: `ChemicalData` has a title banner
  (row 1), header (row 2) and units row (row 3); `GIS` has a single header row.
- `QAQC` is those columns minus `MapSymbol`, `Pd` and `Pt`, with
  `latitude`/`longitude` capitalized. The loader matches headers
  case-insensitively; the three absent columns are NULL for those rows
  (`QAQC_MISSING_COLUMNS`).

## Reconciliation is deferred

**`GIS` is not `ChemicalData` plus location data, and it is not a clean subset.**
It is a stale, hand-maintained fork. It carries the same mixed coordinate
systems (WGS84 / NAD27 / NAD83 / blank) and the same ~876 rows with no
latitude, so it adds no location information at all.

Every `GIS` sample name exists in `ChemicalData`, but 1704 of the 4848 shared
rows disagree cell-for-cell, in both directions:

| Direction | Columns |
|---|---|
| `GIS` has values `ChemicalData` lacks | 533 `Chem Lab File No.`, 485 `Laboratory`, 85 `FeO`, 85 `Fe2O3` |
| `ChemicalData` has values `GIS` lacks | 633 `Total`, 184 `Area`, 11 `TREE`, 4 `Date analyzed` |
| Outright disagreement | 16 rows on `Area` (`ZuniMountains` vs `Zuni`) |
| Broken formulas | 12 `#VALUE!` `Total`s in `GIS`, 1 in `ChemicalData` |

`ChemicalData` also holds 18 sample rows appended after `GIS` was last synced
(`BP*`, `CR1`, `JP*`, `SA*`, `SL*`).

Neither sheet is authoritative, so both are mirrored in full and the merge is
left to a later phase, **to be ruled on per column by V.T. McLemore**. Until
then:

- do not treat any single `source_sheet` as complete;
- do not de-duplicate across sheets in the mirror;
- a query that reads only `source_sheet='ChemicalData'` silently drops 533 lab
  file numbers, 485 lab names and 170 FeO/Fe2O3 values.

The loader emits a warning whenever the `ChemicalData` and `GIS` row counts
differ, as a standing reminder that the drift has not been resolved.

## The reconciliation workbook

`scripts/cm_reconciliation_report.py` turns everything above into a decision
workbook for whoever owns the source data:

```bash
python -m scripts.cm_reconciliation_report \
  --workbook "/path/to/McLemoreMasterChem_9-18-25.xlsx" \
  --out CM_reconciliation.xlsx
```

Eight sheets. Every yellow column is blank on purpose and carries a dropdown;
nothing in the workbook is decided by the script.

| Sheet | Rows (2025-09-17 revision) | Purpose |
|---|---|---|
| `README` | — | what it is, who fills it in, what happens next |
| `ColumnDecisions` | 8 | one row per disagreeing column, with a suggested starting point |
| `CellDifferences` | 2123 | every disagreeing cell, both values side by side |
| `RowsOnlyInOneSheet` | 19 | the 18 Pearce (2020) samples appended after the last GIS sync, plus the NOTE row |
| `IntegritySummary` | 13 | integrity findings by issue, worst first |
| `IntegrityDetail` | 4276 | the individual rows behind each finding |
| `DetectionLimitSpread` | 64 | analytes reported against many different `<` limits |
| `DuplicateSampleNames` | 258 | names shared by two or more rows |

### Integrity findings

Independent of the sheet-to-sheet drift, from `ChemicalData` alone:

| Rows | Finding |
|---|---|
| 1594 | date is year-only or free text, not a full date |
| 880 | no coordinates |
| 724 | value impossible for its declared unit — e.g. `F` = 27700 in a column the units row declares as `%`, plus 68 in `P` and 65 in `Mn` |
| 300 | non-numeric analyte text: `bd`, `nd`, `tr`, `nr`, `n/a`, `----`, `>2%` |
| 259 | `Au` censored below 0.01 in a ppb column, i.e. some rows are ppm |
| 224 | `Total` outside 95–105% |
| 159 | `Total` differs from the sum of SiO2–LOI by more than 5 |
| 81 + 8 | latitude / longitude outside the New Mexico bounding box |
| 23 | analyzed before collected |
| 21 | coordinates with no declared datum (NAD27 vs WGS84 is ~100 m here) |
| 2 | positive longitude (missing minus sign) |
| 1 | `Total` is `#VALUE!` |

`Total` is deliberately exempt from the unit check: it is a sum, so exceeding
100 is not by itself a unit error. It gets the two dedicated checks above
instead. Only `ChemicalData` is integrity-checked — running the same checks over
`GIS` would double every finding without adding information, since the
sheet-level differences are already enumerated.

## Everything is a string

Analyte columns hold censored values as text (`<0.1`, `<10`, `<0.06` — 1154 of
them in `Au` alone), Excel error text (`#VALUE!`), and blanks; date columns mix
real dates with free text. Storing every column as `String` keeps the mirror
loadable without dropping cells. Parsing value-plus-qualifier (cross-checked
against `CM_DetectionLimits`), casting dates, and reprojecting coordinates are
all transform work.

Cell rendering rules (`_cell_to_text`): dates become ISO-8601 rather than Excel
serials, numbers keep Python's round-trippable `repr`, blank and whitespace-only
cells become NULL rather than `''`, and everything else passes through
stripped.

## Column naming

Sheet headers are spreadsheet labels, not SQL identifiers (`Chem Lab File No.`,
`Depth/legnth (ft)`, `H2O+`), so unlike the NMA/NMW mirrors the source name
cannot be reused verbatim. Names are derived mechanically: snake_case,
non-alphanumerics collapsed to `_`, `+`→`_plus`, `*`→`_star`, `%`→`_pct`.

Analyte columns carry the unit the workbook declares for them in its units row
(`sio2_pct`, `au_ppb`, `as_ppm`), which also keeps `As` and `In` from colliding
with the Python and SQL keywords `as` and `in`. The source typo in
`Depth/legnth (ft)` is preserved as `depth_legnth_ft` so the mapping back to the
sheet stays mechanical.

`SOURCE_HEADER_BY_COLUMN` records the exact source header for every column and
`ANALYTE_UNITS` records the declared unit for every analyte, so the units row is
not lost.

## Row identity

Sample names are **not** unique in the source (`S1`, `S10`, `S100` and ~340
others repeat), so rows are keyed on `(source_sheet, source_row)` where
`source_row` is the 1-based Excel row number. Every mirror row is traceable to a
cell range in the delivered workbook.

## Known junk in the data range

The first data row of `ChemicalData` is not a sample: its `SAMPLE` cell holds
"NOTE: SEE THE ORIGINAL CITATION FOR INFORMATION ON METHODS OF ANALYSES,
QA/QC, DETECTION LIMITS, ETC." It is mirrored like any other row and must be
excluded by the transform.

`CM_MineralSystems` is mirrored positionally, table notes included: the sheet
puts the systems table in columns 1–6 and three unrelated lists of critical
minerals by USGS phase in columns 7–9, and several rows are footnotes rather
than systems.

Also unresolved in the source data: `F` is declared as `%` in the units row but
several rows report values in the tens of thousands (Gal1 `f_pct` = 27700),
i.e. ppm. The mirror carries the value as given; the transform must decide.

## Layout is asserted, not guessed

Each sheet declares which row holds its header, and the load fails loudly if
that row does not contain the expected label, or if a header appears that has no
mirror column. A revised workbook that moves a header row, renames a column or
adds one must be looked at by a human — and given a migration — before it lands
in the mirror.
