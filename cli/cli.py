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
import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """Command line interface for managing the application."""
    pass


@cli.command()
def initialize_lexicon():
    from core.initializers import init_lexicon

    init_lexicon()


@cli.command()
@click.argument(
    "root_directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
)
def associate_assets_command(root_directory: str):
    from cli.service_adapter import associate_assets

    associate_assets(root_directory)


@cli.command()
@click.argument(
    "file_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
def well_inventory_csv(file_path: str):
    """
    parse and upload a csv to database
    """
    # TODO: use the same helper function used by api to parse and upload a WI csv
    from cli.service_adapter import well_inventory_csv

    well_inventory_csv(file_path)


@cli.group()
def water_levels():
    """Water-level utilities"""
    pass


@water_levels.command("bulk-upload")
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    required=True,
    help="Path to CSV file containing water level rows",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["json"], case_sensitive=False),
    default=None,
    help="Optional output format",
)
def water_levels_bulk_upload(file_path: str, output_format: str | None):
    """
    parse and upload a csv
    """
    from cli.service_adapter import water_levels_csv

    pretty_json = (output_format or "").lower() == "json"
    water_levels_csv(file_path, pretty_json=pretty_json)


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
