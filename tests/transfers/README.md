# Transfer tests

Tests for the legacy migration scripts in `transfers/` — the deprecated
NM_Aquifer (AMPAPI) and NM_Wells drivers.

## Excluded from CI

`.github/workflows/tests.yml` runs pytest with `--ignore=tests/transfers`, so
nothing in this directory gates a pull request. The transfer scripts they cover
are deprecated and run by hand against SQL Server; `transfers/*` is likewise
omitted from the coverage total in `pyproject.toml`.

Put new tests here only if they exercise `transfers/`. Tests for the
`NMA_*`/`NMW_*` ORM models (`db/nma_legacy.py`, `db/nmw_legacy.py`) belong in
`tests/` proper — those tables are still read by live API routes, so they stay
in CI.

## Running them

From the repo root, against the `ocotilloapi_test` database:

```bash
uv run pytest tests/transfers
```
