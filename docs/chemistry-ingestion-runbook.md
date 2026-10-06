# Chemistry Ingestion — Interim Workaround Runbook

Purpose: capture the known gaps, assumptions, and step-by-step process for
Data Services (Ocotillo) chemistry ingestion, so the manual workaround can be
run consistently while the fuller solution is pursued.

- Jira: [BDMS-1034](https://nmbgmr.atlassian.net/browse/BDMS-1034).
- Code (Data Services path):
  - `services/chemistry_lims.py` — parse a LIMS `.xlsx` and load the legacy
    NMA chemistry tables (analyte mapping ported from AMPAPI `chemfile.py`).
  - `services/chemistry_drive.py` — on-demand ingest of new files from the
    shared Drive folder; updates the manifest. Engineer-triggered; no polling.
  - `cli/cli.py` — `oco water-chemistry bulk-upload` and `oco water-chemistry
    sync-drive`.
- Target tables: `NMA_MajorChemistry`, `NMA_MinorTraceChemistry`,
  `NMA_Chemistry_SampleInfo` (`db/nma_legacy.py`).
- Legacy source: AMPAPI `chemfile.py` (`MajorChemistry` /
  `MinorandTraceChemistry` in SQL Server).
- Field half: the crew's data-entry spreadsheet (sample info + field
  parameters) has its own ingest -- see
  **`docs/chemistry-field-sheet-ingest.md`**. It writes the same
  `NMA_Chemistry_SampleInfo` rows this ingest does, matched on the field
  sample ID (`SamplePointID`, the well plus the crew's letter). Both ingests
  match that way, so either can go first. A workbook loaded after the field
  sheet adopts the sheet's record rather than creating a second one. See
  "Either ingest can go first" in that doc.

---

## 0. The workaround at a glance

```mermaid
flowchart LR
    S["Sianin<br/>export lab LIMS batch as .xlsx"] --> D["Shared Google Drive folder<br/>CHEMISTRY_DRIVE_FOLDER_ID"]
    E["Engineer<br/>oco water-chemistry sync-drive (on demand)"] --> D
    E --> T["Ingest new/changed files →<br/>Ocotillo NMA_* chemistry tables"]
    E --> M["manifest.json in GCS<br/>updated with per-file results"]
```

Chemistry is ingested into a single destination: the Ocotillo (Data Services)
Postgres database — the legacy `NMA_MajorChemistry`, `NMA_MinorTraceChemistry`,
and `NMA_Chemistry_SampleInfo` tables.

---

## 1. Roles

- **Sianin** — exports each lab chemistry batch from the LIMS as an `.xlsx`
  workbook and drops it in the shared Drive folder. One workbook per batch.
- **Engineer** (e.g. Kelsey) — explicitly triggers the Data Services ingestion
  CLI against the folder when a run is wanted, reviews the printed results, and
  confirms the manifest updated. Acts on any files reported as `failed`. There
  is no polling or scheduling — ingestion only happens when an engineer runs it.
- **Engineering** — owns the CLI, the analyte map, and the fuller solution.

---

## 2. Prerequisites (Kelsey's machine)

- [ ] Repo checked out; env installed **with the CLI group**:
      `uv sync --locked --group cli` (installs `openpyxl` +
      `google-api-python-client`, which are not part of the API runtime).
- [ ] Postgres (Ocotillo) reachable; `.env` has `POSTGRES_*` (or Cloud SQL)
      creds pointing at the target Data Services database.
- [ ] `GCS_BUCKET_NAME` set (holds the manifest).
- [ ] `CHEMISTRY_DRIVE_FOLDER_ID` set to the shared folder id
      (see `.env.example`). Optional `CHEMISTRY_INGEST_MANIFEST_PATH`
      (default `chemistry-ingest/manifest.json`).
- [ ] Google credentials available with:
      - **read** access to the shared Drive folder,
      - **read/write** on the GCS bucket.
      Locally this is application-default credentials
      (`gcloud auth application-default login`) for an account added to the
      folder; in production it is the base64 `GCS_SERVICE_ACCOUNT_KEY` service
      account (which must be a member of the folder).

---

## 3. Process — Sianin (drop files)

1. Export the lab batch from the LIMS as an `.xlsx` workbook. It must carry the
   standard LIMS columns: `Param`, `Results_Units`, `Dilution`, `AnalysisTime`,
   `SampleNumber`, `CustomerSampleNumber`, `SamplePointID`, `Method`, `Test`,
   `ReportedND`, `LowerLimit`, `SampleDate`.
2. Ensure `SamplePointID` is the **field sample ID from the chain of
   custody**: the well's PointID (its Ocotillo Thing name) plus the crew's
   letter, for example `WL-0264B`. A `SamplePointID` without a letter is
   rejected. The letter is how each lab sample finds its own field sample,
   including the two halves of a duplicate pair or a split.
3. Ensure every row has its `SampleDate`, the collection date. A blank one is
   rejected, since the lab sample is checked against its field sample's date.
4. Drop the workbook in the shared Drive folder. Do not edit a file in place
   after it has been ingested — a content change re-ingests it (by md5), and a
   lab sample whose results changed then stops the file for review.

---

## 4. Process — Engineer (run the ingest)

Check which database the run will reach, as the server reports it:

```bash
oco db-info
```

The `sync-drive` and `bulk-upload` reports also name the database under their
headline.

Dry run first to see what is new without writing anything:

```bash
oco water-chemistry sync-drive --dry-run
```

Then ingest:

```bash
oco water-chemistry sync-drive
# or point at a specific folder:
oco water-chemistry sync-drive --folder-id <DRIVE_FOLDER_ID>
```

Read the summary. Buckets:

- **ingested** — file loaded; shows rows imported.
- **skipped** — the whole file was already ingested (manifest has a `success`
  entry and the file's md5 is unchanged).
- **ingested with skipped samples** — a file loads, but a lab sample
  (`WCLab_ID` / SampleNumber) already recorded for the well, with exactly the
  same results, is skipped and listed under `skipped_duplicates`; this is
  normal and not a failure. A lab sample whose field sample the field sheet
  already recorded is attached to that record and listed under
  `adopted_samples`. Any other lab sample gets a new record named with its
  `SamplePointID` (`MG-030A`, `MG-030B`, ...).
- **failed** — nothing loaded for that file (a data-quality abort). Causes:

| Reported cause | Meaning | Action |
|----------------|---------|--------|
| `Unmapped analyte Param=...` | A LIMS `Param` name is not in the analyte map. | Send the Param name to engineering to add to `_ANALYTE_MAPPINGS` in `services/chemistry_lims.py`. |
| `no matching Thing (well) found` | `SamplePointID` has no Ocotillo well. | Verify the PointID; ensure the well was transferred to Data Services first. |
| `... has no sample letter` | `SamplePointID` is just the well (`WL-0264`). | Use the field sample ID from the chain of custody (`WL-0264B`). |
| `SampleDate is blank` | A row has no collection date. | Fill in `SampleDate` from the chain of custody. |
| `... its rows name more than one sample ...` | Rows sharing one `SampleNumber` give different letters in `SamplePointID`. | Ask the lab which letter is right, and make the rows agree. |
| `... its rows give SampleDates on N different days ...` | Rows sharing one `SampleNumber` give different `SampleDate` days. | Ask the lab which date is right, and make the rows agree. |
| `lab samples X and Y both name field sample ...` | Two `SampleNumber`s in the workbook name the same field sample, which has only one LabSampleID. | Check the letters with the lab, and correct the one that's wrong. |
| `... field sample <point> already has lab id ...` / `is from <date>, not <date>` / `has no collection date` | The `SamplePointID` names a record that can't be this lab sample's: it holds another lab sample's results, or its date disagrees. | Check the letter and `SampleDate` with the lab and the field sheet; correct whichever is wrong, then re-run. |
| `LabSampleID X is already loaded for <point>; ...` | This `SampleNumber` was loaded before, and the workbook now differs: a changed value, an added analyte, or another `SamplePointID`. | Review the listed differences with the lab. A correction to stored results is fixed by hand, not by re-loading. |

Exit code is non-zero if any file failed.

A single file (bypassing Drive) can be loaded directly:

```bash
oco water-chemistry bulk-upload --file /path/to/batch.xlsx
```

---

## 5. The manifest

- Location: `gs://$GCS_BUCKET_NAME/<CHEMISTRY_INGEST_MANIFEST_PATH>`
  (default `chemistry-ingest/manifest.json`).
- Keyed by **Drive file id**. Each entry records:
  `name`, `md5`, `modified_time`, `status` (`success` / `failed`),
  `rows_imported`, `validation_errors_or_warnings`, `ingested_at`
  (and `error` for hard failures).
- Semantics:
  - A file is **skipped** only when its manifest entry is `success` **and** the
    Drive md5 is unchanged.
  - **failed** or **content-changed** files are retried on the next run.
- The manifest is rewritten after **every** file, so an interrupted run keeps
  its progress.
- Inspect it: `gsutil cat gs://$GCS_BUCKET_NAME/chemistry-ingest/manifest.json`.

---

## 6. What the ingest does (summary)

For each workbook: map each `Param` to an analyte code + target table (major vs
minor) via `lookup_analyte`; compute the value (non-detects become
`LowerLimit × Dilution` with a `<` symbol); collapse duplicate
(SamplePointID, WCLab_ID, analyte) rows (prefer EPA 200.7, or "low bromide" for
Br); resolve the base `SamplePointID → Thing`. Then, per distinct lab sample
(`WCLab_ID`): its rows must share one lettered `SamplePointID` (the field
sample ID) and one `SampleDate`, and no other lab sample in the file may name
the same field sample. If that lab sample is already recorded for the well, skip
it when the stored results are identical, and stop for review when they're not.
If a record is already named with its field sample ID, stamp the lab id onto it
and insert the analyte rows under it; the record must have no `WCLab_ID` yet and
be dated on the `SampleDate`, or the file aborts. Otherwise create a new
`NMA_Chemistry_SampleInfo` named with the field sample ID, and insert the
analyte rows under it. A data-quality problem aborts the whole file and nothing
is written.

---

## 7. Known gaps

- **Re-loads are recognized by `WCLab_ID`.** A lab sample already loaded is
  skipped only when the workbook's copy is identical: same `SamplePointID`, and
  the same value, `<` symbol and units for every analyte. Anything else stops
  the file for review, so a correction from the lab is never dropped silently,
  but nor is it applied: stored results are corrected by hand. A genuinely new
  lab sample under a reused SampleNumber stops the same way. A row with no
  SampleNumber is rejected, since there would be nothing to recognize it by on
  the next run.
- **`.xlsx` only.** Legacy `.xls` LIMS exports are not read; the file must be
  a modern `.xlsx`.
- **Fixed analyte map.** Unknown `Param` names fail until engineering adds them
  to `_ANALYTE_MAPPINGS`. Only major + minor analytes are handled — field
  parameters and radionuclides are out of scope.
- **Well must exist first.** `SamplePointID` must already match an Ocotillo
  `Thing.name`; otherwise the file fails.
- **Failed files retry loudly.** A file that fails (e.g. unmapped analyte or a
  missing well) is retried on every run and keeps reporting `failed` until
  resolved.
- **Concurrent runs race the manifest.** Ingestion is engineer-triggered on
  demand by design (no polling/scheduling). But two engineers running
  `sync-drive` at the same time race the manifest object (last write wins) —
  coordinate so only one run is in flight.
- **No alerting.** Failures surface only in the CLI output the engineer reads.
- **Prod excludes the CLI deps.** The `cli` dependency group
  (`openpyxl`, `google-api-python-client`) is not in the production requirements
  export, so the ingest runs from an engineer's machine, not the deployed app.

---

## 8. Assumptions

- One lab batch per `.xlsx`, with the standard LIMS column set (section 3).
- `SamplePointID` is the field sample ID from the chain of custody: the well
  PointID (the Ocotillo `Thing.name`) followed by the crew's sample letter.
- `SampleDate` is the collection date, filled on every row.
- All files in the shared folder are chemistry LIMS workbooks (the sync filters
  to `.xlsx` by MIME type).
- Analyses agency is NMBGMR; non-detects and units follow the AMPAPI
  `chemfile.py` conventions.
- The account running the CLI can read the Drive folder, read/write the GCS
  bucket, and reach the Data Services database.

---

## 9. Toward the fuller solution

Candidate improvements, roughly in priority order:

- **Applying lab corrections.** A changed re-load now stops for review;
  loading the corrected values in place of the stored ones is still manual.
- **Alerting** on failed files (email/Slack) rather than relying on reading CLI
  output.
- Make the **analyte map** data-driven (lexicon-backed) so new params don't
  require a code change.
