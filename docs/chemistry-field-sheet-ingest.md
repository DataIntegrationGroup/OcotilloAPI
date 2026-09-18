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
| `SamplePointID` | the lettered sample point (`RA-116A`); checked against the well |
| `CollectionDate` | `CollectionDate` — **required**, it is the match key |
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
for; it is kept in `Notes` as `Measured <ISO timestamp>`.

---

## 3. How samples are matched

A field visit and its lab batch are **one sample**, so the sheet must not create
a second `NMA_Chemistry_SampleInfo` row beside the one the LIMS ingest made. The
sheet carries no `WCLab_ID` — the crew writes the row down before the sample
reaches a lab — so matching is on **well PointID plus collection date**:

1. Exact `collection_date` match for that well wins.
2. Failing that, a sample on the **same calendar day** is treated as the same
   visit (the sheet's time and the lab's time for one visit routinely differ by
   minutes).
3. Two samples on the same day are ambiguous: reported, never guessed at.

On a match, the sheet **fills blank columns only**. A value already in the
database is kept and the disagreement is reported as a warning — a field sheet
is re-typed and re-sent, so it is not authoritative over what is stored.

With no match, a new sample is created with the **next free letter incrementor**
for that well (`A`, `B`, ... `Z`, `AA`, ...), the same rule the LIMS ingest uses.
If the spreadsheet supplied a different letter, the computed one wins (it cannot
collide with an existing sample point) and the disagreement is reported.

Field parameters attach to the sample named by their `SamplePointID`, whether it
was created by this run, by an earlier run, or by the LIMS ingest. A parameter
already recorded for that sample is skipped, so **re-running the same sheet
loads nothing twice**.

---

## 4. Failure semantics

Any data-quality problem **aborts the whole import and nothing is written** —
the same rule as the LIMS ingest, so a spreadsheet is never half loaded. Every
offending row is reported in one pass, so one round of fixes clears them.

What aborts a run:

| Reported cause | Meaning | Action |
|---|---|---|
| `Missing CollectionDate` | The row has no date to match on. | Fill the date in the spreadsheet. |
| `CollectionDate ... is not a recognizable date` | Not ISO, US-style, or a real date cell. | Fix the cell. |
| `PointID 'WL-####' has no well identifier assigned yet` | A real sample whose well has not been given an id. | Assign the PointID, then re-run. |
| `WellPointID ...: no matching Thing (well) found` | The well is not in Ocotillo. | Transfer or create the well first. |
| `SamplePointID ... does not belong to well ...` | The lettered point's base is a different well. | Fix one of the two cells. |
| `CollectionMethod ... is not a known collection method` | Neither one of the seven `LU_CollectionMethod` meanings nor its code. | Use one from the list in section 2. |
| `CollectedBy ... is longer than 5 characters` | The legacy column holds a 5-character code. | Use the code, not the name — names belong in `Staff`. |
| `non-numeric reading(s)` | A field parameter cell holds text. | Blank it or fix the number. |
| `no sample <point> -- it is neither in the ChemistrySampleInfo tab nor already in the database` | A `FieldParameters` row with no sample. | Add the sample-info row, or fix the `SamplePointID`. |

A run that only reports **warnings** (kept database values, letter
disagreements) or **skips** (parameters already recorded) succeeds.

---

## 5. Known gaps

- **A handful of bad rows blocks the whole sheet.** With the abort-everything
  rule and one living spreadsheet, four blank dates hold up a hundred good rows.
  Deliberate — the alternative is a partly-loaded sheet nobody can reason about
  — but it means the sheet needs cleaning before the first successful run.
- **Same-day matching is a heuristic.** Two genuine visits to one well on one
  day are reported as ambiguous rather than loaded.
- **No lab id on the field side.** If a well is sampled on a day the lab batch
  records differently, the two will not match and a second sample point is
  created.
- **`Q` is invented vocabulary.** See section 2.
- **Lab result tabs are ignored.** `GenChemResults` and `IsotopeResults` are not
  read by this command, and the LIMS ingest reads a LIMS export, not this
  workbook — so those tabs currently have no ingest path.
- **No alerting, and prod excludes the CLI deps.** As with the LIMS ingest, this
  runs from an engineer's machine and failures surface only in its output.
- **The raw zone is write-and-keep.** Nothing prunes old snapshots, and nothing
  reconciles them against what was loaded — a replay is something an engineer
  chooses, not a repair the ingest performs.
