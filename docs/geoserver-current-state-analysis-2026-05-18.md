# GeoServer Current State Analysis (2026-05-18)

## Scope
This is a current-state snapshot of GeoServer-related implementation and operations in this repository. All work described here lives on the `geophysical/poc` branch.

## Companion Doc
- Architecture diagram: docs/geoserver-architecture-2026-05-18.md

## 1) Current Purpose of GeoServer
GeoServer currently appears to serve as a dedicated geospatial publishing tier for AEM raster and service-link use cases, while the main Ocotillo OGC feature API is still served by mounted pygeoapi under /ogcapi.

Evidence:
- ADR states pygeoapi remains active for /ogcapi and GeoServer is the strategic direction for public geospatial delivery (ADR is still marked Proposed and partially superseded).
- AEM ingest/batch code publishes validated GeoTIFF assets to GeoServer via REST (workspace + coverage store registration).
- STAC collection builders can emit GeoServer WMS/WFS/WCS links when GeoServer env vars are configured.

Net: GeoServer is in active support for AEM publishing workflows, but it is not yet the sole or primary geospatial interface in app runtime because pygeoapi still serves the OGC API feature surface.

## 2) Components That Exist Today

### Application-side components
- GeoServer publisher helper:
  - services/geoserver_helper.py
  - Handles:
    - config via GEOSERVER_URL, GEOSERVER_USERNAME, GEOSERVER_PASSWORD
    - idempotent workspace/store handling
    - external GeoTIFF registration using GeoServer REST endpoint
    - publish status tracking payloads
- AEM asset ingest integration:
  - services/aem_asset_ingest.py
  - Invokes publish_geotiff_asset for validated AEM GeoTIFFs.
- AEM batch orchestration:
  - services/aem_batch.py
  - Routes geotiff records through upload + GeoServer publish attempt.
- STAC asset link generation:
  - services/aem_stac.py
  - Adds optional survey-level WMS/WFS/WCS links when GEOSERVER_PUBLIC_URL and GEOSERVER_WORKSPACE are set.

### Data model and migration support
- Asset publish tracking fields exist in DB model:
  - db/asset.py
  - publish_target, publish_status, publish_workspace, publish_store_name, publish_layer_name, publish_last_attempt_at, publish_last_error
- Migration that added those fields:
  - alembic/versions/u1v2w3x4y5z6_add_asset_publish_tracking_columns.py

### Testing coverage
- GeoServer publisher unit tests:
  - tests/test_geoserver_helper.py
  - Covers: create missing workspace/store, idempotency, failure recording, missing source root error handling
- AEM ingest tests verifying publish state persistence:
  - tests/test_aem_asset_ingest.py
- STAC tests for GeoServer collection assets:
  - tests/test_aem.py (GeoServer WMS/WFS/WCS asset expectations)

### Infrastructure / deployment components
- Terraform module for standalone GeoServer stack:
  - geoserver_iac/main.tf
  - geoserver_iac/variables.tf
  - geoserver_iac/outputs.tf
  - geoserver_iac/versions.tf
  - geoserver_iac/startup-geoserver.sh.tpl
- Provisioning pattern:
  - GCP VM instance + instance group
  - HTTPS load balancer with managed certificate and health checks
  - Startup script installs docker + gcsfuse, mounts GCS bucket(s), runs GeoServer container
- Container image pin:
  - docker.osgeo.org/geoserver:2.28.0

## 3) Rough Existing Data Flows

### Flow A: AEM GeoTIFF ingest -> GeoServer publish
1. AEM batch/run ingests file metadata and uploads GeoTIFF to GCS.
2. Asset metadata record is created or updated.
3. GeoServer helper resolves mounted filesystem source path from GEOSERVER_RASTER_SOURCE_ROOT + storage path.
4. GeoServer helper ensures workspace exists.
5. GeoServer helper checks for existing coverage store; if absent, registers external GeoTIFF.
6. Publish result is persisted to asset publish_* tracking columns.

### Flow B: STAC collection generation -> GeoServer service links
1. AEM STAC collection is built.
2. If GEOSERVER_PUBLIC_URL and GEOSERVER_WORKSPACE are set, collection assets include:
   - WMS GetCapabilities
   - WFS GetFeature
   - WCS DescribeCoverage
3. Resulting links point clients to GeoServer OWS endpoints.

### Flow C: Parallel geospatial serving mode (current)
1. Main API still serves OGC API Features under /ogcapi using pygeoapi.
2. GeoServer is used for AEM GeoTIFF publication and optional STAC map/feature/coverage links.
3. This implies a hybrid platform state (pygeoapi + GeoServer).

## 4) Known Basic Use Cases and Users

### Supported use cases (known)
- Publish validated AEM GeoTIFFs to GeoServer during batch ingest.
- Track publication outcomes per asset (success/failed/skipped/disabled).
- Provide GeoServer WMS/WFS/WCS links in STAC collections for AEM datasets.
- Serve GeoServer through public HTTPS endpoint (domain configured in Terraform vars).

### Likely user groups (inferred from code/docs)
- Data engineering / ingestion operators running AEM batch and single-file ingest.
- GIS/data consumers using WMS/WFS/WCS endpoints linked from STAC artifacts.
- Platform/infra maintainers operating GCP/Terraform deployment for GeoServer.

### Not shown as implemented in repo
- Full replacement of /ogcapi feature APIs by GeoServer.
- GeoServer workspace/layer/style lifecycle as code (beyond runtime REST publication in ingest path).
- End-user UI workflows in Ocotillo admin for GeoServer management.

## 5) How It Is Deployed (As Implemented)
- Infra-as-code in geoserver_iac deploys a dedicated GCP VM-based stack.
- VM startup script:
  - installs docker and gcsfuse
  - mounts configured GCS bucket prefixes (GeoServer data and optional surveys)
  - runs GeoServer container on 8080 with proxy base URL set to https://<domain>/geoserver
- HTTPS load balancer fronts VM instance group and health-checks /geoserver/index.html.
- Terraform backend uses GCS state bucket/prefix.

### GCS as GeoServer data source of truth
GeoServer configuration state (workspaces, stores, layers, styles) is not stored on ephemeral container or VM disk. It is persisted in GCS and mounted into the container via gcsfuse:

- **Data directory bucket** (`geoserver_data_bucket`): mounted r/w at host path `geoserver_data_mount_point` (default `/mnt/disks/geoserver-data`), scoped to prefix `geoserver_data_only_dir` (default `data_dir`), then bind-mounted into the container at `/opt/geoserver_data`. This bucket is the authoritative source of truth for GeoServer config.
- **Surveys bucket** (`surveys_bucket`, optional): mounted read-only at host path `surveys_mount_point` (default `/mnt/disks/geoserver-surveys`) and exposed inside the container at `surveys_container_mount_point` (default `/opt/geoserver_data/surveys`). Used for GeoServer raster asset access.

VM service account (`geoserver-vm`) is granted `roles/storage.objectViewer` on both buckets via IAM resources in main.tf. GCS object versioning is the implicit backup mechanism for GeoServer config, but whether versioning is enabled on the live bucket is unknown.


## 6) Unknowns / Gaps Captured
- **Partially known**: Source of truth for GeoServer config is `geoserver_data_bucket` (GCS, mounted via gcsfuse — see section 5). Unknown: which specific bucket is live in production, and whether workspace/layer/style writes originate from admin UI or REST API calls.
- Unknown authn/authz posture for GeoServer admin/API and public endpoints (beyond LB exposure and SSH admin CIDR).
- Unknown SLOs, observability dashboards, alerting, and incident ownership for GeoServer service.
- **Partially known**: GeoServer config backup relies on GCS object versioning on `geoserver_data_bucket`. Unknown: whether versioning is enabled, what retention policy exists, and whether a restore drill has been performed.
- Unknown rollout status of ADR recommendation to make GeoServer the primary delivery tier.
- Unknown whether IaC in geoserver_iac is fully in sync with deployed infra (state file in repo is non-authoritative and mixed local artifacts exist).

## 7) Current-State Conclusion
GeoServer is implemented and integrated enough to support AEM raster publication and downstream service-link generation, with a dedicated GCP deployment path defined in Terraform. However, the primary OGC feature API in this application remains pygeoapi-based, so current architecture is hybrid rather than fully GeoServer-centric. The largest unknowns are operational governance (config-as-code, ownership, observability, security controls) and the true production cutover status.
