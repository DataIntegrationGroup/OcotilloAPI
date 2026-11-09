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