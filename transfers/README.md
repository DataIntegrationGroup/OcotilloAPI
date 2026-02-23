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
