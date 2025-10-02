import json

from shapely.ops import transform
import pyproj
import httpx

from constants import SRID_WGS84

TRANSFORMERS = {}


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

    resp = httpx.get(url, params=params, timeout=30)
    data = resp.json()

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


if __name__ == "__main__":
    x = -106.904107
    y = 34.068198

    print(get_state_from_point(x, y))
    print(get_county_from_point(x, y))
    print(get_quad_name_from_point(x, y))
    print(get_epqs_elevation_from_point(x, y))
