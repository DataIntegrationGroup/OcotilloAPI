# Contract Details

| **Item** | **Value** |
| --- | --- |
| Contract Version | 1.0.0 |
| Status | Accepted |
| Provider | OcotilloAPI |
| Consumers | WeaverAPI, public users |
| Standards | OGC API - EDR 1.1 (OGC 19-086r6), CoverageJSON (OGC 21-069r2), GeoJSON (RFC 7946) |
| Base path | `/ogcapi/collections/manual_waterlevels` |
| Authentication | None, public data only for `/ogcapi/...`. Required, public and private data for `/ogcapi-internal/...` |

# Purpose
The purpose of this document is to determine and record the shape of the `/manual_waterlevels` OGC EDR API endpoints. These endpoints will be used by external sources and so the schemas defined herein will act as the source of truth for how it will be shaped by OcotilloAPI and how it will be consumed by others (e.g. WeaverAPI).

# /manual_waterlevels Data
The data served by the `/manual_waterlevels` OGC EDR endpoints will consist of well information and hand-measured waterlevels only. They will not contain any "continuous" observations (e.g. acoustic transducer, e-probe).

# Shape

## Sites

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
                "alternate_id": alternate_site_id,
                "alternate_id_descriptor": alternate_id_descriptor
            }
        }
    ]
}
```

## Time series

The time series data will be returned as CoverageCollection of [CoverageJSONs](https://docs.ogc.org/cs/21-069r2/21-069r2.html) as follows

```json
{
    "type": "CoverageCollection",
    "domainType": "PointSeries",
    "parameters": {
        "groundwater level below ground surface": {
            "type": "Parameter",
            "description": {
                "en": "Depth from the ground surface down to the water table, measured by hand during a site visit. Larger values mean the water table is further below the surface."
            },
            "observedProperty": {
                "id": "groundwater level below ground surface",
                "label": {
                    "en": "Groundwater level below ground surface"
                }
            },
            "unit": {
                "symbol": "ft",
                "label": {
                    "en": "ft"
                }
            } 
        },
        "groundwater level reason": {
            "type": "Parameter",
            "description": {
                "en": "USGS-style condition codes explaining why a water level reads as it does or could not be measured."
            },
            "observedProperty": {
                "id": "groundwater level reason",
                "label": {
                    "en": "Groundwater level reason"
                }
            },
        }
    },
    "coverages": [
        {
            "type": "Coverage",
            "id": id,
            "domain": {
                "type": "Domain",
                "domainType": "PointSeries",
                "axes": {
                    "x": {
                        "values": [longitude]
                    },
                    "y": {
                        "values": [latitude]
                    },
                    "t": {
                        "values": [value 1 datetime, value 2 datetime, ..., value n datetime]
                    }
                },
                "referencing": [
                    {
                        "coordinates": ["x", "y"],
                        "system": {
                            "type": "GeographicCRS",
                            "id": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                        }
                    },
                    {
                        "coordinates": ["t"],
                        "system": {
                            "type": "TemporalRS",
                            "calendar": "Gregorian"
                        }
                    }
                ]
            },
            "ranges": {
                "groundwater level below ground surface": {
                    "type": "NdArray",
                    "dataType": "float",
                    "axisNames": ["t"],
                    "shape": [n],
                    "values": [value 1, value 2, ..., value n]
                },
                "groundwater level reason": {
                    "type": "NdArray",
                    "dataType": "string",
                    "axisNames": ["t"],
                    "shape": [n],
                    "values": [value 1 reason, value 2 reason, ..., value n reason]
                }
            }
        }
    ]
}
```

# Notes

## ogc_waterlevels as of 11/4/2026

- The current `ogc_waterlevels` view, which as of 11/4/2026 is a union of manual and transducer waterlevels. The view is initially constructed in `alembic/versions/z9a0b1c2d3e4_add_edr_water_views.py`. The views are then reconstructed in `alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py` to gate on `public_release`. The internal views are constructed in `alembic/versions/2d3c3a268652_create_internal_ogc_views.py`. The views are repaired in `alembic/versions/b7c8d9e0f1a2_repair_missing_edr_water_views.py`.
- The current view only reports `groundwater level` observations but does not account for measuring point heights. It either needs to report `groundwater level below ground surface` and subtract the measuring point height, or report the measuring point height for each observation.
- Transducer and manual water level measurements should be split up into different views.
- Separate public and internal views should be created to support `/ogcapi` and `/ogcapi-internal` collections.

**IMPORTANT** `docs/measuring-point-height-null-handling.md` says that Cris Morton and Ethan Mamer want `null` measuring point heights to be `0`. This must be documented for the EDR endpoints.

## EDR Formations/Construction

The EDR endpoints that we make are bespoke, after a fashion. Updates to create the responses will not only need to be made in the views but in how the EDR endpoints are made, too. These will need to be done in `core/edr_provider.py`. `WaterEDRProvider::_station_properties` will, for example, need to be updated to include the new properties that are needed for this contract but don't already exist (e.g. `well_depth`). Updates in other places are likely needed, but are not listed here.

**IMPORTANT**
- The `id` field is an integer for the `FeatureCollection` but converted to a string for the `CoverageCollection`. These should be the same data types to enable joins between sites and observations.
- 'dataType` is hardcoded to `float` for each `range`. It should allow `integer` and `string` values too (`core/edr_provider.py::WaterEDRProvider::_coverageCollection`, line 417).

# Integration with WeaverAPI

The following steps will be taken to integrate this collection with WeaverAPI:

1. Query `/locations` to get a FeatureCollection of all locations that report manual groundwater levels
2. Query `/locations/{locId}`, one at a time, to get the associated manual groundwater levels as a CoverageColltion.
   - We are not concerned about timing since this work is done on a schedule during off-hours (i.e. at night). The queries, data collection, and harmonization are no longer done live via the CLI.

If a `413` error is encountered then we'll need to add query parameters to either step 1 or 2 to decrease the amount of data being returned. In step 1 we can use the `bbox` query parameter to tile New Mexico to get fewer points at a time. In step 2 we can use the `datetime` query parameter to get fewer observations at a time; in this case we need to make sure that we *always* get data up to the present day.


# Outstanding Questions

- **DECIDED**: this collection will report `groundwater level below ground surface`, *not* `groundwater level` with an asssociated `measuring point height` parameter and range.
  - **Original question**: We could maintain this as `groundwater level` rather than `groundwater level below ground surface`. What WeaverAPI needs, though, is the depth below ground surface. If, therefore, we want `groundwater level` to be maintained then measuring point heights *must* be provided for every observation. This would require adding a second `Parameter` to the `CoverageCollection` for `measuring point height` and adding a second `coverage` with `n` measuring point heights (one for every `groundwater level`). Thoughts on how to best proceed?
- **DECIDED**: this will be an OGC EDR collection and not OGC Features.
  - **Original question**: Should we pivot from EDR to Features? If we do this it'd be more difficult to bundle/relate the sites and observations if they live in different collections (one for observations with `null` geometry and one for wells). We'd need to document this somewhere, and where that documentation would go isn't too obvious. We could, conversely, serve the data with `geometry` for every observation where the `geometry` corresponds with the well, but then we'd miss metadata needed from wells such as `well_depth`.
  - We could also put well metadata with the observation data, but then we'd be mixing data in the response which is not a good idea.
- **DECIDED**: `/manual_waterlevels` is the correct id for this collection.
  - **Original question**: is `/manual_waterlevels` the correct id for the collection?
- **DECIDED**: This should become `/manual_waterlevels` and transducer and manual measurements should be split into different views and collections. `/continuous_waterlevels` will be developed at a later date.
  - **Original question**: Should this stay `/waterlevels` and transducer and manual measurements have different parameter names, or should they be split into different views and collections?