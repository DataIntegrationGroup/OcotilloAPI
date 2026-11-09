# Contract Details

| **Item** | **Value** |
| --- | --- |
| Contract Version | 1.0.0 |
| Status | Accepted |
| Provider | OcotilloAPI |
| Consumers | WeaverAPI, public users |
| Standards | OGC API - EDR 1.1 (OGC 19-086r6), CoverageJSON (OGC 21-069r2), GeoJSON (RFC 7946) |
| Base path | `/ogcapi/collections/water_chemistry` |
| Authentication | None, public data only for `/ogcapi/...`. |

# Purpose
The purpose of this document is to determine and record the shape of the `/water_chemistryt` OGC EDR API endpoints. These endpoints will be used by external sources and so the schemas defined herein will act as the source of truth for how it will be shaped by OcotilloAPI and how it will be consumed by others (e.g. WeaverAPI).

# /water_chemistry

## Data
The data served by the `/water_chemistry` OGC EDR endpoints will consist of

- Well information and water chemistry observations.
- Public data for `/ogcapi/water_chemistry/` endpoints.
- Both real and `null` values, both of which contain corresponding reasons for their state.

### Shape

#### Sites

The sites will be returned as a FeatureCollection of [GeoJSONs](https://geojson.org/) as follows

```json
{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": id,
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            "properties": {
                "name": name,
                "elevation": elevation,
                "elevation_units": "m",
                "horizontal_datum": "WGS84",
                "vertical_datum": "NAVD88",
                "well_depth": well_depth,
                "well_depth_units": "ft",
                "alternate_ids": [
                    {
                        "id": id,
                        "relation": relation,
                        "organization": organization
                    }
                ]
            }
        }
    ]
}
```

where

| **Field** | **Type** | **Description** |
| --- | --- | --- |
| `id` | `str` | Internal id of the well |
| `elevation` | `float` | Elevation of the well, in meters |
| `elevation_units` | `str` | Always `"m"` |
| `horizontal_datum` | `str` | Always `"WGS84"` |
| `vertical_datum` | `str` | Always `"NAVD88"` |
| `well_depth` | `float` or `null` | Depth of the well, in feet |
| `well_depth_units` | `str` | Always `"ft"` |
| `alternate_ids` | `list` | Alternate ids for the well. Each element is an object with `id`, `relation`, and `organization` |