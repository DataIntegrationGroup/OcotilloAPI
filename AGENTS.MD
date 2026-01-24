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

  
## 7. Running pytest safely
- Activate the repo virtualenv before testing: `source .venv/bin/activate` from the project root so all
  dependencies (sqlalchemy, fastapi, etc.) are available.
- Load environment variables from `.env` so pytest sees the same DB creds the app uses. For quick shells:
  `set -a; source .env; set +a`, or use `ENV_FILE=.env pytest ...` with `python-dotenv` installed.
- Many tests expect a running Postgres bound to the vars in `.env`; confirm `POSTGRES_*` values point to the
  right instance before running destructive suites.
- When done, `deactivate` to exit the venv and avoid polluting other shells.

Following this playbook keeps ETL runs measured in seconds/minutes instead of hours. EOF
