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
import shapefile
from shapely.errors import GEOSException
from shapely.io import from_geojson

import constants
from db.thing import Thing
from db.group import GroupThingAssociation, Group
from db.location import Location, LocationThingAssociation
from geoalchemy2.functions import ST_GeomFromText, ST_Within, ST_AsGeoJSON
from geoalchemy2.shape import to_shape
from shapely.wkt import loads as wkt_loads
from sqlalchemy import Select, select
from sqlalchemy.orm import aliased
from sqlalchemy import func


def get_thing_features(
    session, thing_type: list | str | None, group: str | int | None
) -> list:
    # sql = (
    #     select(Thing, ST_AsGeoJSON(Location.point).label("geojson"))
    #     .join(LocationThingAssociation, Thing.id == LocationThingAssociation.thing_id)
    #     .join(Location, LocationThingAssociation.location_id == Location.id)
    # )

    # selection_args = [Thing, ST_AsGeoJSON(Location.point).label("geojson")]
    # if thing_type == "well":
    #     selection_args.append(WellThing)
    # elif thing_type == "spring":
    #     selection_args.append(SpringThing)

    # Subquery: get the latest association for each thing (optionally only active)
    lta_alias = aliased(LocationThingAssociation)

    latest_assoc = (
        select(
            LocationThingAssociation.thing_id,
            func.max(LocationThingAssociation.effective_start).label("max_start"),
        )
        .where(
            LocationThingAssociation.effective_end == None
        )  # Only active, remove if you want most recent regardless of end
        .group_by(LocationThingAssociation.thing_id)
        .subquery()
    )

    sql = (
        select(Thing, ST_AsGeoJSON(Location.point).label("geojson"), Location.elevation)
        .join(lta_alias, Thing.id == lta_alias.thing_id)
        .join(Location, lta_alias.location_id == Location.id)
        .join(
            latest_assoc,
            (latest_assoc.c.thing_id == lta_alias.thing_id)
            & (latest_assoc.c.max_start == lta_alias.effective_start),
        )
    )

    if thing_type:
        if isinstance(thing_type, str):
            thing_type = thing_type.lower()
            sql = sql.where(Thing.thing_type == thing_type)
        elif isinstance(thing_type, list):
            thing_type = [t.lower() for t in thing_type]
            sql = sql.where(Thing.thing_type.in_(thing_type))
        else:
            raise ValueError("thing_type must be a string or a list of strings")

    if group:
        sql = sql.join(GroupThingAssociation).join(Group)
        if isinstance(group, str):
            sql = sql.where(Group.name == group)
        else:
            sql = sql.where(Group.id == group)

    # unique needs to be invoked to prevent duplicates from eager loading
    return session.execute(sql).unique().all()


def create_shapefile(things: list, filename: str = "things.shp") -> None:
    # Create a point shapefile
    with shapefile.Writer(filename, shapeType=shapefile.POINT) as shp:
        shp.field("id", "L")
        shp.field("name", "C")

        for thing, point, elevation in things:
            # Assume loc.point is WKT or a Shapely geometry or GeoJSON
            if isinstance(point, str):
                try:
                    geom = wkt_loads(point)
                except GEOSException:
                    geom = from_geojson(point)
            else:
                geom = to_shape(point)

            shp.point(geom.x, geom.y)
            shp.record(thing.id, thing.name, elevation)


def make_within_wkt(sql: Select, wkt: str) -> Select:
    within = ST_GeomFromText(wkt, constants.SRID_WGS84)  # Assuming WGS84 (SRID 4326)
    return sql.where(ST_Within(Location.point, within))


# ============= EOF =============================================
