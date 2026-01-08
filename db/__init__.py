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

# import all models from db package so that Alembic can discover them

from db.base import *
from db.base import Base

from db.analysis_method import *
from db.asset import *
from db.collabnet import *
from db.contact import *
from db.deployment import *
from db.geochronology import *
from db.geothermal import *
from db.field import *
from db.group import *
from db.lexicon import *
from db.location import *
from db.notes import *
from db.observation import *
from db.parameter import *
from db.permission_history import *
from db.publication import *
from db.regulatory_limit import *
from db.sample import *
from db.sensor import *
from db.status_history import *
from db.thing import *
from db.transducer import *
from db.measuring_point_history import *
from db.data_provenance import *
from db.aquifer_system import *
from db.geologic_formation import *
from db.thing_aquifer_association import *
from db.thing_geologic_formation_association import *
from db.aquifer_type import *
from db.nma_legacy import *
from db.minor_trace_chemistry import *

from sqlalchemy import (
    func,
    desc,
    cast,
    Text,
)
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy_searchable import (
    inspect_search_vectors,
    search_manager,
)
from sqlalchemy.orm import configure_mappers

configure_mappers()


def search(query, search_query, vector=None, regconfig=None, sort=True, limit=None):
    if not search_query.strip():
        return query

    if vector is None:
        entity = query.column_descriptions[0]["entity"]
        search_vectors = inspect_search_vectors(entity)
        vector = search_vectors[0]

    if regconfig is None:
        regconfig = search_manager.options["regconfig"]

    query = query.filter(
        vector.op("@@")(
            func.parse_websearch(cast(regconfig, REGCONFIG), cast(search_query, Text))
        )
    )
    if sort:
        query = query.order_by(
            desc(
                func.ts_rank_cd(vector, func.parse_websearch(cast(search_query, Text)))
            )
        )

    if limit:
        query = query.limit(limit)

    return query.params(term=search_query)


# ============= EOF =============================================
