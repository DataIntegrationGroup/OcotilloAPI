# AGENTS: High-Volume Transfer Playbook

This repo pushes millions of legacy rows through SQLAlchemy. When Codex or any other agent has to work on
these transfers, keep the following rules in mind to avoid hour-long runs:

## 1. Skip ORM object construction once volume climbs
- **Do not call `session.bulk_save_objects`** for high frequency tables (e.g., transducer observations,
  water-levels, chemistry results). It still instantiates every mapped class and kills throughput.
- Instead, build plain dictionaries/tuples and call `session.execute(insert(Model), data)` or the newer
  SQLAlchemy `session.execute(stmt, execution_options={"synchronize_session": False})`.
- If validation is required (Pydantic models, bound schemas), validate first and dump to dicts before the
  Core insert.

  
## 2. Running pytest safely
- Activate the repo virtualenv before testing: `source .venv/bin/activate` from the project root so all
  dependencies (sqlalchemy, fastapi, etc.) are available.
- Load environment variables from `.env` so pytest sees the same DB creds the app uses. For quick shells:
  `set -a; source .env; set +a`, or use `ENV_FILE=.env pytest ...` with `python-dotenv` installed.
- Many tests expect a running Postgres bound to the vars in `.env`; confirm `POSTGRES_*` values point to the
  right instance before running destructive suites.
- When done, `deactivate` to exit the venv and avoid polluting other shells.

## 3. Data migrations must be idempotent
- Data migrations should be safe to re-run without creating duplicate rows or corrupting data.
- Use upserts or duplicate checks and update source fields only after successful inserts.

## 4. Do a cleanup and code analysis pass after code changes
- After completing any code modification, do a cleanup and code analysis pass adjusted to the size and risk of the change.
- Check for obvious regressions, dead code, inconsistent config/docs/tests, and adjacent issues introduced by the change.
- Fix any concrete issues you find in that pass instead of stopping at implementation.
- After code cleanup, run `black` on the touched Python files and run `flake8` on the touched Python files before wrapping up.
- Run targeted validation for the modified area after cleanup; use broader validation when the change affects shared boot, deploy, or database paths.

Following this playbook keeps ETL runs measured in seconds/minutes instead of hours. EOF

## Activate python venv
Always use `source .venv/bin/activate` to activate the venv running python
