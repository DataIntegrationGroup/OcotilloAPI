# Loading the chemistry field sheet into Ocotillo

This guide walks you through copying the field crew's chemistry spreadsheet
into the Ocotillo database. You don't need any programming experience. You'll
download the spreadsheet, type commands into a terminal (Terminal on a Mac, Git
Bash on Windows), and change a few lines in one settings file.

Plan on about 30 minutes the first time. Later runs take about 5.

## What the ingest does

The field crew records each water chemistry visit in a Google Sheet. It has
two tabs:

- **ChemistrySampleInfo**: one row per sample (which well, what day, who
  collected it).
- **FieldParameters**: the readings taken on site (pH, temperature,
  conductivity, and so on).

You download the spreadsheet as an Excel file. The ingest reads both tabs from
that file and saves them to the database. It's safe to run more than once. A
row that's already loaded is skipped, so nothing gets saved twice.

If any row in the sheet has a problem, the ingest stops and saves **nothing**.
A practice run lists every problem at once. It can also save the problem rows
to their own spreadsheet, and make a copy of the sheet without them, so the
rest can load while the problem rows are fixed.

Each sample is known by its **field sample ID**, the `SamplePointID` column:
the well plus the crew's letter, such as `WL-0264A`. The lab copies the same
ID from the chain of custody, which is how its results find this sample later.

## Before you start

Check that you have each of these. If you're missing one, ask the Data
Services lead before going further.

- [ ] A copy of the OcotilloAPI project on your computer, in any folder.
      This guide calls that folder `<path-to-OcotilloAPI>`.
- [ ] Windows only: Git Bash installed. It's part of Git for Windows. The
      commands in this guide are written for a Mac or Linux terminal, and Git
      Bash runs them the same way. Nobody has followed this guide on Windows
      yet, so tell the Data Services lead about anything that doesn't work.
- [ ] `uv` installed. It manages the project's Python packages.
- [ ] The Google Cloud command-line tool (`gcloud`) installed.
- [ ] The Cloud SQL proxy program (`cloud-sql-proxy`) downloaded. It opens a
      secure connection to the database.
- [ ] A Google account with read and write access to the Ocotillo databases.
      The practice run needs write access too: it saves every row and then
      undoes it.
- [ ] Permission to view the field spreadsheet in Google Sheets.
- [ ] The name of the database to load into: `ocotillo-staging` for
      practice, `ocotillo` for production.

## A few basics

- **The terminal** is where you type commands. On a Mac, open the Terminal
  app (press `Cmd` + `Space`, type "Terminal", press `Return`). On Windows,
  open Git Bash from the Start menu.
- **Running a command** means pasting it into the terminal and pressing
  `Return` (`Enter` on Windows). To paste into Git Bash, right-click and
  choose **Paste**, or press `Shift` + `Insert`.
  Paste one command at a time and wait for it to finish. You'll know it's
  finished when the prompt, the line ending in `%` or `$`, comes back.
- **Stopping a command** that's still running: press `Ctrl` + `C`.
- **`<something>` in angle brackets** is a placeholder. Replace the whole
  thing, brackets included, with your own value.

---

## Step 1. Open a terminal in the project folder

Open a terminal and run this, with your project folder in place of
`<path-to-OcotilloAPI>`:

```bash
cd <path-to-OcotilloAPI>
```

For example, `cd ~/PycharmProjects/OcotilloAPI`. This moves the terminal into
the project folder. Every command in this guide assumes you've run it first.
If you close the terminal, run it again when you come back.

## Step 2. Install the packages the ingest needs

```bash
uv sync --locked --group cli
```

This installs the tools the ingest uses. It can take a minute or two the
first time. It's fine to run again later, since it only installs what's
missing.

## Step 3. Sign in to Google for database access

**If you've connected to the Ocotillo database from this computer before, skip
this step.**

The database connection uses your Google sign-in. Run:

```bash
gcloud auth application-default login
```

A browser window opens. Pick your work Google account and allow the
permissions it asks for. When the browser says you're signed in, go back to
the terminal.

Run the command exactly as shown. Adding extra permissions for Google Drive or
Sheets makes Google block the sign-in with a "tried to access sensitive info"
message. This guide doesn't need them, because you download the spreadsheet
yourself in the next step.

## Step 4. Download the field spreadsheet

1. Open the field spreadsheet in Google Sheets.
2. Choose **File > Download > Microsoft Excel (.xlsx)**. The file saves to
   your **Downloads** folder.
3. Open your Downloads folder (Finder on a Mac, File Explorer on Windows) and
   rename the file. Any name works if it uses only letters, numbers, hyphens
   (`-`) and underscores (`_`), for example `field-data-2026-10-05.xlsx`. The
   original name has an `&` in it, and the terminal treats `&` and spaces as
   special characters.

From here on, the guide writes your file's name as `<file-name>`, without the
`.xlsx`. If you named it `field-data-2026-10-05.xlsx`, then
`<file-name>_loadable.xlsx` means `field-data-2026-10-05_loadable.xlsx`.

Download a fresh copy every time you run the ingest. An old copy won't
include the crew's latest rows.

## Step 5. Update the `.env` settings file

`.env` is a plain text file in the project folder. It holds settings like
which database to use. It also holds passwords, so **never email it, paste
it into chat, or upload it anywhere**.

Open it in any editor that saves plain text, such as an IDE like PyCharm or
VS Code, but not a word processor like Word. If you don't have one, use the
editor that comes with your computer. On a Mac, this opens it in TextEdit:

```bash
open -e .env
```

On Windows, this opens it in Notepad:

```bash
notepad .env
```

Make the two changes in 5a and 5b below, then save (`Cmd` + `S` on a Mac,
`Ctrl` + `S` on Windows) and close the file.

### 5a. Choose where the ingest keeps its copy

Each run saves a copy of exactly what it read from the file. The copy makes it
possible to investigate a problem later. Add this line at the end of the file
to keep the copies in a folder on your computer:

```
OCO_RAW_ZONE_DIR=~/.ocotillo/raw
```

Without this line, or `INGESTION_GCS_BUCKET` for the shared cloud bucket, the
ingest refuses to run.

### 5b. Check which database you'll load into

Find the line that starts with `POSTGRES_DB=`. Make sure it names the
database you meant to use:

```
POSTGRES_DB=ocotillo-staging
```

Use `ocotillo-staging` for practice and `ocotillo` for production. This line
decides where the data goes. Double-check it every time. Loading
into production when you meant staging is the most serious mistake you can
make here.

## Step 6. Connect to the database

The database lives in Google Cloud. The Cloud SQL proxy opens a private
connection to it, and it has to keep running for the whole ingest.

1. If Docker Desktop is running a local Ocotillo database, stop it first. Two
   databases on the same connection point will confuse the ingest.
2. Open a **second** terminal window, and run Step 1 in it.
3. Start the proxy in that window, with the program's location in place of
   `<path-to-cloud-sql-proxy>`, for example `~/cloud-sql-proxy`. On Windows
   the program's name ends in `.exe`.

   ```bash
   <path-to-cloud-sql-proxy> waterdatainitiative-271000:us-west4:dataservices --auto-iam-authn
   ```

4. Wait for a line that says the proxy is **ready for new connections**.
5. Leave this window open and go back to your first terminal window.

## Step 7. Confirm which database you're connected to

In your first terminal window, run:

```bash
uv run oco db-info
```

It asks the database server which database you reached, and changes nothing.
Look at the first line:

```
Database:     ocotillo-staging
```

**If the name isn't the database you expected, stop here.** Go back to
Step 5b. If it says `Could not connect to the database`, go back to Step 6
and check the proxy is still running.

## Step 8. Do a practice run

A practice run, or dry run, reads the file and checks every row. It reports
what it would save, but it saves nothing to the database and keeps no copy.

Copy all three lines and paste them together. The `\` at the end of a line
tells the terminal the command continues on the next one.

```bash
uv run oco water-chemistry field-upload --file ~/Downloads/<file-name>.xlsx --dry-run \
    --failed-rows ~/Downloads/<file-name>_failed_rows.xlsx \
    --loadable ~/Downloads/<file-name>_loadable.xlsx
```

The last two lines ask for two extra files, written only if a row has a
problem:

- **`<file-name>_failed_rows.xlsx`**, the failed row workbook: every row with
  a problem, with its row number in the Google Sheet and why it failed.
- **`<file-name>_loadable.xlsx`**, the loadable copy: your download with the
  problem rows blanked out, so everything else can load now.

Read the top line of the report:

| Top line says | What it means | What to do |
|---|---|---|
| `DRY RUN (nothing written)` | Every row passed. | Go to Step 10. |
| `ABORTED -- nothing written` | At least one row has a problem. | Go to Step 9. |

Just under the top line, **Database** names the database the run checked
against. It should match Step 7.

The summary under the top line counts what a real run would do:

- **samples created**: samples the database doesn't have yet.
- **samples matched**: samples it already has under that field sample ID,
  for example from lab results or an earlier run.
- **readings skipped**: readings already saved on an earlier run.
- **rows failed**: rows with a problem. One practice run finds all of them.

**If the top line says `ABORTED`, expect `0` for samples created, samples
matched and readings skipped.** Any failed row stops the whole run, so the
report doesn't count the rows that passed. Only **rows read** and **rows
failed** mean anything. Step 9a gets the real counts from the loadable copy.

At the very end, **REPORTS** says where the two files were saved, or that
they weren't needed because no row failed.

## Step 9. Deal with the failed rows

Do this step only if Step 8's top line said `ABORTED`. If it said
`DRY RUN (nothing written)`, go straight to Step 10.

### 9a. Check the rest of the sheet

Do a practice run on the loadable copy, the file Step 8 made with the failed
rows blanked out:

```bash
uv run oco water-chemistry field-upload --file ~/Downloads/<file-name>_loadable.xlsx --dry-run
```

The top line should say `DRY RUN (nothing written)`. This time the counts
are real: **samples created**, **samples matched** and **readings skipped**
are what the rest of the sheet would do. Step 8 explains what each count
means.

If this run says `ABORTED` too, send the whole terminal output to the Data
Services lead.

### 9b. Fix the failed rows in the Google Sheet

Open `<file-name>_failed_rows.xlsx` from Downloads. It has a sheet for each
tab. The **Source row** column is the row number in the Google Sheet, and
**Why it failed** says what's wrong. The rest of each line is the row as it
was, so you can see the cells without switching back and forth.

Fix the problems **in the Google Sheet**, not in the downloaded file. The
Google Sheet is the crew's master copy, and edits to your download would be
lost next time. If you can't edit the sheet yourself, send the failed row
workbook to whoever keeps it.

| Why it failed says | How to fix it in the sheet |
|---|---|
| `Missing CollectionDate` | Fill in the date the sample was collected. |
| `... is not a recognizable date` | Retype the date, for example `2026-09-25`. |
| `Missing SamplePointID` | Fill in the field sample ID (the well plus the crew's letter, such as `WL-0264A`), on both tabs. |
| `SamplePointID ... has no sample letter` | The ID is just the well (`WL-0264`). Add the crew's letter (`WL-0264A`), on both tabs. Check the crew's notes or the chain of custody for the right letter. |
| `does not belong to well ...` | The `SamplePointID` doesn't match the `WellPointID`. Correct one of them. |
| `no matching Thing (well) found` | The well isn't in Ocotillo yet. Ask the Data Services lead to add it. Every row for that well is listed. |
| `has no well identifier assigned yet` | The row says `WL-####` because the well hasn't been given a PointID. Ask the Data Services lead to assign one, then put it on both tabs. |
| `SamplePointID ... is dated ... here but also used on row ...` | Two rows of the sheet give one field sample ID two different days. Decide which date is right. If they really are two visits, give one of them a letter the well hasn't used, on both tabs. |
| `SamplePointID ... already belongs to the ... visit` | The database already has this field sample ID, on another day. The error lists the letters the well has used. Give this visit a new letter, on this row and its FieldParameters row. |
| `has ... samples named ...; cannot tell which` | The database holds two samples with this ID. Send the row to the Data Services lead. |
| `is not a known collection method` | Use one of the methods listed in `docs/chemistry-field-sheet-ingest.md`, section 2. |
| `is longer than 5 characters` (CollectedBy) | Use the short code. Put full names in the `Staff` column. |
| `non-numeric reading(s)` | A reading cell holds text. Enter a number, or clear the cell. |
| `Missing Time` | Fill in the date and time the readings were taken. |
| `Time ... is not a recognizable date and time` | Retype it with the date and the time, for example `2026-09-25 10:45`. A time on its own isn't enough. |
| `its ChemistrySampleInfo row N failed: ...` | Nothing is wrong with this FieldParameters row itself. Its sample's row (row N) failed, for the reason given. Fix row N, and this row loads with it. |
| `no sample ...` (FieldParameters) | Add a matching row on the ChemistrySampleInfo tab, or fix the `SamplePointID`. |
| `... was collected on ..., but these readings were taken on ...` | The FieldParameters `Time` is on a different day from the ChemistrySampleInfo `CollectionDate`. Check both against the crew's notes and correct the wrong one. Different times on the same day are fine. |

After the fixes, **download a fresh copy** (Step 4, including the rename),
then start again from Step 8. Occasionally a fixed row turns up a new
problem. A row stops at its first problem, so a check further along only runs
once that one is fixed. For example, once a missing date is filled in, the row
can fail because its letter is already used by another sample.

A first run often turns up a few problems, such as blank dates. That's
expected.

### 9c. Load the rest while rows are fixed (optional)

Fixing rows can take a while, for example if you need to ask the crew. You
don't have to hold everything else back:

1. Do Step 10 with `<file-name>_loadable.xlsx` in place of
   `<file-name>.xlsx`.
2. Once the rows are fixed in the Google Sheet, download a fresh copy and
   start again from Step 8. Rows already loaded show as **samples matched**
   and **readings skipped**. Only the fixed rows are new.

The loadable copy blanks only the rows that failed. If a sample's
FieldParameters row failed but its ChemistrySampleInfo row didn't, the sample
loads now **without its readings**, and they're added when the fixed row
loads.

Check the date errors first (`... was collected on ..., but these readings
were taken on ...`). If the wrong date is the sample's `CollectionDate`
rather than the readings' `Time`, fix it in the Google Sheet and download a
fresh copy before loading anything. Once the sample is saved, a fixed sheet
can't change its date, and the next run stops with `already belongs to the
... visit`.

## Step 10. Do the real run

This is the practice-run command without `--dry-run` and the two report
files:

```bash
uv run oco water-chemistry field-upload --file ~/Downloads/<file-name>.xlsx
```

The top line should say `SUCCESS`. Just under it, **Database** names the
database the data was saved to. Check it's the one you meant. The summary
numbers should match what the practice run reported, and a line starting
`Archived` tells you the copy of the file was saved.

If you see a **WARNINGS** section, the data still loaded. Warnings point out
things a person should look at, such as the sheet disagreeing with a value
already in the database. The database value is always kept. Copy the
warnings and send them to the Data Services lead.

## Step 11. Check it worked

Run the real command from Step 10 a second time, on the same file:

```bash
uv run oco water-chemistry field-upload --file ~/Downloads/<file-name>.xlsx
```

This time **samples created** and **readings loaded** should both be `0`, and
the readings from the first run show as skipped. That confirms the data is
saved, and that running the ingest again doesn't duplicate it.

## Step 12. Finish up

1. Go to the terminal window running the proxy and press `Ctrl` + `C` to stop
   it.
2. Close both terminal windows.
3. Delete `<file-name>.xlsx` from Downloads, along with
   `<file-name>_loadable.xlsx` if you made one. The ingest kept its own copy
   in Step 10, and next time you'll download a fresh one. Keep
   `<file-name>_failed_rows.xlsx` until every row in it is fixed and loaded.

You don't need to undo the `.env` change. It'll be ready for next time. Just
check `POSTGRES_DB` again before every run.

---

## If something goes wrong

| You see | What it means | What to do |
|---|---|---|
| `This app tried to access sensitive info in your Google Account` | The sign-in command had extra Drive or Sheets permissions added. | Run the Step 3 command exactly as shown. |
| `No raw zone configured ...` | `.env` doesn't say where to keep the copy. | Repeat Step 5a, and remember to save the file. |
| `No such file or directory` naming `<file-name>.xlsx` | The file isn't in Downloads under that exact name. | Repeat Step 4, including the rename. |
| `Found neither a ChemistrySampleInfo nor a FieldParameters tab` | The file isn't the field spreadsheet, or its tabs were renamed. | Download the right spreadsheet, or ask the sheet's keeper about the tab names. |
| `Could not connect to the database`, `connection refused`, or the command hangs | The proxy isn't running. | Repeat Step 6, then Step 7. |
| `command not found: uv` or `command not found: gcloud` | The tool isn't installed. | Ask the Data Services lead for help installing it. |

If anything else goes wrong, copy the whole terminal output. Send it to the
Data Services lead, with a note about which step you were on.

## What happens when a cell is left blank

Some columns have to be filled in, or the run stops. Others can be left
blank, and the ingest either fills in a default or leaves that detail
empty. A row where **every** cell is blank is ignored.

### ChemistrySampleInfo tab

| Column | If you leave it blank |
|---|---|
| `WellPointID` | The ingest takes the well from `SamplePointID` (`RA-116A` means well `RA-116`). If both are blank, the run stops. |
| `SamplePointID` | **The run stops.** The field sample ID is how the readings and the lab results find this sample. It also stops if the ID has no letter (`WL-0264` rather than `WL-0264A`). |
| `CollectionDate` | **The run stops.** One field sample is one visit on one day, and the date is checked against the readings and any sample already saved under that ID. |
| `AnalysisAgency` | Saved as `NMBGMR`. |
| `SampleType` | Left empty. |
| `CollectionMethod` | Left empty. |
| `CollectedBy` | Left empty. |
| `Data Source` | Left empty. |
| `Sample Notes` | Left empty, or holds only the `Staff:` line if `Staff` is filled in. |
| `Staff` | Nothing is recorded about who was on site. No other column holds that. |

### FieldParameters tab

| Column | If you leave it blank |
|---|---|
| `SamplePointID` | **The run stops.** It's the only link between the readings and their sample. |
| `Time` | **The run stops.** The date in `Time` is how the ingest checks the readings belong to this visit. |
| `pHf`, `T (C)`, `CF (uS/cm)`, `DO (mg/L)`, `ORP (mV)`, `Discharge rate (gpm)` | That one reading isn't saved. The rest of the row still loads. |

### Filling in a blank later

When a row matches a sample that's already saved, the ingest only fills in
details that are still empty in the database. It never erases anything. So if
a cell was blank on an earlier run, fill it in on the sheet and run the
ingest again, and the new value is saved. That works for readings too.

A value that was already saved doesn't change, even if someone edits it on
the sheet:

- An edited ChemistrySampleInfo detail keeps the database value and shows up
  under **WARNINGS**. Send those to the Data Services lead.
- An edited reading keeps the saved value and shows up under **SKIPPED**,
  like any reading that was already loaded. The run gives no other sign that
  the number changed, so tell the Data Services lead if a reading needs
  correcting.

`AnalysisAgency` is the exception. A blank there counts as `NMBGMR`, so if
the database holds a different agency for that visit, you'll see a warning
even though nobody changed anything.

## How this connects to the lab results

The lab results arrive separately, in a LIMS workbook, and are loaded with a
different command (`docs/chemistry-ingestion-runbook.md`). They find this
sample by its field sample ID, which the lab copies from the chain of
custody. Either load can go first, and the sample ends up as one record.

That only works if the letter on the sheet is the letter on the chain of
custody. If the two disagree, the lab results stop at their own load, or
attach to a different sample. Before changing a letter to get past an error
in Step 9, check which letter the crew wrote on the chain of custody, and tell
whoever loads the lab results about the change.
