# Loading isotope results into Ocotillo

This guide walks you through copying the isotope results from the chemistry
field spreadsheet into the Ocotillo database. You don't need any programming
experience. It works the same way as loading the field sheet, so if you've
done that, most of this will be familiar.

Plan on about 15 minutes if your computer is already set up for the field
sheet, and about 30 if it isn't.

## What the ingest does

The isotope results live on the **IsotopeResults** tab of the same Google
Sheet the field crew uses to enter sample info and field parameters. Each row
is one sample's results from one lab. For example, the labs currently report:

- `NMBGMR` reports deuterium (`H2r`) and oxygen-18 (`O18r`).
- `Beta Analytic` reports carbon-14 age and percent modern carbon, carbon-13
  (`C13r`), and often its own deuterium and oxygen-18.
- `University of Miami Tritium Laboratory` reports tritium.

The ingest only loads the measurement columns it knows about. If a lab starts
reporting something new and a column is added to the tab for it, the ingest
skips that column, and the report names it under **WARNINGS** (Step 6). If
this happens, tell the Data Services lead so the ingest can be set up to read
it.

You download the spreadsheet as an Excel file. The ingest reads the
IsotopeResults tab and saves each result to the database, along with its lab,
analysis date, qualifier (`<` or `>`) and uncertainty. When two labs report
the same measurement for a sample, both are kept.

Each row finds its sample by the **field sample ID**: the well plus the crew's
letter, such as `RA-092A`. On this tab it's in the column headed
`WellPointID`, even though it holds the sample ID, not just the well ID.

**The ingest never creates a sample.** The tab has no collection date, so it
can only add results to a sample that's already in the database. Load the
sample info before the isotope results (Step 3 below).

As with the field sheet, it's safe to run more than once. A result that's
already loaded is skipped, so nothing gets saved twice. A result that has
changed since it was loaded stops the run instead (see
[When a result changes](#when-a-result-changes)).

If any row has a problem, the ingest stops and saves **nothing**. A practice
run, or dry run, lists every problem at once.

## Before you start

You need everything on the field sheet guide's
[Before you start](chemistry-field-sheet-ingest-walkthrough.md#before-you-start)
list. It also explains the basics: what the terminal is, how to run a command,
and what `<something>` in angle brackets means.

---

## Step 1. Get set up

Follow Steps 1 to 7 of the
[field sheet guide](chemistry-field-sheet-ingest-walkthrough.md), and stop
before its Step 8:

1. [Open a terminal in the project folder](chemistry-field-sheet-ingest-walkthrough.md#step-1-open-a-terminal-in-the-project-folder).
2. [Install the packages](chemistry-field-sheet-ingest-walkthrough.md#step-2-install-the-packages-the-ingest-needs).
3. [Sign in to Google](chemistry-field-sheet-ingest-walkthrough.md#step-3-sign-in-to-google-for-database-access),
   if you haven't before.
4. [Download the field spreadsheet](chemistry-field-sheet-ingest-walkthrough.md#step-4-download-the-field-spreadsheet)
   and rename it. The isotope results are in the same file.
5. [Update `.env`](chemistry-field-sheet-ingest-walkthrough.md#step-5-update-the-env-settings-file),
   and check `POSTGRES_DB` names the database you mean.
6. [Connect to the database](chemistry-field-sheet-ingest-walkthrough.md#step-6-connect-to-the-database).
7. [Confirm which database you're connected to](chemistry-field-sheet-ingest-walkthrough.md#step-7-confirm-which-database-youre-connected-to).

The rest of this guide writes your downloaded file's name as `<file-name>`,
without the `.xlsx`, the same as the field sheet guide.

## Step 2. Check the results are typed in

Open the IsotopeResults tab in Google Sheets and look over the rows you're
about to load. Each row needs:

- the field sample ID, with its letter, in `WellPointID`;
- the lab's name in `AnalysisLab`, spelled as in the list above (capital
  letters and extra spaces don't matter);
- at least one result.

If a row only has the sample ID and the lab, with no results yet, that's fine.
The ingest reports it as an empty row and skips it.

## Step 3. Load the sample info first

The isotope results attach to samples the database already has. If the field
sheet's sample info hasn't been loaded since these samples were collected,
load it now by following the field sheet guide's
[Step 8](chemistry-field-sheet-ingest-walkthrough.md#step-8-do-a-practice-run)
to
[Step 10](chemistry-field-sheet-ingest-walkthrough.md#step-10-do-the-real-run),
using the same download.

A **practice** run of the field sheet isn't enough. It saves nothing, so the
isotope ingest can't see its samples. The field sheet needs a real run first.

If you're not sure whether it's loaded, go on to Step 4. A practice run
reports every row whose sample is missing.

## Step 4. Do a practice run

A practice run, or dry run, reads the file and checks every row. It reports
what it would save, but it saves nothing to the database and keeps no copy.

Copy all three lines and paste them together:

```bash
uv run oco water-chemistry isotope-upload --file ~/Downloads/<file-name>.xlsx --dry-run \
    --failed-rows ~/Downloads/<file-name>_isotope_failed_rows.xlsx \
    --loadable ~/Downloads/<file-name>_isotope_loadable.xlsx
```

As with the field sheet, the last two lines ask for two extra files:

- **`<file-name>_isotope_failed_rows.xlsx`**: every row with a problem, with
  its row number in the Google Sheet and why it failed. Empty rows are listed
  on the same sheet, in row order, so every row that needs a look is in one
  place. Written if any row failed or is empty.
- **`<file-name>_isotope_loadable.xlsx`**: your download with the problem rows
  and the empty rows blanked out on the IsotopeResults tab, so every row left
  in it is one that loads. Written only if a row failed.

Read the top line of the report:

| Top line says | What it means | What to do |
|---|---|---|
| `DRY RUN (nothing written)` | Every row passed. | Go to Step 6. |
| `ABORTED -- nothing written` | At least one row has a problem. | Go to Step 5. |

Just under the top line, **Database** names the database the run checked
against. It should match Step 1.

The summary counts what a real run would do:

- **results loaded**: results the database doesn't have yet.
- **samples with results**: how many samples those results belong to.
- **results skipped**: results already saved on an earlier run.
- **rows empty**: rows with a lab but no results. They're listed under
  **EMPTY ROWS** and skipped. An empty row doesn't stop the run.
- **rows failed**: rows with a problem. One practice run finds all of them.

**If the top line says `ABORTED`, expect `0` for results loaded, samples with
results and results skipped.** Any failed row stops the whole run, so the
report doesn't count the rows that passed. Step 5a gets the real counts.

## Step 5. Deal with the failed rows

Do this step only if Step 4's top line said `ABORTED`.

### 5a. Check the rest of the sheet

Do a practice run on the loadable copy:

```bash
uv run oco water-chemistry isotope-upload --file ~/Downloads/<file-name>_isotope_loadable.xlsx --dry-run
```

The top line should say `DRY RUN (nothing written)`, and this time the counts
are real. If this run says `ABORTED` too, send the whole terminal output to
the Data Services lead.

### 5b. Fix the failed rows

Open `<file-name>_isotope_failed_rows.xlsx` from Downloads. **Source row** is
the row number in the Google Sheet, and **Why it failed** says what's wrong.
Fix the problems **in the Google Sheet**, not in the downloaded file.

Rows whose **Why it failed** starts with `Empty, not a failure` have a sample
and a lab but no results. They didn't stop the run. Fill in the results once
the lab reports them, or delete the row if it was added by mistake.

| Why it failed says | How to fix it |
|---|---|
| `no sample ... -- load its ChemistrySampleInfo row ...` | The database doesn't have this sample yet. Load the field sheet (Step 3). If the sample isn't on the ChemistrySampleInfo tab either, add it there, with its collection date, then load the field sheet. |
| `SamplePointID ... has no sample letter` | The ID is just the well (`WL-0231`). Add the crew's letter (`WL-0231A`). Check the ChemistrySampleInfo tab or the chain of custody for the right one. |
| `Missing SamplePointID` | Fill in the field sample ID in `WellPointID`. |
| `has no well identifier assigned yet` | The row says `WL-####`. Ask the Data Services lead to assign the PointID, then use it here and on the other tabs. |
| `no matching Thing (well) ... found` | The well isn't in Ocotillo yet. Ask the Data Services lead to add it. |
| `has ... samples named ...; cannot tell which one` | The database holds two samples with this ID. Send the row to the Data Services lead. |
| `Missing AnalysisLab` | Fill in the lab's name. |
| `AnalysisLab ... is not a known lab` | Check the spelling against the lab names above. If it's a new lab, ask the Data Services lead to add it. |
| `AnalysisDate ... is not a recognizable date` | Retype the date, for example `2025-08-27`, or clear the cell. |
| `... is not a number` | A result or uncertainty cell holds text. Enter the number, or clear the cell. A `<` or `>` goes in its own `_Qualifier` column, not with the number. |
| `... is not one of <, >` | A `_Qualifier` cell holds something else. Use `<` or `>`, or clear it. |
| `... filled but ... blank` | A qualifier or uncertainty is filled in but the result beside it is blank. Usually a number went in the wrong column. |
| `... was collected on ..., but ... analysed it on ...` | The analysis date is before the sample was collected. Check both dates against the lab report and the crew's notes. If the analysis date is right, the sample ID may name the wrong visit. |
| `... is also on row ... with a different result` | Two rows give the same sample, lab and measurement different numbers. Delete the wrong one. |
| `... is already stored for ... and differs: ...` | See [When a result changes](#when-a-result-changes) below. |
| `... is stored ... times for ...` | The database already holds that result twice. Send the row to the Data Services lead. |

A failed row holds back **all** of that row's results, not only the one with
the problem. For example, one bad date on a Beta Analytic row keeps that
sample's carbon-14, carbon-13, deuterium and oxygen-18 from loading until it's
fixed.

After the fixes, download a fresh copy, rename it, and start again from
Step 4.

### 5c. Load the rest while rows are fixed (optional)

You don't have to wait for every row to be fixed. Do Step 6 with
`<file-name>_isotope_loadable.xlsx` in place of `<file-name>.xlsx`. Once the
rows are fixed, download a fresh copy and start again from Step 4. Results
already loaded show as **results skipped**.

The loadable copy shows what **would** load when you made it, not what **was**
loaded. To see what a real run loaded, use its report, or the snapshot named
on its `Archived` line.

## Step 6. Do the real run

This is the practice-run command without `--dry-run` and the two report files:

```bash
uv run oco water-chemistry isotope-upload --file ~/Downloads/<file-name>.xlsx
```

The top line should say `SUCCESS`. Check **Database** names the database you
meant. **results loaded** should match the practice run, and a line starting
`Archived` tells you a copy of the tab was saved.

If you see a **WARNINGS** section, the data still loaded. Three warnings are
common:

- `... doesn't read the column(s) ...`: the tab has a column the ingest
  doesn't know, so nothing in it was loaded. If it holds results, send the
  warning to the Data Services lead.

- `... repeats row ...; loaded once`: the same result is typed on two rows.
  It was saved once. Delete the extra row from the sheet when you can.
- `... has no collection date`: the sample has no collection date in the
  database, so these results have no date unless the lab gave an analysis
  date. Send these to the Data Services lead.

## Step 7. Check it worked

Run the real command from Step 6 a second time, on the same file:

```bash
uv run oco water-chemistry isotope-upload --file ~/Downloads/<file-name>.xlsx
```

This time **results loaded** should be `0`, and **results skipped** should
match the first run's results loaded. That confirms the results are saved,
and that running again doesn't duplicate them.

## Step 8. Finish up

Follow the field sheet guide's
[Step 12](chemistry-field-sheet-ingest-walkthrough.md#step-12-finish-up): stop
the proxy, close the terminals, and delete the downloads. Keep
`<file-name>_isotope_failed_rows.xlsx` until every row in it is fixed and
loaded.

---

## When a result changes

Once a result is saved, the ingest never changes it. If the sheet later gives
a different number, qualifier, uncertainty or unit for the same sample, lab
and measurement, the run stops with `... is already stored for ... and
differs`, and lists what changed.

That can happen for two reasons:

- **Someone edited the sheet**, to fix a typo or by mistake.
- **The lab re-analysed the sample**, for example because it was asked to,
  and reported a new value.

Either way, a person has to decide which value is right. Don't edit the sheet
back and forth to get the run through. Send the failed row workbook to the
Data Services lead. They correct the saved result by hand if the new value
stands. Once the sheet and the database agree, the row shows as skipped and
the rest loads.

## What happens when a cell is left blank

| Column | If you leave it blank |
|---|---|
| `WellPointID` | **The row fails.** The field sample ID is how the results find their sample. |
| `AnalysisLab` | **The row fails**, unless the row has no results at all. The lab is part of what identifies each result. |
| `AnalysisDate` | Left empty. Results are dated by their sample's collection date either way, so this only records when the lab ran them. |
| `ChemistryLabID` | Left empty. This is the lab's own number for the sample, such as Beta Analytic's. |
| A result column, such as `H2r (pm)` | That result isn't saved. The rest of the row still loads. |
| A `_Qualifier` column | No qualifier. Most results don't have one. |
| An `_Uncertainty` or `Tritium_error` column | No uncertainty is saved for that result. |

A row where every result cell is blank is reported as empty and skipped.

## If something goes wrong

| You see | What it means | What to do |
|---|---|---|
| `Found no IsotopeResults tab` | The file isn't the field spreadsheet, or the tab was renamed. | Download the right spreadsheet, or ask the sheet's keeper about the tab name. |
| `No raw zone configured ...` | `.env` doesn't say where to keep the copy. | Repeat the field sheet guide's [Step 5a](chemistry-field-sheet-ingest-walkthrough.md#5a-choose-where-the-ingest-keeps-its-copy). |
| `Could not connect to the database`, `connection refused`, or the command hangs | The proxy isn't running. | Repeat the field sheet guide's Steps 6 and 7. |
| Almost every row says `no sample ...` | The field sheet hasn't been loaded into this database. | Do Step 3, then start again from Step 4. |

For anything else, copy the whole terminal output and send it to the Data
Services lead, with a note about which step you were on.

For the rules behind this guide, such as how results are matched and what the
ingest won't do, see `docs/chemistry-isotope-ingest.md`.
