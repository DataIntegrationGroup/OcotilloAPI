# CLI

This directory contains Typer-based command entrypoints for operational and migration workflows.

## Main entrypoint

- `cli/cli.py`

Run commands from repo root:

```bash
source .venv/bin/activate
python -m cli.cli --help
```

## Common commands

- `python -m cli.cli restore-local-db path/to/dump.sql`
- `python -m cli.cli restore-local-db gs://ocotillo/sql-exports/latest.sql.gz`
- `python -m cli.cli transfer-results`
- `python -m cli.cli compare-duplicated-welldata`
- `python -m cli.cli alembic-upgrade-and-data`

## Notes

- CLI logging is written to `cli/logs/`.
- Keep CLI commands thin; move heavy logic into service/transfer modules.
