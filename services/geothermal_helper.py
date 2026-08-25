# ===============================================================================
# Copyright 2026 ross
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
"""Read-side helpers for geothermal wells.

TEMPORARY SOURCE: these read straight from the legacy NM_Wells staging mirror
(``db/nmw_legacy.py``). A "geothermal well" is a ``NMW_WellHeaders`` row whose
``GthrmExist`` flag is set. Location (lat/long/county/state) is joined from
``NMW_WellLocations`` on ``WellDataID``.

Once the NM_Wells -> Ocotillo transform exists, swap the source to the ``thing``
table and populate ``thing_id`` on the response. Keeping the DB access behind
this helper is what makes that swap a one-file change.
"""

from uuid import UUID

from sqlalchemy import or_, select

from db.nmw_legacy import NMW_WellHeaders, NMW_WellLocations
from schemas.geothermal import GeothermalWellResponse


def _base_query():
    """Header rows flagged geothermal, left-joined to their location."""
    return (
        select(NMW_WellHeaders, NMW_WellLocations)
        .outerjoin(
            NMW_WellLocations,
            NMW_WellHeaders.well_data_id == NMW_WellLocations.well_data_id,
        )
        .where(NMW_WellHeaders.gthrm_exist == 1)
    )


def _to_response(header: NMW_WellHeaders, location: NMW_WellLocations | None):
    return GeothermalWellResponse(
        well_data_id=header.well_data_id,
        thing_id=None,  # not yet linked; see NM_Wells -> thing transform
        api=header.api,
        name=header.cur_well_nam,
        well_number=header.cur_well_num,
        well_class=header.well_class,
        well_type=header.well_type,
        status=header.cur_status,
        operator=header.cur_operatr,
        owner=header.cur_owner,
        total_depth=header.total_depth,
        completion_date=header.compl_date,
        has_geothermal_data=bool(header.gthrm_exist),
        county=location.county if location else None,
        state=location.state if location else None,
        latitude=location.lat_dd83 if location else None,
        longitude=location.long_dd83 if location else None,
    )


# Columns a free-text term is matched against. Everything a person might use
# to refer to a well: what it is called, how it is identified, and who ran it.
_SEARCH_COLUMNS = (
    NMW_WellHeaders.cur_well_nam,
    NMW_WellHeaders.api,
    NMW_WellHeaders.cur_well_num,
    NMW_WellHeaders.cur_operatr,
    NMW_WellLocations.county,
)


def _search_clauses(q: str):
    """One clause per whitespace-separated word, each matching any column.

    Words are ANDed so that adding a word narrows the result — "jemez 1"
    returns a subset of "jemez" rather than everything matching either. ILIKE
    wildcards in the term are escaped so a stray % does not silently widen the
    search to everything.
    """
    clauses = []
    for word in q.split():
        pattern = "%{}%".format(
            word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        clauses.append(
            or_(*[column.ilike(pattern, escape="\\") for column in _SEARCH_COLUMNS])
        )
    return clauses


def get_geothermal_wells_query(
    county: str | None = None,
    name_contains: str | None = None,
    q: str | None = None,
):
    """Build the list query; returned as a SQLAlchemy select for pagination."""
    sql = _base_query()
    if county:
        sql = sql.where(NMW_WellLocations.county == county)
    if name_contains:
        sql = sql.where(NMW_WellHeaders.cur_well_nam.ilike(f"%{name_contains}%"))
    if q and q.strip():
        for clause in _search_clauses(q.strip()):
            sql = sql.where(clause)
    return sql.order_by(NMW_WellHeaders.cur_well_nam)


def geothermal_wells_transformer(rows) -> list[dict]:
    """Map (header, location) Rows -> GeothermalWellResponse dicts."""
    return [_to_response(header, location).model_dump() for header, location in rows]


def get_geothermal_well_by_id(session, well_data_id: UUID):
    """Return a single geothermal well by legacy WellDataID, or None."""
    row = session.execute(
        _base_query().where(NMW_WellHeaders.well_data_id == well_data_id)
    ).first()
    if row is None:
        return None
    header, location = row
    return _to_response(header, location)


# ============= EOF =============================================
