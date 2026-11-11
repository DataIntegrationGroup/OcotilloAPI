# Contract Details

| **Item** | **Value** |
| --- | --- |
| Contract Version | 1.0.0 |
| Status | Accepted |
| Provider | OcotilloAPI |
| Consumers | WeaverAPI, public users |
| Standards | OGC API - EDR 1.1 (OGC 19-086r6), CoverageJSON (OGC 21-069r2), GeoJSON (RFC 7946), datetime (ISO 8601) |
| Base path | `/ogcapi/collections/manual_waterlevels` |
| Authentication | None, public data only for `/ogcapi/...`. |

# Purpose
The purpose of this document is to determine and record the shape of the `/manual_waterlevels` OGC EDR API endpoints. These endpoints will be used by external sources and so the schemas defined herein will act as the source of truth for how it will be shaped by OcotilloAPI and how it will be consumed by others (e.g. WeaverAPI).

# /manual_waterlevels

## Data
The data served by the `/manual_waterlevels` OGC EDR endpoints will consist of

- Well information and hand-measured waterlevels only. They will not contain any "continuous" observations (e.g. acoustic transducer).
- Public data for `/ogcapi/collections/manual_waterlevels/` endpoints.
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
                "ground_surface_elevation": elevation,
                "ground_surface_elevation_units": "m",
                "vertical_datum": "NAVD88",
                "well_depth": well_depth,
                "well_depth_units": "ft",
                "geologic_formation": {
                    "code": code,
                    "description": description
                }
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

where, for the following, `id` is at `features[].id` and all other fields are under `features[].properties`

| **Field** | **Type** | **Description** |
| --- | --- | --- |
| `id` | `int` | Internal id of the well |
| `name` | `str` | The name of the well (e.g. the PointID) |
| `ground_surface_elevation` | `float` | Elevation of the ground surface where the well is located, in meters |
| `ground_surface_elevation_units` | `str` | Always `"m"` |
| `horizontal_datum` | `str` | Always `"WGS84"` |
| `vertical_datum` | `str` | Always `"NAVD88"` |
| `well_depth` | `float` or `null` | Depth of the well, in feet |
| `well_depth_units` | `str` | Always `"ft"` |
| `geologic_formation` | `dict` | The geologic formation completion code and description |
| `alternate_ids` | `list` | Alternate ids for the well. Each element is an object with `id`, `relation`, and `organization` |

According to the standard [RFC 7946](https://www.rfc-editor.org/info/rfc7946/#section-4) the CRS must be "a geographic coordinate reference system, using the World Geodetic System 1984 (WGS 84) datum, with longitude and latitude units of decimal degrees."

#### Time series

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
                },
                "categories": [
                    {
                        "id": "Water level affected by atmospheric pressure",
                        "label": {
                            "en": "Water level affected by atmospheric pressure"
                        }
                    },
                    {
                        "id": "Water level was frozen (no level recorded).",
                        "label": {
                            "en": "Water level was frozen (no level recorded)."
                        }
                    },
                    {
                        "id": "Site was dry",
                        "label": {
                            "en": "Site was dry"
                        }
                    },
                    {
                        "id": "Site was flowing recently.",
                        "label": {
                            "en": "Site was flowing recently."
                        }
                    },
                    {
                        "id": "Site was flowing. Water level or head couldn't be measured w/out additional equipment.",
                        "label": {
                            "en": "Site was flowing. Water level or head couldn't be measured w/out additional equipment."
                        }
                    },
                    {
                        "id": "Nearby site that taps the same aquifer was flowing.",
                        "label": {
                            "en": "Nearby site that taps the same aquifer was flowing."
                        }
                    },
                    {
                        "id": "Nearby site that taps the same aquifer had been flowing recently.",
                        "label": {
                            "en": "Nearby site that taps the same aquifer had been flowing recently."
                        }
                    },
                    {
                        "id": "Recharge water was being injected into the aquifer at this site.",
                        "label": {
                            "en": "Recharge water was being injected into the aquifer at this site."
                        }
                    },
                    {
                        "id": "Recharge water was being injected into nearby site that taps the same aquifer.",
                        "label": {
                            "en": "Recharge water was being injected into nearby site that taps the same aquifer."
                        }
                    },
                    {
                        "id": "Water was cascading down the inside of the well.",
                        "label": {
                            "en": "Water was cascading down the inside of the well."
                        }
                    },
                    {
                        "id": "Water level was affected by brackish or saline water.",
                        "label": {
                            "en": "Water level was affected by brackish or saline water."
                        }
                    },
                    {
                        "id": "Well was not in hydraulic contact w/formation (from source other than defined in USGS C714 or C93).",
                        "label": {
                            "en": "Well was not in hydraulic contact w/formation (from source other than defined in USGS C714 or C93)."
                        }
                    },
                    {
                        "id": "Measurement was discontinued (no level recorded).",
                        "label": {
                            "en": "Measurement was discontinued (no level recorded)."
                        }
                    },
                    {
                        "id": "Obstruction was encountered in the well (no level recorded)",
                        "label": {
                            "en": "Obstruction was encountered in the well (no level recorded)"
                        }
                    },
                    {
                        "id": "Site was being pumped",
                        "label": {
                            "en": "Site was being pumped"
                        }
                    },
                    {
                        "id": "Site was pumped recently",
                        "label": {
                            "en": "Site was pumped recently"
                        }
                    },
                    {
                        "id": "Nearby site that taps the same aquifer was being pumped",
                        "label": {
                            "en": "Nearby site that taps the same aquifer was being pumped"
                        }
                    },
                    {
                        "id": "Nearby site that taps the same aquifer was pumped recently",
                        "label": {
                            "en": "Nearby site that taps the same aquifer was pumped recently"
                        }
                    },
                    {
                        "id": "Foreign substance present on the water surface",
                        "label": {
                            "en": "Foreign substance present on the water surface"
                        }
                    },
                    {
                        "id": "Well was destroyed (no subsequent water levels should be recorded)",
                        "label": {
                            "en": "Well was destroyed (no subsequent water levels should be recorded)"
                        }
                    },
                    {
                        "id": "Water level affected by stage in nearby surface-water site",
                        "label": {
                            "en": "Water level affected by stage in nearby surface-water site"
                        }
                    },
                    {
                        "id": "Other conditions exist that would affect the level (remarks)",
                        "label": {
                            "en": "Other conditions exist that would affect the level (remarks)"
                        }
                    },
                    {
                        "id": "Water level not affected",
                        "label": {
                            "en": "Water level not affected"
                        }
                    },
                    {
                        "id": "Site was unsafe to measure (no level recorded)",
                        "label": {
                            "en": "Site was unsafe to measure (no level recorded)"
                        },
                        "description": {
                            "en": "Site conditions made measurement hazardous, so no water level was recorded."
                        }
                    }
                ]
            }
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

where

| **Field** | **Type** | **Description** |
| --- | --- | --- |
| `coverages[].id` | `str` | Relates the coverage back to the feature's (well's) `id` where it is measured. Note that `id` is a `str` for coverages but an `int` for features |
| `coverages[].domain.axes.x.values` | `list[float]` | Longitude of the well. There is only one item in the list. |
| `coverages[].domain.axes.y.values` | `list[float]` | Latitude of the well. There is only one item in the list. |
| `coverages[].domain.axes.t.values` | `list[str]` | ISO 8601 datetime strings for each element in each range |
| `coverages[].ranges["groundwater level below ground surface"].shape` | `list[int]` | `[n]`, where n is the number of observations in the coverage. Null values are counted. |
| `coverages[].ranges["groundwater level below ground surface"].values` | `list[float \| null]` | Groundwater level below ground surface observations |
| `coverages[].ranges["groundwater level reason"].shape` | `list[int]` | `[n]`, where n is the number of reasons in the coverage. Null values are counted. |
| `coverages[].ranges["groundwater level reason"].values` | `list[str \| null]` | Groundwater level reason for each observation |

## Endpoints

Paths are relative to the base path, `/ogcapi/collections/manual_waterlevels`. Required parameters are in **bold**.

| **Method** | **Path** | **Query parameters** | **Response type** | **Use** |
| --- | --- | --- | --- | --- |
| GET | `/` | `f` | JSON (collection metadata) | Describe the collection: title, description, spatial/temporal extent, the parameters it serves (`parameter_names`), and the query types it supports (`data_queries`). |
| GET | `/locations` | `datetime`, `parameter-name`, `bbox`, `f` | GeoJSON `FeatureCollection` (see [Sites](#sites)) | List every well that has at least one reading matching the filters. With no parameters, returns every well in the collection. |
| GET | `/locations/{locId}` | `datetime`, `parameter-name`, `f` | CoverageJSON `CoverageCollection` (see [Time series](#time-series)) | Get the time series for one well. `locId` is the feature `id` from `/locations`. With no `datetime`, returns the well's entire record. |
| GET | `/position` | **`coords`**, `datetime`, `parameter-name`, `f` | CoverageJSON `CoverageCollection` | Get time series for wells whose location intersects the `coords` WKT geometry. A `Point` must match a well's coordinates exactly, so prefer `/locations/{locId}` for a single well. |
| GET | `/area` | **`coords`**, `datetime`, `parameter-name`, `f` | CoverageJSON `CoverageCollection` | Get time series for every well inside the `coords` WKT `Polygon`. `coords` is a required query parameter.|
| GET | `/cube` | **`bbox`**, `datetime`, `parameter-name`, `f` | CoverageJSON `CoverageCollection` | Get time series for every well inside the `bbox`. `bbox` is a required query parameter. |

Parameter behaviour:

- `datetime`: an ISO 8601 instant or interval; `..` leaves an end open (e.g. `2020-01-01/..`). Applies to the reading timestamps.
- `parameter-name`: comma-separated. `groundwater level below ground surface` and `groundwater level reason` are separate parameters, so naming only one omits the other's range. Leave it out to get both.
- `bbox` is a comma-separated list of the following values: `minx`, `miny`, `maxx`, `maxy`. They are defined via longitude and latitude in WGS84 (EPSG:4326).
- `coords` is a WKT Polygon that uses longitude latitude pairs, defined using WGS84 (EPS:4326).
- `f`: `json` (default for clients) or `html`.

Not supported:

- `/radius`, `/trajectory`, `/corridor` and `/items` return `400 Unsupported query type`.
- `/instances` returns an empty list. Manual readings have no transducer deployments.
- `z` and `crs` are accepted, and so is `limit` on `/locations`, but they are ignored. There is no pagination.

Responses:

- `200`: data found.
- `204 No Content`: the coverage queries (`/locations/{locId}`, `/position`, `/area`, `/cube`) matched no readings.
- `400`: invalid parameter, e.g. missing `coords` or `bbox`, malformed WKT.
- `413`: request too large (planned; see [Integration with WeaverAPI](#integration-with-weaverapi)).

# Notes

## ogc_waterlevels as of 11/4/2026

- The current `ogc_waterlevels` view, which as of 11/4/2026 is a union of manual and transducer waterlevels. The view is initially constructed in `alembic/versions/z9a0b1c2d3e4_add_edr_water_views.py`. The views are then reconstructed in `alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py` to gate on `public_release`. The internal views are constructed in `alembic/versions/2d3c3a268652_create_internal_ogc_views.py`. The views are repaired in `alembic/versions/b7c8d9e0f1a2_repair_missing_edr_water_views.py`.
- The current view only reports `groundwater level` observations but does not account for measuring point heights. It either needs to report `groundwater level below ground surface` and subtract the measuring point height, or report the measuring point height for each observation.
- Transducer and manual water level measurements should be split up into different views.
- Separate public and internal views should be created to support `/ogcapi` and `/ogcapi-internal` collections.
- Ensure that each `null` observation has a corresponding `groundwater level reason`, otherwise omit it from the view.

**IMPORTANT**

`docs/measuring-point-height-null-handling.md` says that Cris Morton and Ethan Mamer want `null` measuring point heights to be `0`. This must be documented for the EDR endpoints.

## EDR Formations/Construction

The EDR endpoints that we make are bespoke, after a fashion. Updates to create the responses will not only need to be made in the views but in how the EDR endpoints are made, too. These will need to be done in `core/edr_provider.py`. `WaterEDRProvider::_station_properties` will, for example, need to be updated to include the new properties that are needed for this contract but don't already exist (e.g. `well_depth`).

**IMPORTANT**

The following is a non-exhaustive list of updates that need to occur. Others are likely needed but not everything is enumerated herein since the codebase and standards were not exhaustively reviewed for where development needs to occur.

- `dataType` is hardcoded to `float` for each `range`. It should allow `integer` and `string` values too (`core/edr_provider.py::WaterEDRProvider::_coverageCollection`, line 417).
- A `413: request too large` error needs to be raised if too much data is queried at once.
- `/locations` should have a `parameter-name` query parameter. Document that it is part of the standard though not in the OpenAPI spec from OGC. Ensure it shows up in the OpenAPI spec/documentation for Ocotillo. Pin the amendment with a test so that a `pygeoapi` upgrade that adds it natively does not create a duplicate entry.
- `/locations` should document that `bbox` is not in the OGC standard but is in the OpenAPI spec so is included here.

# How to use API

The following steps will be taken to integrate this collection with WeaverAPI. These steps can be used by other consumers, too. If other consumers need the information live they may want to follow other strategies than retrieving time series data one-well-at-a-time. That is, however, up to the different consumers:

1. Query `/locations` to get a FeatureCollection of all locations that report manual groundwater levels
2. Query `/locations/{locId}`, one at a time, to get the associated manual groundwater levels as a CoverageCollection.
    - To conform with other FeatureCollections the `id` for every feature is an `int`, but to conform with [CoverageJSON standards](https://schemas.opengis.net/covjson/1.0/coveragejson.json) `locId` will need to be passed as a `str`. 
    - WeaverAPI is not concerned about timing it works on a schedule during off-hours (i.e. at night). The queries, data collection, and harmonization are no longer done live via the CLI.

If a `413` error is encountered then WeaverAPI will need to add query parameters to either step 1 or 2 to decrease the amount of data being returned. In either step we can use the `datetime` query parameter to get fewer records at once; in this case we need to make sure that we *always* get data from the beginning of records up to the present day. Instead of a `datetime` query parameter for step 1, though, WeaverAPI can tile New Mexico to retrieve all of the locations using the `bbox` query parameter.

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
- **DECIDED**: `/locations` will have a `parameter-name` query parameter.
  - **Original question**: The EDR standard's written requirements for [`/locations`](https://docs.ogc.org/is/19-086r6/19-086r6.html#_60c4d31c-62f2-4dc7-9a3e-6a1a9127d29e) (Table 13, Req. A.33) list `parameter-name` as a query parameter, but the standard's official OpenAPI definition ([locations.yaml](https://schemas.opengis.net/ogcapi/edr/1.1/openapi/paths/queries/locations.yaml)) omits it. `pygeoapi` follows the OpenAPI definition, so it accepts `?parameter-name` on `/locations` (and our provider filters on it) but does not list it in the generated OpenAPI document. It will be especially useful for the future `/water_chemistry` collection. Should we include it in this contract? If so, should we document it only here, or also add it to the generated OpenAPI document (we generate that file in `core/pygeoapi.py::_generate_openapi`, so it can be amended there without patching `pygeoapi`)?
- **DECIDED**: `/locations` will have a `bbox` query parameter.
  - **Original question**: Conversely, the standard's written requirements for `/locations` do not list `bbox`, but its official OpenAPI definition does, and `pygeoapi` both accepts and documents it. Should we keep `bbox` in the contract, marked as supported-but-not-in-the-written-requirements, or remove it?

# Future Work

While this will support public data access for WeaverAPI and other consumers this will also serve as contract for `/ogcapi-internal/manual_waterlevels`. That collection will serve both public and private data. It will not, however, be defined and mounted for the effort to connect OcotilloAPI to WeaverAPI. That work will need to be done in the future when it is warranted.