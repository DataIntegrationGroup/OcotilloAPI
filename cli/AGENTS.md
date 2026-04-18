# AGENTS: CLI Typer Pattern

Use the normal Typer layout in this directory:

- Keep `cli/cli.py` as the root app and subcommand registry only.
- Put non-trivial command groups in their own module, named after the mounted command group, such as `cli/aem_ingest.py`.
- Mount subcommand groups from `cli/cli.py` with `cli.add_typer(...)` instead of inlining them into the root file.

Implementation rules:

- Keep command functions thin; move business logic into `services/`, `transfers/`, or other domain modules.
- Put command-group-local helpers in the same command module when they are only used there.
- Load `.env` and shared CLI-wide environment defaults in `cli/cli.py`, not in each subcommand module.
- Prefer Typer-native argument and option declarations and keep help text concrete.
- When adding a new command group, update `cli/README.md` so the docs match the mounted commands.

Naming guidance:

- Use filenames that match the mounted command group when practical.
- Avoid generic shim modules whose only purpose is to re-export another Typer app.
