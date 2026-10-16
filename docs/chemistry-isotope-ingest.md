# Chemistry isotope ingest: the IsotopeResults tab

The AMP chemistry data-entry workbook carries four tabs. `ChemistrySampleInfo`
and `FieldParameters` load through the field-sheet ingest
(`docs/chemistry-field-sheet-ingest.md`). This ingest loads the
**`IsotopeResults`** tab into `NMA_MinorTraceChemistry`, where the legacy
isotope results already live.

- Ticket: BDMS-1461.
- Code:
  - `services/chemistry_isotopes.py`: map rows, find samples, write.
  - `services/chemistry_field_sheet.py`: read the workbook (shared with the
    field sheet).
  - `services/ingest_raw_zone.py`: archive what was read (shared).
  - `cli/cli.py`: `oco water-chemistry isotope-sync-sheet` and
    `oco water-chemistry isotope-upload`.
- Target table: `NMA_MinorTraceChemistry` (`db/nma_legacy.py`).
- Vocabulary: `LEGACY_ANALYTE_NAMES` and `LEGACY_UNITS` in
  `services/legacy_chemistry.py`.
- Step-by-step guide for whoever runs it:
  `docs/chemistry-isotope-ingest-walkthrough.md`.

## Why it is its own command

Isotope results are lab data. They come back weeks or months after the sample
is collected, usually well after its sample info and field parameters have
been entered, and from several labs:

| Lab | What it reports |
|---|---|
| `NMBGMR` | H2r, O18r, sometimes with uncertainties |
| `Beta Analytic` | radiocarbon age and pMC, C13r, H2r, O18r, and its own sample id |
| `University of Miami Tritium Laboratory` | tritium and its error |

The field-sheet commands load sample info and field parameters as soon as the
crew enters them, without waiting on any lab. This command loads the isotope
tab whenever its results arrive. The LIMS ingest can't take these either: it
reads one lab's LIMS export, a long table keyed by that lab's `SampleNumber`,
and records every result as `NMBGMR`.

---

## 1. Commands

```bash
# From Drive, dry run first: reads, validates, reports, writes nothing.
oco water-chemistry isotope-sync-sheet --dry-run

# Then for real (defaults to $CHEMISTRY_FIELD_SHEET_ID, the same workbook):
oco water-chemistry isotope-sync-sheet
```

```bash
# From a downloaded copy. A .csv export of the IsotopeResults tab works too.
oco water-chemistry isotope-upload --file ~/Downloads/Chemistry\&FieldParams_DataEntry.xlsx --dry-run
```

Check where a run will go with `oco db-info` first. Every report also names the
database under its headline.

**Load the sample info first.** A result attaches to a sample that is already
recorded (section 3). Run `sync-sheet` or `field-upload` before this command,
or results for new samples fail with "no sample ...".

`--failed-rows PATH` and `--loadable PATH` (`isotope-upload` only, one `.xlsx`)
work as they do for the field sheet: one dry run writes every failed row to a
workbook, and a copy of the export with those rows blanked, which loads the
rest while the failed rows are fixed. A failure fails the **whole sheet row**,
so the loadable copy holds back every result on that row.

**Empty rows**, with a sample and a lab but no results, don't stop the run,
but both reports account for them:

- The workbook lists them alongside the failed rows, in row order, with a
  reason starting `Empty, not a failure`, so the review covers them in one
  place. It is written when any row failed **or** is empty.
- The loadable copy blanks them along with the failed rows, so every row left
  in it is one that loads. It is still written only when a row failed;
  otherwise the export loads as it is.

The loadable copy shows what a dry run found would load, not what a real run
loaded. The record of a real run is its report and its raw-zone snapshot.

## 1a. The raw zone

As with the field sheet, every real run archives what it read before mapping,
then maps from the archive. Only the `IsotopeResults` tab is archived, under its
own dataset, `chemistry_isotope_results`, so a replay of one command never
picks up the other's snapshot.

```bash
oco water-chemistry isotope-sync-sheet --list-snapshots
oco water-chemistry isotope-sync-sheet --replay latest
```

`--no-raw` skips archiving. A dry run archives nothing.

---

## 2. What the tab maps to

Each row is one sample's results from one lab. The legacy table is long, so
each populated value cell becomes its own `NMA_MinorTraceChemistry` row.

Row-level columns:

| Spreadsheet heading | Goes to | Rule |
|---|---|---|
| `WellPointID` (or `SamplePointID`) | `chemistry_sample_info_id`, `nma_SamplePointID` | The lettered field sample ID (`RA-092A`), despite the heading. See section 3 |
| `AnalysisLab` | `analyses_agency` | Required; must be one of `ISOTOPE_LABS` |
| `AnalysisDate` | `analysis_date` | Optional; stored as a date |
| `ChemistryLabID` | `nma_WCLab_ID` on each result row | Optional; stored as text |

Measurements:

| Value | Qualifier -> `symbol` | Uncertainty -> `uncertainty` | `analyte` | `units` |
|---|---|---|---|---|
| `Age (years)` | `Age_Qualifier` | `Age_Uncertainty (years)` | `C14_years` | `yrs` |
| `pMC (pmc)` | `pMC_Qualifier` | `pMC_Uncertainty (pmc)` | `C14` | `pmc` |
| `C13r (pm)` | | | `C13r` | `pm` |
| `H2r (pm)` | | `H2r_Uncertainty (pm)` | `H2r` | `pm` |
| `O18r (pm)` | | `O18r_Uncertainty (pm)` | `O18r` | `pm` |
| `Tritium Units (TU)` | | `Tritium_error` | `3H` | `TU` |

- **Analytes** are the legacy `LU_MinorTraceAnalyte` codes, which is what the
  OGC views and `/chemistry/results` already read.
- **Units** are the legacy abbreviations, normalized here rather than taken
  from the heading: `pm` is per mil (‰), `pmc` percent modern carbon, `TU`
  tritium units, `yrs` years.
- **Headings** are matched with their parenthetical hint stripped, so
  rewording `H2r (pm)` to `H2r (permil)` doesn't drop the column.
- **Qualifiers** are `<` or `>`. Most results have none, and a blank qualifier
  is normal. A qualifier or uncertainty filled in beside a **blank** value is
  refused: it is usually a value typed into the wrong column.
- **Negative values** are real reported values (tritium below detection, say)
  and are stored as they are.
- **Lab ids are text.** Labs' own ids aren't numbers (`885-44878-1`,
  `260404-01`), so a cell holding only digits is written without the `.0`
  the spreadsheet adds (`765646.0` is stored as `765646`).

**The sample record is never written.** In particular a lab's id goes on its
own result rows, never on the sample's single `nma_WCLab_ID`. One sample can go
to several labs, each with its own id, and that one slot on the sample belongs
to the LIMS ingest: it is how LIMS recognizes a reload, and LIMS only adopts a
field sample whose slot is still empty. The legacy audit columns
(`nma_GlobalID`, `nma_chemistry_sample_info_uuid`) hold NM_Aquifer's values
only and stay empty on new rows.

---

## 3. How a result finds its sample

The tie is the **field sample ID**, the same key the field-sheet and LIMS
ingests match on.

1. The row's `WellPointID` cell holds the field sample ID, `RA-092A`. An ID
   with no letter (`WL-0231`) fails the row: it names the well, not one of the
   well's samples.
2. The well part (`RA-092`) is matched to `Thing.name`, and the sample is the
   `NMA_Chemistry_SampleInfo` on that well named with the full ID. Exactly one
   must exist. None found fails the row; two found fails it as ambiguous.
3. Every result from the row takes that sample's `id` as
   `chemistry_sample_info_id`, the foreign key every chemistry read path joins
   through. That is how a result gets its well and collection date.

**This ingest never creates a sample.** The tab has no collection date, and
both other ingests check a sample's date when they match it, so a sample made
here without one would block the field sheet and the LIMS ingest from ever
matching it. The sample comes from `ChemistrySampleInfo`.

An `AnalysisDate` earlier than the sample's collection date fails the row:
either the date is a typo, or the ID names the wrong sample.

### Two labs, one analyte

A result's identity is its **sample, analyte and lab**. When Beta Analytic and
NMBGMR both report H2r for a sample, both are stored, told apart by
`analyses_agency`. Nothing is discarded.

### Re-runs and re-analyses

- A result already stored for that sample, analyte and lab, with the same
  value, qualifier, uncertainty and units, is **skipped** and listed. Re-running
  a sheet loads nothing twice.
- One whose value, qualifier, uncertainty or units **differ** fails its row,
  listing each difference, and the run aborts. The stored value is never
  overwritten from the sheet. The new value may be a re-analysis the lab was
  asked for, or a typo, and a person decides which stands. A stored result is
  corrected by hand.
- The same result typed twice in the sheet loads once, with a warning. Two
  **different** results for one sample, analyte and lab fail both rows, since
  nothing says which is right.

---

## 4. Failure semantics

Any failed row **aborts the whole import and nothing is written**, the same rule
as the other chemistry ingests. One pass reports every failed row.

| Reported cause | Meaning | Action |
|---|---|---|
| `has no sample letter` | The ID is the well (`WL-0231`). | Use the field sample ID from the chain of custody (`WL-0231A`). |
| `no matching Thing (well) ...` | The well isn't in Ocotillo. | Transfer or create the well first. |
| `no sample RA-092A -- load its ChemistrySampleInfo row ...` | The sample isn't recorded yet. | Run `sync-sheet` or `field-upload` first, or correct the ID. |
| `has N samples named ...; cannot tell which` | Two records share the ID on this well. | Reconcile the duplicate samples by hand. |
| `Missing AnalysisLab` / `is not a known lab` | The lab is blank or not in `ISOTOPE_LABS`. | Fix the spelling, or have engineering add the lab. |
| `... is not a number` | A value or uncertainty holds text, or a qualifier typed into the value (`<0.44`). | Put the qualifier in its own column, or fix the cell. |
| `... is not one of <, >` | The qualifier is something else. | Use `<` or `>`. |
| `... filled but ... blank` | A qualifier or uncertainty with no value beside it. | Fill the value, or clear the stray cell. |
| `AnalysisDate ... is not a recognizable date` | Not a date. | Fix the cell. |
| `was collected on ..., but ... analysed it on ...` | The analysis predates collection. | Correct whichever date is wrong, or the ID. |
| `... is also on row N with a different result` | Two rows give one sample, analyte and lab different results. | Delete the wrong row. |
| `... is already stored for ... and differs: ...` | A stored result changed. | Review with the lab; correct the stored result by hand if the new one stands. |
| `... is stored N times for ...` | The table already holds two such results. | Reconcile them by hand. |

A run that reports only **warnings** (a repeated row, an undated sample, a
column it doesn't read), **skips**, or **empty rows** (a row with a lab but no
results) succeeds.

---

## 5. Known gaps

- **The OGC map layer shows one lab.** `ogc_minor_chemistry_wells` keeps one
  value per well and analyte: the latest by analysis date, falling back to the
  collection date. Where two labs report H2r, only one appears there.
  `/chemistry/results` shows both.
- **No tritium column on that layer.** `ogc_minor_chemistry_wells` has columns
  for H2r, O18r, C13r, C14 and C14 age, but not `3H`.
- **The materialized views need a refresh** before new results show on the OGC
  layers.
- **Legacy rows without a lab** can't be matched by lab. A sheet result for an
  analyte that a legacy row with a blank `analyses_agency` already holds loads
  beside it.
- **The `WellPointID` heading is misleading.** It holds the field sample ID.
  Renaming it `SamplePointID` in the template would say what it holds; both
  headings are accepted.
- **Lab names are a fixed list.** A new lab fails until it is added to
  `ISOTOPE_LABS`.
- **New measurement columns don't load.** The ingest reads only the columns
  in `ISOTOPE_COLUMNS`. A column added to the tab for a new measurement loads
  nothing until it is added there. The report names any column it doesn't
  read, under WARNINGS, and the run still succeeds.
- **`GenChemResults` still has no ingest path.**
