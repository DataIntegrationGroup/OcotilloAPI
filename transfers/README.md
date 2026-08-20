# Transfers

This directory contains legacy-to-target ETL transfer logic.

## Status: deprecated

Both legacy migration drivers are frozen. Do not add new migrations to either:

- `transfers/transfer.py` -- the NM_Aquifer (AMPAPI, SQL Server) driver.
- `transfers/transfer_geothermal.py` -- the NM_Wells (geothermal) driver, plus
  its `nmw_mirror_transfer.py`, `nmw_sql_dump.py`, and `export_nmw_csvs.py`
  supporting modules.

Their top-level entry points raise `DeprecationWarning`. They are kept runnable
because the tables they populate (`NMA_*`, `NMW_*`) are still read by live API
routes, so backfills and re-runs must remain possible -- but they receive no new
features.

Consequently their tests live in `tests/transfers/` and do **not** gate CI
(`.github/workflows/tests.yml` runs pytest with `--ignore=tests/transfers`), and
`transfers/*` is omitted from the coverage total in `pyproject.toml`. Run them by
hand with `uv run pytest tests/transfers`.

Still live and *not* deprecated:

- `services/scoped_transfer.py` and the `oco scoped-transfer` command, which
  import the individual NM_Aquifer transferers directly.
- `transfers/seed_geothermal.py`, a dev/test seeder that generates fake data
  rather than reading a legacy source.

## Main orchestration

- `transfers/transfer.py` (deprecated)

## Important supporting modules

- `transfers/transferer.py`: base transfer patterns
- `transfers/util.py`: shared parsing/mapping helpers
- `transfers/logger.py`: transfer logging
- `transfers/metrics.py`: metrics capture

## Performance rules

For high-volume tables, prefer Core batch inserts:

- `session.execute(insert(Model), rows)`

Avoid ORM-heavy per-row object construction for bulk workloads.

## Outputs

- Logs: `transfers/logs/`
- Metrics: `transfers/metrics/`

## Transfer Auditing CLI

Use the transfer-auditing CLI to compare each source CSV against the current destination Postgres table.

### Run

```bash
source .venv/bin/activate
set -a; source .env; set +a
oco transfer-results
```

### Useful options

```bash
oco transfer-results --sample-limit 5
oco transfer-results --summary-path transfers/metrics/transfer_results_summary.md
```

- `--sample-limit`: limits sampled key details retained internally per transfer result.
- `--summary-path`: path to the markdown report.

If `oco` is not on your PATH, use:

```bash
python -m cli.cli transfer-results --sample-limit 5
```

### Output

Default report file:

- `transfers/metrics/transfer_results_summary.md`

Summary columns:

- `Source Rows`: raw row count in the source CSV.
- `Agreed Rows`: rows considered in-scope by transfer rules/toggles.
- `Dest Rows`: current row count in destination table/model.
- `Missing Agreed`: `Agreed Rows - Dest Rows` (positive means destination is short vs agreed source rows).
