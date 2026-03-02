# Transfers

This directory contains legacy-to-target ETL transfer logic.

## Main orchestration

- `transfers/transfer.py`

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
