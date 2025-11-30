import json
import os

import httpx
import pyproj
from shapely.ops import transform
from sqlalchemy.orm import DeclarativeBase

from constants import SRID_WGS84

TRANSFORMERS = {}
METERS_TO_FEET = 3.28084


def to_bool(value: str) -> bool | str:
    """Convert a string to a boolean."""
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    elif value.lower() in ("false", "0", "no"):
        return False

    return value


def get_bool_env(key, default=False):
    return to_bool(os.getenv(key, default))


def transform_srid(geometry, source_srid, target_srid):
    """
    geometry must be a shapely geometry object, like Point, Polygon, or MultiPolygon
    """
    transformer_key = (source_srid, target_srid)
    if transformer_key not in TRANSFORMERS:
        source_crs = pyproj.CRS(f"EPSG:{source_srid}")
        target_crs = pyproj.CRS(f"EPSG:{target_srid}")
        transformer = pyproj.Transformer.from_crs(
            source_crs, target_crs, always_xy=True
        )
        TRANSFORMERS[transformer_key] = transformer
    else:
        transformer = TRANSFORMERS[transformer_key]
    return transform(transformer.transform, geometry)


def convert_m_to_ft(meters: float | None) -> float | None:
    """Convert a length from meters to feet."""
    if meters is None:
        return None
    return round(meters * METERS_TO_FEET, 6)


def convert_ft_to_m(feet: float | None) -> float | None:
    """Convert a length from feet to meters."""
    if feet is None:
        return None
    return round(feet / METERS_TO_FEET, 6)


def get_tiger_data(
    lon: float, lat: float, layer: int, outfields: str = "*"
) -> dict | None:
    url = f"https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/{layer}/query"
    params = {
        "f": "json",
        "where": "1=1",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": f"{SRID_WGS84}",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": outfields,
        "returnGeometry": "false",
    }
    try:
        resp = httpx.get(url, params=params, timeout=30)
    except Exception as e:
        print(f"Error getting TIGER data for POINT ({lon} {lat}) {e}")
        return None

    data = resp.json()
    if not data.get("features"):
        return None

    return data["features"][0]["attributes"]


def get_state_from_point(lon: float, lat: float) -> str | None:
    attrs = get_tiger_data(lon, lat, layer=0, outfields="BASENAME")
    if attrs:
        return attrs["BASENAME"]


def get_county_from_point(lon: float, lat: float) -> str | None:
    """
    Look up county for a given longitude/latitude
    using the US Census TIGERWeb REST API.
    """

    attrs = get_tiger_data(lon, lat, layer=1, outfields="BASENAME")
    if attrs:
        return attrs["BASENAME"]


def get_quad_name_from_point(lon: float, lat: float) -> str:
    url = "https://carto.nationalmap.gov/arcgis/rest/services/map_indices/MapServer/10/query"
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": f"{SRID_WGS84}",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CELL_NAME,CELL_MAPCODE",
        "returnGeometry": "false",
    }
    try:
        resp = httpx.get(url, params=params, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"Error getting quad name for POINT ({lon} {lat}) {e}")
        return None

    if data["features"]:
        attrs = data["features"][0]["attributes"]
        return attrs["CELL_NAME"]
    else:
        print(f"No quad name found for POINT ({lon} {lat})")
        return None


def get_epqs_elevation_from_point(lon: float, lat: float) -> float | None:
    url = "https://epqs.nationalmap.gov/v1/json"
    params = {
        "x": lon,
        "y": lat,
        "units": "Meters",
        "wkid": f"{SRID_WGS84}",
        "includeDate": False,
    }

    resp = httpx.get(url, params=params)
    try:
        data = resp.json()
    except json.decoder.JSONDecodeError:
        return None

    return data["value"]


def convert_ngvd29_to_navd88(
    elevation_ngvd29: float, longitude: float, latitude: float
) -> float:
    url = "https://geodesy.noaa.gov/api/ncat/llh"
    params = {
        "lat": latitude,
        "lon": longitude,
        "inDatum": "nad83(2011)",
        "outDatum": "nad83(2011)",
        "inVertDatum": "ngvd29",
        "outVertDatum": "navd88",
        "orthoHt": elevation_ngvd29,
    }
    response = httpx.get(url, params=params)
    data = response.json()

    elevation_navd88 = data.get("destOrthoht")
    return elevation_navd88


def retrieve_latest_polymorphic_history_table_record(
    target_record: DeclarativeBase,
    polymorphic_relationship: str,
    polymorphic_type: str,
) -> DeclarativeBase | None:
    """
    Retrieve the latest record from a polymorphic table. This function assumes that the
    parent class has the correct mixin to support retrieval via an attribute. This
    requires end_date to be None

    This function does not apply to the DataProvenance table since it is not
    a history table.

    Parameters:
    ----------
    target_record : DeclarativeBase
        The parent record from which to retrieve the polymorphic child record.
    polymorphic_relationship : str
        The name of the relationship attribute on the parent record that corresponds to the polymorphic table.
    polymorphic_type : str
        The specific type of the polymorphic record to retrieve (e.g., 'Use Status' or 'Monitoring Status' for StatusHistory).
    latest : bool, optional
        If True, retrieves the latest record based on start_date. Defaults to True.

    Returns
    -------
    DeclarativeBase | None
        The latest record from the specified polymorphic table with the defined type if it exists.
    """
    if polymorphic_relationship == "permissions":
        type_field = "permission_type"
    elif polymorphic_relationship == "status_history":
        type_field = "status_type"

    polymorphic_records = getattr(target_record, polymorphic_relationship)
    type_polymorphic_records = [
        r
        for r in polymorphic_records
        if getattr(r, type_field) == polymorphic_type and r.end_date is None
    ]
    sorted_type_polymorphic_records = sorted(
        type_polymorphic_records, key=lambda r: r.start_date, reverse=True
    )
    if sorted_type_polymorphic_records:
        return sorted_type_polymorphic_records[0]
    else:
        return None


if __name__ == "__main__":
    x = -106.904107
    y = 34.068198

    print(get_state_from_point(x, y))
    print(get_county_from_point(x, y))
    print(get_quad_name_from_point(x, y))
    print(get_epqs_elevation_from_point(x, y))
