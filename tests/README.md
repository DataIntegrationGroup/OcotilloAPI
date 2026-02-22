# Tests

This directory contains automated tests (unit, integration, transfer, and API behavior).

## Layout

- `tests/unit/`: focused unit tests
- `tests/integration/`: cross-component tests
- `tests/transfers/`: transfer-focused tests
- `tests/features/`: BDD-style feature tests

## Running tests

From repo root:

```bash
source .venv/bin/activate
set -a; source .env; set +a
pytest -q
```

Run a subset:

```bash
pytest -q tests/transfers
```

## Notes

- Many tests depend on database settings from `.env`.
- Keep tests deterministic and idempotent where possible.
