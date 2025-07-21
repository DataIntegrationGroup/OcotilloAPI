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
from core.app import init_lexicon
from db.engine import session_ctx



from migration.migration2 import migrate_wells, migrate_water_levels


def wells():
    with session_ctx() as sess:
        migrate_wells(sess, 1000)

def waterlevels():
    with session_ctx() as sess:
        migrate_water_levels(sess, 800)

@click.command()
def initialize_lexicon():
    init_lexicon()


if __name__ == '__main__':
    waterlevels()

# ============= EOF =============================================
