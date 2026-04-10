# Scoped Transfer Guide

This guide explains how to use `oco scoped-transfer` to run a targeted legacy data transfer for one or more `PointID` values.

It is written for a beginner who may not use CLI tools often.

## What `scoped-transfer` does

`oco scoped-transfer` imports only the records related to the `PointID` values you request.

This is useful when you want to:

- test a single well or site
- rerun a small transfer after fixing an issue
- avoid running a full legacy transfer
- inspect what would be imported before writing data

## Before you start

Run commands from the project root.

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Load environment variables from `.env`:

```bash
set -a
source .env
set +a
```

If you skip these steps, the CLI may fail because it cannot find the right Python packages or database settings.

If `oco` is not available in your shell, you can run the same command with:

```bash
python -m cli.cli scoped-transfer --pointid SM-0001
```

The examples below use `oco`, but both forms are valid.

## Basic command

Transfer one `PointID`:

```bash
oco scoped-transfer --pointid SM-0001
```

Transfer more than one `PointID`:

```bash
oco scoped-transfer --pointid SM-0001 --pointid SM-0002
```

The command will:

1. validate your requested `PointID` values
2. determine which transfer families need to run
3. run the scoped transfer
4. print a final summary

## What you will see

At the start of the run, the CLI prints a short status message so you know it is working:

```text
Starting scoped transfer for PointIDs: SM-0001
Validating requested scope and preparing execution...
```

At the end, it prints a scoped transfer summary like this:

```text
[SCOPED TRANSFER]
========================================================================
Requested PointIDs: SM-0001
Selected families: wells, contacts, permissions, waterlevels, ...

FAMILY SUMMARY
  wells                        completed  rows=1
  contacts                     completed  rows=1
  permissions                  completed  rows=1  created=2  skipped_existing=0
  waterlevels                  completed  rows=38
```

## Understanding the summary

Each line in `FAMILY SUMMARY` is a transfer family.

Common statuses:

- `completed`: the family ran and found matching data
- `planned`: shown during `--dry-run`; the family would run
- `no-op`: the family had no matching data for your requested `PointID`

Common fields:

- `rows=...`: number of matching source rows for that family
- `created=...`: number of records created or updated by that step
- `skipped_existing=...`: records skipped because they already existed

`no-op` is normal. It does not mean the run failed.

## What are "families"?

In `scoped-transfer`, a **family** is a group of related records that are imported together.

You will see family names:

- in the `Selected families` line
- in the `FAMILY SUMMARY` output
- when using `--only`
- when using `--skip`

Think of a family as a transfer step for one kind of data.

For example:

- `wells` imports the main well/site record
- `contacts` imports owner or related contact records
- `waterlevels` imports manual water-level measurements

Not every `PointID` has data in every family. That is why many families may show `no-op` in the summary.

### Family list

| Family | What it means |
|---|---|
| `wells` | Main water well records and core well details. |
| `springs` | Spring site records. |
| `perennial-streams` | Perennial stream site records. |
| `ephemeral-streams` | Ephemeral stream site records. |
| `met-stations` | Meteorological station site records. |
| `rock-sample-locations` | Rock sample site records. |
| `diversion-of-surface-water` | Surface-water diversion site records. |
| `lake-pond-reservoir` | Lake, pond, or reservoir site records. |
| `soil-gas-sample-locations` | Soil gas sample site records. |
| `other-site-types` | Other site records that do not fit the main site groups. |
| `outfall-wastewater-return-flow` | Outfall or wastewater return flow site records. |
| `screens` | Well screen records linked to wells. |
| `contacts` | Owner or related contact records linked to a site. |
| `permissions` | Permission history such as monitoring or sampling permission. |
| `waterlevels` | Manual groundwater level measurements. |
| `link-ids` | Alternate IDs linked to a site, such as OSE or PLSS-style identifiers. |
| `groups` | Project or grouping records that associate sites together. |
| `assets` | Site images or files, such as photos. |
| `associated-data` | Additional attached data records related to a site. |
| `hydraulics-data` | Hydraulics test or aquifer property data linked to a well. |
| `chemistry-sampleinfo` | Chemistry sample header records for water-quality sampling. |
| `field-parameters` | Field-measured chemistry values linked to a chemistry sample. |
| `major-chemistry` | Major ion chemistry results linked to a chemistry sample. |
| `radionuclides` | Radionuclide chemistry results linked to a chemistry sample. |
| `minor-trace-chemistry` | Minor and trace chemistry results linked to a chemistry sample. |
| `sensors` | Sensor and deployment records for monitoring equipment. |
| `pressure` | Continuous pressure-based water-level records. |
| `acoustic` | Continuous acoustic water-level records. |
| `pressure-daily` | Daily summarized pressure-based water-level records. |
| `ngwmn-views` | NGWMN legacy view records related to well construction and water levels. |
| `nma-stratigraphy` | Legacy stratigraphy records. |
| `surface-water-data` | Surface-water measurement records. |
| `surface-water-photos` | Surface-water photo assets. |
| `weather-data` | Weather measurement records. |
| `weather-photos` | Weather photo assets. |
| `soil-rock-results` | Soil or rock analysis result records. |
| `cleanup-locations` | A cleanup step that fills in location fields such as state, county, or quad name after transfer. |

## Dry run mode

Use `--dry-run` to see what would run without writing to the database.

Example:

```bash
oco scoped-transfer --pointid SM-0001 --dry-run
```

This is the safest way to check your scope before making changes.

## Limiting the run to specific families

Use `--only` to run just a few transfer families.

Example: run only wells

```bash
oco scoped-transfer --pointid SM-0001 --only wells
```

Example: run only water levels

```bash
oco scoped-transfer --pointid SM-0001 --only waterlevels
```

Example: run only chemistry sample info

```bash
oco scoped-transfer --pointid SM-0001 --only chemistry-sampleinfo
```

Important:

- some families depend on others
- the CLI may automatically add prerequisite families

For example, if you request `field-parameters`, the CLI may also add `wells` and `chemistry-sampleinfo`.

You will see that in the final output as:

```text
Auto-added prerequisites: chemistry-sampleinfo, wells
```

## Skipping families

Use `--skip` to leave out families you do not want to run.

Example:

```bash
oco scoped-transfer --pointid SM-0001 --skip assets --skip weather-photos
```

This is useful when:

- you are narrowing a test run
- a family is known to be irrelevant for your target
- you want faster iteration while debugging

## JSON output

Use `--output json` if you want machine-readable output.

Example:

```bash
oco scoped-transfer --pointid SM-0001 --dry-run --output json
```

This is useful for scripting or saving results to another tool.

When JSON output is enabled, the CLI prints JSON instead of the human summary.

## Common examples

### Example 1: Preview a transfer for one well

```bash
oco scoped-transfer --pointid SM-0001 --dry-run
```

Use this first when you are not sure what data exists.

### Example 2: Run the full scoped transfer for one well

```bash
oco scoped-transfer --pointid SM-0001
```

Use this after the dry run looks correct.

### Example 3: Re-run only water levels for one well

```bash
oco scoped-transfer --pointid SM-0001 --only waterlevels
```

Use this when you are debugging water-level behavior.

### Example 4: Run wells and contacts only

```bash
oco scoped-transfer --pointid SM-0001 --only wells --only contacts
```

Use this when you want a smaller targeted import.

### Example 5: Run two PointIDs together

```bash
oco scoped-transfer --pointid SM-0001 --pointid SM-0002
```

Use this when the same test or fix should be checked for more than one site.

## Troubleshooting

### The command says a `PointID` was not found

That usually means the requested `PointID` does not appear in the source data for the selected scope.

Try:

- checking for typos
- confirming letter case and punctuation
- running a dry run again

### A family shows `no-op`

That means the family had no matching rows for the requested `PointID`.

This is expected for many families. Not every site has data in every table.

### The command finishes but creates less than expected

Check:

- whether you used `--only` or `--skip`
- whether prerequisites were auto-added
- the `rows=...` counts in the summary
- whether data may already exist and be counted as `skipped_existing`


## Related files

Main CLI command:

- `cli/cli.py`

Scoped transfer service:

- `services/scoped_transfer.py`

## Quick reference

```bash
# Basic run
oco scoped-transfer --pointid SM-0001

# Dry run
oco scoped-transfer --pointid SM-0001 --dry-run

# Only one family
oco scoped-transfer --pointid SM-0001 --only waterlevels

# Skip one family
oco scoped-transfer --pointid SM-0001 --skip assets

# JSON output
oco scoped-transfer --pointid SM-0001 --output json
```
