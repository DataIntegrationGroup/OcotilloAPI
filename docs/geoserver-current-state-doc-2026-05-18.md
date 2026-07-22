# GeoServer Current State Documentation

**Prepared by:** Jake Ross
**Date:** 2026-05-18
**Meeting / source:** geophysical/poc branch — code review + IaC analysis

---

**Purpose.** Capture the current state of GeoServer integration in plain language: what it is, how data moves through it, what is working, what is broken, and what decisions are still open.

---

## 1. Summary (Current State)

GeoServer is a dedicated geospatial publishing tier integrated into the OcotilloAPI platform. It handles AEM raster (GeoTIFF) publication and exposes WMS/WFS/WCS service links for STAC collections. It runs as a Docker container on a GCP VM, backed by GCS buckets for persistent config and raster data. The primary OGC API feature surface (/ogcapi) still runs on pygeoapi, so the current architecture is hybrid — GeoServer handles rasters and OWS services, pygeoapi handles vector feature API. GeoServer also connects to PostGIS as a vector data store.

---

## 2. What Problem Does It Solve?

- **Original problem:** No OGC-compliant raster tile/coverage service existed for AEM geophysical survey data being ingested into the platform.
- **Current problem:** AEM GeoTIFF ingest pipeline needs a publish target that exposes WMS/WFS/WCS endpoints; STAC collection records need service links for map/feature/coverage consumers. GeoServer fills both roles.
- **Primary users / consumers:**
  - AEM ingest operators (run batch and single-file ingest that triggers GeoServer publish)
  - GIS/data consumers (access WMS/WFS/WCS links embedded in STAC collection assets)
  - Platform/infra maintainers (operate GCP + Terraform deployment)

---

## 3. Inputs / Outputs

| Input | Ingestion Layer | Raw Data Storage | Transformation & Load | Clean Data Storage | Service |
|---|---|---|---|---|---|
| AEM GeoTIFF files | `services/aem_batch.py`, `services/aem_asset_ingest.py` | GCS (`surveys_bucket`) | `services/geoserver_helper.py` — registers external GeoTIFF as GeoServer coverage store via REST | GeoServer data dir in GCS (`geoserver_data_bucket`) | WMS / WCS via HTTPS LB (`geoserver.newmexicowaterdata.org`) |
| PostGIS vector data | GeoServer admin / REST config | PostgreSQL + PostGIS DB | GeoServer PostGIS data store connection | GeoServer workspace / layer config in GCS data dir | WFS via HTTPS LB |
| STAC collection build | `services/aem_stac.py` | PostgreSQL (asset + survey records) | Generates WMS/WFS/WCS hrefs from `GEOSERVER_PUBLIC_URL` + `GEOSERVER_WORKSPACE` | STAC JSON artifact | STAC collection served by OcotilloAPI |

---

## 4. Main Components

| Component | Role today | Owner / repo | Status |
|---|---|---|---|
| `services/geoserver_helper.py` | Idempotent GeoServer REST publish helper — workspace + coverage store registration, publish status tracking | OcotilloAPI / geophysical/poc | Active |
| `services/aem_asset_ingest.py` | Single-file AEM ingest — invokes publish_geotiff_asset | OcotilloAPI / geophysical/poc | Active |
| `services/aem_batch.py` | Batch AEM orchestration — routes GeoTIFFs through upload + GeoServer publish | OcotilloAPI / geophysical/poc | Active |
| `services/aem_stac.py` | STAC service-link generation — adds WMS/WFS/WCS hrefs to collection assets | OcotilloAPI / geophysical/poc | Active |
| `db/asset.py` publish fields | DB tracking for publish outcome per asset (`publish_status`, `publish_layer_name`, etc.) | OcotilloAPI / geophysical/poc | Active |
| `geoserver_iac/` | Terraform IaC — GCP VM + instance group + HTTPS LB + gcsfuse bucket mounts | OcotilloAPI / geophysical/poc | Defined; live state unknown |
| GeoServer container | `docker.osgeo.org/geoserver:2.28.0` running on GCP VM | GCP / geoserver_iac | Assumed active; not confirmed |
| GCS `geoserver_data_bucket` | Source of truth for GeoServer config (workspaces, stores, layers, styles) — gcsfuse r/w mount at `/opt/geoserver_data` | GCP | Active; bucket name unknown |
| GCS `surveys_bucket` | Raster source data for GeoServer coverage stores — gcsfuse r/o mount at `/opt/geoserver_data/surveys` | GCP | Active; bucket name unknown |
| PostgreSQL + PostGIS | Vector data store — GeoServer connects directly for WFS feature serving | OcotilloAPI DB | Active |
| HTTPS Load Balancer | Public front door for GeoServer at `geoserver.newmexicowaterdata.org/geoserver` | GCP / geoserver_iac | Defined in IaC |

---

## 5. Key Behavior

**Flow A — AEM GeoTIFF publish:**
1. Ingest uploads GeoTIFF to GCS (`surveys_bucket`).
2. GeoServer helper resolves mounted path (`GEOSERVER_RASTER_SOURCE_ROOT` + storage path).
3. Helper ensures workspace exists; registers external GeoTIFF as coverage store if absent.
4. Publish outcome written to asset `publish_*` columns in DB.

**Flow B — STAC service links:**
1. STAC collection build reads asset + survey records from DB.
2. If `GEOSERVER_PUBLIC_URL` and `GEOSERVER_WORKSPACE` are set, collection assets include WMS/WFS/WCS hrefs.
3. GIS clients discover GeoServer endpoints via those links.

**Flow C — Hybrid serving (current):**
- `/ogcapi` OGC Features served by pygeoapi (unchanged).
- GeoServer serves AEM raster publication and related OWS endpoints.
- PostGIS vector data available to GeoServer as a data store alongside raster coverage stores.

**Config persistence:**
GeoServer data directory is gcsfuse-mounted from `geoserver_data_bucket` into the container at `/opt/geoserver_data`. All workspace/store/layer/style changes persist to GCS, not to ephemeral container disk.

---

## 6. Known Problems

- No workspace/layer/style lifecycle as code — GeoServer config changes (e.g. new PostGIS data stores, style edits) go directly to GCS data dir via admin UI or REST, with no Git-backed review gate or promotion process.
- IaC state is non-authoritative in the repo (`terraform.tfstate` is empty; `.tfstate.backup` is a stale local snapshot). True deployed state is unknown.
- Hybrid serving architecture (pygeoapi + GeoServer) is unresolved — ADR recommending GeoServer as primary delivery tier is still marked Proposed.
- No observability: no confirmed dashboards, alerts, or on-call ownership for GeoServer service health or publish failure rates.

---

## 7. Open Decisions / Questions

- Which GCS buckets are the live `geoserver_data_bucket` and `surveys_bucket` in production?
- Are workspace/store/layer writes happening via admin UI (writes to GCS data dir) or via REST API calls from code?
- Is GCS object versioning enabled on `geoserver_data_bucket`? Has a restore drill been performed?
- What is the current production traffic split between GeoServer OWS endpoints and pygeoapi /ogcapi?
- What is the status of the ADR to make GeoServer the primary delivery tier — is there a timeline?
- What is the authn/authz posture for the GeoServer admin endpoint and public OWS endpoints?
- Who owns GeoServer incident response and what are the SLOs?
