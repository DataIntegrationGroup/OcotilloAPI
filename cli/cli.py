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
from dotenv import load_dotenv

load_dotenv()

import click


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


@cli.command()
@click.argument(
    "file_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
def waterlevels_csv(file_path: str):
    """
    parse and upload a csv
    """
    # TODO: use the same helper function used by api to parse and upload a WL csv
    from cli.service_adapter import water_level_csv

    water_level_csv(file_path)


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
