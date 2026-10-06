# Chemistry field-sheet ingest — sample info and field parameters

The lab half of chemistry ingestion arrives as a LIMS workbook
(`docs/chemistry-ingestion-runbook.md`). This is the **field** half: the AMP
data-entry spreadsheet the sampling crew fills in, whose `ChemistrySampleInfo`
and `FieldParameters` tabs become `NMA_Chemistry_SampleInfo` and
`NMA_FieldParameters` rows.

- Code:
  - `services/chemistry_field_sheet.py` — read the spreadsheet (Google Sheet,
    `.xlsx` in Drive, or a local `.csv`/`.xlsx` export).
  - `services/ingest_raw_zone.py` — archive what was read (dlt → partitioned
    parquet), and read a snapshot back for replay.
  - `services/chemistry_field_params.py` — map rows, match samples, write.
  - `cli/cli.py` — `oco water-chemistry sync-sheet` and
    `oco water-chemistry field-upload`.
- Target tables: `NMA_Chemistry_SampleInfo`, `NMA_FieldParameters`
  (`db/nma_legacy.py`).

The same workbook also carries `GenChemResults` and `IsotopeResults`. **This
ingest does not read them** — lab results are the LIMS ingest's business.

---

## 1. Commands

New to this? `docs/chemistry-field-sheet-ingest-walkthrough.md` walks through a
first load step by step, from installing the tools to checking the result.

```bash
# From Drive, dry run first: reads, validates, reports, writes nothing.
oco water-chemistry sync-sheet --dry-run

# Then for real (defaults to $CHEMISTRY_FIELD_SHEET_ID):
oco water-chemistry sync-sheet
oco water-chemistry sync-sheet --sheet-id 'https://docs.google.com/spreadsheets/d/<id>/edit'
```

```bash
# From a downloaded copy — for an engineer without Drive access to the sheet.
oco water-chemistry field-upload --file ~/Downloads/Chemistry\&FieldParams_DataEntry.xlsx --dry-run

# A CSV export holds a single tab, so pass one --file per tab.
oco water-chemistry field-upload --file info.csv --file params.csv
```

Prerequisites are the LIMS ingest's (`uv sync --locked --group cli`, database
reachable), plus read access to the spreadsheet for whatever identity the CLI
runs as — application-default credentials locally, the `GCS_SERVICE_ACCOUNT_KEY`
service account in production. Set `CHEMISTRY_FIELD_SHEET_ID` to the sheet id or
URL, and a raw zone (next section).

There is **no manifest**. The LIMS sync needs one because a workbook is a
one-shot batch; this spreadsheet is a living document that grows week over
week, so it is re-read in full every run and idempotency comes from the
database instead (section 3).

### Finding and setting aside failed rows

Any failed row stops the whole run (section 4), and one dry run reports every
failed row. Two options write that out as files, so the rows can be fixed and
the rest loaded in the meantime:

```bash
oco water-chemistry field-upload --file sheet.xlsx --dry-run \
    --failed-rows sheet_failed_rows.xlsx --loadable sheet_loadable.xlsx
```

- `--failed-rows PATH` writes the **failed row workbook**: every row that
  stopped the run, on a sheet per tab, with its row number in the Google Sheet,
  why it failed, and the cells it held. `sync-sheet` takes it too.
- `--loadable PATH` (`field-upload` only, one `.xlsx`) writes the **loadable
  copy**: the export with every failed row blanked. Rows are blanked, not
  deleted, so every row keeps its number. A dry run on the copy should pass,
  and loading it loads everything else.

Both are written only when a row fails, and neither changes what reaches the
database. The cycle is:

1. Dry-run with both options.
2. Load the loadable copy, if the rest shouldn't wait.
3. Fix the failed rows **in the Google Sheet**, using the failed row workbook.
4. Download a fresh copy, then dry-run and load it. Rows loaded in step 2 are
   matched and skipped, and only the fixed rows are new.

---

## 1a. The raw zone (dlt)

Every run **archives what it read before it maps anything, and then maps from
the archive**. What loaded is provably what was kept.

```bash
oco water-chemistry sync-sheet --list-snapshots     # what is archived
oco water-chemistry sync-sheet --replay <load_id>   # load a snapshot again
oco water-chemistry sync-sheet --replay latest
```

- **Where**: `INGESTION_GCS_BUCKET` (the raw-zone bucket the Dagster+ ingestion
  uses — *never* `GCS_BUCKET_NAME`, the API's upload bucket), or
  `OCO_RAW_ZONE_DIR` for a local directory, or `--raw-url` per run. None of
  these is defaulted: **the ingest refuses to run rather than write nowhere
  useful.** Pass `--no-raw` to ingest without archiving.
- **Layout**: `{tab}/year=/month=/day=/{load_id}.{file_id}.parquet`, matching
  the Dagster+ raw zone, so a snapshot is found by prefix without reading files.
- **What a row holds**: `{tab, row_number, header_json, cells_json}`. Headings
  are archived exactly as typed rather than as one column each — a crew adding
  "DO (mg/L)" to a tab is an ordinary edit, and it should not become a schema
  migration in the archive. Date cells are archived as ISO text.
- **A dry run archives nothing**, the same as it writes no database rows.
- **A failed run still archives.** The abort happens during mapping, after the
  snapshot is written — which is the point: the record of what arrived is what
  you need in order to fix it.

This is dlt doing extraction, parquet and load packages. Mapping, validation and
the writes into Ocotillo's tables stay in the service layer: the destination is
an FK-heavy relational schema owned by alembic, not a warehouse for dlt to
evolve. `dlt[filesystem,gs]`, `pyarrow` and `gcsfs` are in the `cli` dependency
group, so the API image is unaffected.

---

## 2. What the tabs map to

`ChemistrySampleInfo` — one row per sample:

| Spreadsheet heading | Goes to |
|---|---|
| `WellPointID` | resolved to `Thing.name`; the sample's well |
| `SamplePointID` | the field sample ID (`RA-116A`) — **required, with the crew's letter**; it is the match key, and is checked against the well |
| `CollectionDate` | `CollectionDate` — **required**; a match must be dated the same day |
| `AnalysisAgency` | `AnalysesAgency` (defaults to `NMBGMR`) |
| `SampleType (SD)` | `SampleType` |
| `CollectionMethod (F = faucet)` | `CollectionMethod`, as the legacy code (see below) |
| `CollectedBy (GR = grab??)` | `CollectedBy` (5 characters; longer is rejected) |
| `Data Source` | `DataSource` |
| `Sample Notes` | `SampleNotes` |
| `Staff` | prepended to `SampleNotes` as `Staff: ...` |

Headings are matched with any parenthetical hint stripped, so rewording
"`SampleType (SD)`" to "`SampleType (SD/GW)`" does not silently drop the column.

`CollectionMethod` takes either the method written out or NM_Aquifer's
one-letter `LU_CollectionMethod` code. Prefer the words: `F` and `H` are both
faucets, and nobody reading the letter alone can tell the well head from the
house. Case and spacing do not matter. Either way the ingest stores the code,
because that is what every legacy `NMA_Chemistry_SampleInfo` row holds, so a
sheet row matched to a legacy row compares equal instead of being reported as a
disagreement:

| Meaning | Code (also accepted, and what is stored) |
|---|---|
| `Bailer` | `B` |
| `Faucet at well head` | `F` |
| `Grab sample` | `G` |
| `Faucet or outlet at house` | `H` |
| `Pump` | `P` |
| `Thief sampler` | `T` |
| `Unknown` | `U` |

Anything outside the table is refused. The vocabulary is `COLLECTION_METHODS`
in `services/chemistry_field_params.py`.

`Staff` has no column of its own in the legacy schema. Folding it into the notes
keeps the only record of who was on site; a dedicated column would be a schema
change to a legacy mirror table.

`FieldParameters` — one row per sample, **one column per measurement**. The
legacy table is long, so each populated cell becomes its own row:

| Spreadsheet column | `FieldParameter` | `Units` |
|---|---|---|
| `pHf` | `pHf` | `pH` |
| `T (C)` | `T` | `°C` |
| `CF (uS/cm)` | `CF` | `µS/cm` |
| `DO (mg/L)` | `DO` | `mg/L` |
| `ORP (mV)` | `ORP` | `mV` |
| `Discharge rate (gpm)` | `Q` | `gpm` |

Units are normalized here rather than taken from the heading, so field rows read
the same as the lab rows the LIMS ingest writes. The symbols are the legacy AMP
vocabulary in `services/legacy_chemistry.py` — **except `Q`**, which NM_Aquifer
has no symbol for. Discharge is recorded by the crew and would otherwise be
dropped, so this ingest introduces the symbol. Rename it here and in
`FIELD_PARAMETER_COLUMNS` if AMP settles on something else.

The `Time` column is the reading time, which `NMA_FieldParameters` has no column
for; it is kept in `Notes` as `Measured <ISO timestamp>`. It is **required**,
date included: it's how the ingest checks that a readings row reached the right
visit (section 3).

---

## 3. How samples are matched

A field sample and its lab results are **one sample record**, so the sheet must
not create a second `NMA_Chemistry_SampleInfo` row beside the one the LIMS
ingest made. They're matched on the **field sample ID**, the `SamplePointID`:
the well plus the crew's letter (`WL-0264B`). The lab copies it from the chain
of custody, so it's the one name both halves share. **Different letters are
different field samples**, so nothing is ever matched on the well and date
alone.

Each `ChemistrySampleInfo` row:

1. **Must have a lettered `SamplePointID`.** A blank one, or one with no letter
   (`WL-0264`), aborts the run. So does the same `SamplePointID` on rows dated
   on different days: every one of those rows is reported, and none loads,
   since nothing says which date is right.
2. **Matches the record already named with it**, if that record is dated on the
   same day. The name is what tells apart two samples taken at one well on one
   day: a duplicate minutes apart, or a split at the same time.
3. **Aborts the run** if a record with that name is from another day, or has
   no date. The crew reused a letter, and the error lists the letters the well
   already uses so a free one can be picked.
4. **Creates a record** named with its `SamplePointID` when none exists.

On a match, the sheet **fills blank columns only**. A value already in the
database is kept and the disagreement is reported as a warning — a field sheet
is re-typed and re-sent, so it is not authoritative over what is stored.

Field parameters attach to the sample named by their `SamplePointID`, whether it
was created by this run, by an earlier run, or by the LIMS ingest. A parameter
already recorded for that sample is skipped, so **re-running the same sheet
loads nothing twice**. A `FieldParameters` row whose `Time` falls on a
different calendar day from its sample's collection date aborts the run: either
the name reached the wrong visit, or one of the two dates is a typo. Only the
day is compared, so a reading taken minutes after collection loads normally.

### Either ingest can go first

Both ingests match on the field sample ID, so a field sample and its lab results
end up as one record whichever lands first:

| Order | Result |
|---|---|
| LIMS, then field sheet | LIMS creates the record under the `SamplePointID` from the chain of custody. The sheet's row with that ID matches it and fills blanks, and its field parameters take the record's `WCLab_ID`. |
| Field sheet, then LIMS | LIMS **adopts** the sheet's record of that name: it stamps the `WCLab_ID` onto it, backfills that id on the field parameters, and attaches the lab results. The sheet's collection time is kept. |

Field-first is the usual order, since crews have field data well before lab
results come back. For each lab sample (every workbook row sharing one
`SampleNumber`, the LabSampleID):

- **Its rows must agree, and be complete.** One lettered `SamplePointID` and
  one `SampleDate` (the collection date). No letter, a blank `SampleDate`, two
  letters, or dates on two days abort the workbook.
- **One LabSampleID belongs to one field sample.** Two lab samples in the
  workbook naming the same field sample abort it.
- **The record named with its `SamplePointID` takes the results** if it has no
  `WCLab_ID` yet and is dated on the `SampleDate`. If it already has a lab id,
  is from another day, or has no date, the workbook **aborts** and the error
  says which. If no record has that name yet, one is created under it.
- **A LabSampleID already loaded** is skipped if the workbook's copy is an exact
  repeat, so re-running a file is harmless. If anything differs (a corrected
  value, an added analyte, or another `SamplePointID`), the workbook aborts and
  lists the differences for review.

Adoptions show up in the `bulk-upload` report under **ADOPTED**, and in
`adopted_samples` in the result payload.

---

## 4. Failure semantics

Any data-quality problem **aborts the whole import and nothing is written** —
the same rule as the LIMS ingest, so a spreadsheet is never half loaded. Every
failing row is reported in one pass: a row that fails is set aside, and the
rest still go through every check. A `FieldParameters` row whose
`ChemistrySampleInfo` row failed is reported as depending on it, rather than
with a knock-on error. The result also carries the failures as data
(`failed_rows`: tab, row, `SamplePointID`, reason, and the row it depends on),
which is what `--failed-rows` writes out.

What aborts a run:

| Reported cause | Meaning | Action |
|---|---|---|
| `Missing CollectionDate` | The row has no date to match on. | Fill the date in the spreadsheet. |
| `CollectionDate ... is not a recognizable date` | Not ISO, US-style, or a real date cell. | Fix the cell. |
| `PointID 'WL-####' has no well identifier assigned yet` | A real sample whose well has not been given an id. | Assign the PointID, then re-run. |
| `WellPointID ...: no matching Thing (well) found` | The well is not in Ocotillo. Reported on each of its rows. | Transfer or create the well first. |
| `its ChemistrySampleInfo row N failed: ...` | A `FieldParameters` row whose sample-info row failed; the reason is that row's. | Fix row N; this row then loads with it. |
| `SamplePointID ... does not belong to well ...` | The lettered point's base is a different well. | Fix one of the two cells. |
| `CollectionMethod ... is not a known collection method` | Neither one of the seven `LU_CollectionMethod` meanings nor its code. | Use one from the list in section 2. |
| `CollectedBy ... is longer than 5 characters` | The legacy column holds a 5-character code. | Use the code, not the name — names belong in `Staff`. |
| `non-numeric reading(s)` | A field parameter cell holds text. | Blank it or fix the number. |
| `Missing Time` | A `FieldParameters` row has no reading time. | Fill in the date and time the readings were taken. |
| `Time ... is not a recognizable date and time` | The `Time` cell isn't a date and time, for example a time with no date. | Retype it with the date, for example `2026-09-25 10:45`. |
| `no sample <point> -- it is neither in the ChemistrySampleInfo tab nor already in the database` | A `FieldParameters` row with no sample. | Add the sample-info row, or fix the `SamplePointID`. |
| `Missing SamplePointID` | The row has no field sample ID. | Fill in the well plus the crew's letter, on both tabs. |
| `SamplePointID ... has no sample letter` | The ID is just the well (`WL-0264`). | Add the crew's letter (`WL-0264A`), on both tabs. |
| `SamplePointID <point> is dated <date> here but also used on row N (<date>)` | Rows of this sheet give one field sample ID two different days. | Decide which date is right, and give the other visit a letter the well hasn't used, on these rows and their `FieldParameters` rows. |
| `SamplePointID <point> already belongs to the <date> visit` | Two visits share one field sample ID. | Give this visit a letter the well hasn't used (the error lists the ones in use), on this row and its `FieldParameters` row. |
| `<point> was collected on <date>, but these readings were taken on <date>` | The readings row's `Time` is on another day from its sample's `CollectionDate`. | Correct whichever date is wrong, or the `SamplePointID` if it names the wrong visit. |

A run that only reports **warnings** (kept database values, letter
disagreements) or **skips** (parameters already recorded) succeeds.

---

## 5. Known gaps

- **A handful of bad rows blocks the whole sheet.** With the abort-everything
  rule and one living spreadsheet, four blank dates hold up a hundred good rows.
  Deliberate — the alternative is a partly-loaded sheet nobody can reason about
  — but it means the sheet needs cleaning before it loads. `--loadable` makes a
  copy without those rows, so the rest can load while they're fixed.
- **A fixed row can fail on a check it never reached.** A row is only checked as
  far as it got. When its missing `CollectionDate` is filled in, it may then
  meet a later check, such as a letter the well already uses. One pass reports
  everything the data allows, not what fixing it will reveal.
- **Letters are trusted.** Lab and field records meet only on the field sample
  ID. If the lab copies a letter wrong from the chain of custody, its results
  go to the sample that letter names, when that sample can take them, and
  nothing in the data shows it.
- **Dates must agree.** A lab `SampleDate` on another day from the field
  sheet's `CollectionDate` for the same field sample stops the load, whichever
  ingest runs second. Someone checks which date is wrong.
- **Older records may not match their field sample IDs.** Before #970, both
  ingests could name a new record with a computed "next free" letter instead of
  the one supplied. A load that meets such a record reports it as another
  visit's, and someone reconciles it by hand.
- **Visits split before BDMS-1283 stay split.** Field-first runs before LIMS
  learned to adopt left a sheet sample and a LIMS sample for one visit. Nothing
  merges them automatically yet.
- **`Q` is invented vocabulary.** See section 2.
- **Lab result tabs are ignored.** `GenChemResults` and `IsotopeResults` are not
  read by this command, and the LIMS ingest reads a LIMS export, not this
  workbook — so those tabs currently have no ingest path.
- **No alerting, and prod excludes the CLI deps.** As with the LIMS ingest, this
  runs from an engineer's machine and failures surface only in its output.
- **The raw zone is write-and-keep.** Nothing prunes old snapshots, and nothing
  reconciles them against what was loaded — a replay is something an engineer
  chooses, not a repair the ingest performs.
