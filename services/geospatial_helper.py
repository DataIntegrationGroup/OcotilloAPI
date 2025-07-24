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
import json

import shapefile
from shapely.errors import GEOSException
from geoalchemy2 import functions as geofunc
from shapely.io import from_geojson

import constants
from db.thing import Thing
from db.group import GroupThingAssociation, Group
from db.location import Location, LocationThingAssociation
from geoalchemy2.functions import ST_GeomFromText, ST_Within, ST_AsGeoJSON
from geoalchemy2.shape import to_shape
from shapely.wkt import loads as wkt_loads
from sqlalchemy import Select, select


def get_thing_features(
    session, thing_type: str | None, group: str | int | None
) -> list:
    sql = (
        select(Thing, ST_AsGeoJSON(Location.point).label("geojson"))
        .join(LocationThingAssociation, Thing.id == LocationThingAssociation.thing_id)
        .join(Location, LocationThingAssociation.location_id == Location.id)
    )

    # selection_args = [Thing, ST_AsGeoJSON(Location.point).label("geojson")]
    # if thing_type == "well":
    #     selection_args.append(WellThing)
    # elif thing_type == "spring":
    #     selection_args.append(SpringThing)

    sql = (
        select(Thing, ST_AsGeoJSON(Location.point).label("geojson"))
        .join(LocationThingAssociation, Thing.id == LocationThingAssociation.thing_id)
        .join(Location, LocationThingAssociation.location_id == Location.id)
    )

    if thing_type:
        sql = sql.where(Thing.thing_type == thing_type)
    # if thing_type == "well":
    #     sql = sql.join(WellThing, Thing.id == WellThing.thing_id)
    # elif thing_type == "spring":
    #     sql = sql.join(SpringThing, Thing.id == SpringThing.thing_id)

    if group:
        sql = sql.join(GroupThingAssociation).join(Group)
        if isinstance(group, str):
            sql = sql.where(Group.name == group)
        else:
            sql = sql.where(Group.id == group)

    return session.execute(sql).all()


def create_shapefile(things: list, filename: str = "things.shp") -> None:
    # Create a point shapefile
    with shapefile.Writer(filename, shapeType=shapefile.POINT) as shp:
        shp.field("id", "L")
        shp.field("name", "C")

        for thing, point in things:
            # Assume loc.point is WKT or a Shapely geometry or GeoJSON
            if isinstance(point, str):
                try:
                    geom = wkt_loads(point)
                except GEOSException:
                    geom = from_geojson(point)
            else:
                geom = to_shape(point)

            shp.point(geom.x, geom.y)
            shp.record(thing.id, thing.name)


def make_within_wkt(sql: Select, wkt: str) -> Select:
    within = ST_GeomFromText(wkt, constants.SRID_WGS84)  # Assuming WGS84 (SRID 4326)
    return sql.where(ST_Within(Location.point, within))


# ============= EOF =============================================
