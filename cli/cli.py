# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
from pathlib import Path

import typer
from dotenv import load_dotenv

load_dotenv()

cli = typer.Typer(help="Command line interface for managing the application.")
water_levels = typer.Typer(help="Water-level utilities")
data_migrations = typer.Typer(help="Data migration utilities")
cli.add_typer(water_levels, name="water-levels")
cli.add_typer(data_migrations, name="data-migrations")


@cli.command("initialize-lexicon")
def initialize_lexicon():
    from core.initializers import init_lexicon

    init_lexicon()


@cli.command("associate-assets")
def associate_assets_command(
    root_directory: str = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    )
):
    from cli.service_adapter import associate_assets

    associate_assets(root_directory)


@cli.command("well-inventory-csv")
def well_inventory_csv(
    file_path: str = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    )
):
    """
    parse and upload a csv to database
    """
    # TODO: use the same helper function used by api to parse and upload a WI csv
    from cli.service_adapter import well_inventory_csv

    well_inventory_csv(file_path)


@water_levels.command("bulk-upload")
def water_levels_bulk_upload(
    file_path: str = typer.Option(
        ...,
        "--file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to CSV file containing water level rows",
    ),
    output_format: str | None = typer.Option(
        None,
        "--output",
        case_sensitive=False,
        help="Optional output format",
    ),
):
    """
    parse and upload a csv
    """
    # TODO: use the same helper function used by api to parse and upload a WL csv
    from cli.service_adapter import water_levels_csv

    pretty_json = (output_format or "").lower() == "json"
    water_levels_csv(file_path, pretty_json=pretty_json)


@data_migrations.command("list")
def data_migrations_list():
    from data_migrations.registry import list_migrations

    migrations = list_migrations()
    if not migrations:
        typer.echo("No data migrations registered.")
        return
    for migration in migrations:
        repeatable = " (repeatable)" if migration.is_repeatable else ""
        typer.echo(f"{migration.id}: {migration.name}{repeatable}")


@data_migrations.command("status")
def data_migrations_status():
    from db.engine import session_ctx
    from data_migrations.runner import get_status

    with session_ctx() as session:
        statuses = get_status(session)
    if not statuses:
        typer.echo("No data migrations registered.")
        return
    for status in statuses:
        last_applied = (
            status.last_applied_at.isoformat() if status.last_applied_at else "never"
        )
        typer.echo(
            f"{status.id}: applied {status.applied_count} time(s), last={last_applied}"
        )


@data_migrations.command("run")
def data_migrations_run(
    migration_id: str = typer.Argument(...),
    force: bool = typer.Option(
        False, "--force", help="Re-run even if already applied."
    ),
):
    from db.engine import session_ctx
    from data_migrations.runner import run_migration_by_id

    with session_ctx() as session:
        ran = run_migration_by_id(session, migration_id, force=force)
    typer.echo("applied" if ran else "skipped")


@data_migrations.command("run-all")
def data_migrations_run_all(
    include_repeatable: bool = typer.Option(
        False,
        "--include-repeatable/--exclude-repeatable",
        help="Whether to include repeatable migrations.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run non-repeatable migrations."
    ),
):
    from db.engine import session_ctx
    from data_migrations.runner import run_all

    with session_ctx() as session:
        ran = run_all(session, include_repeatable=include_repeatable, force=force)
    typer.echo(f"applied {len(ran)} migration(s)")


@cli.command("alembic-upgrade-and-data")
def alembic_upgrade_and_data(
    revision: str = typer.Argument("head"),
    include_repeatable: bool = typer.Option(
        False,
        "--include-repeatable/--exclude-repeatable",
        help="Whether to include repeatable migrations.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run non-repeatable migrations."
    ),
):
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from db.engine import engine, session_ctx
    from data_migrations.runner import run_all

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    command.upgrade(cfg, revision)

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        heads = context.get_current_heads()
        script = ScriptDirectory.from_config(cfg)
        applied_revisions: set[str] = set()
        for head in heads:
            for rev in script.iterate_revisions(head, "base"):
                applied_revisions.add(rev.revision)

    with session_ctx() as session:
        ran = run_all(
            session,
            include_repeatable=include_repeatable,
            force=force,
            allowed_alembic_revisions=applied_revisions,
        )
    typer.echo(f"applied {len(ran)} migration(s)")


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
