# ADR3: Migrating OGC Delivery From Mounted pygeoapi to GeoServer

> Superseded in part on April 19, 2026. OcotilloAPI continues to serve `/ogcapi`
> via mounted `pygeoapi`, while STAC moves to a dedicated service outside this repo.

## Status

Proposed

## Summary

This ADR evaluates whether NMSampleLocations should migrate geospatial service delivery away from the current mounted `pygeoapi` solution and instead use the newer standalone GeoServer instance.

The current design mounts `pygeoapi` into the FastAPI application under `/ogcapi`. That gives the project a simple OGC API - Features surface that is versioned, deployed, and operated with the main API. The repo now also contains a separate GeoServer deployment path under [`geoserver_iac/`](geoserver_iac), and AEM/STAC code already assumes GeoServer-backed WMS/WFS endpoints for some datasets.

The question is not whether GeoServer is technically viable. It is. The question is whether the project should make GeoServer the primary public geospatial delivery tier for feature access plus WFS/WMS, and retire the mounted `pygeoapi` path over time.

## Context

Today, the application exposes OGC API - Features collections via mounted `pygeoapi`.

- [`core/factory.py`](core/factory.py) mounts `pygeoapi` into the FastAPI app during startup.
- [`core/pygeoapi.py`](core/pygeoapi.py) generates runtime config and OpenAPI files into `/tmp/pygeoapi` and mounts the Starlette app under `/ogcapi`.
- [`core/pygeoapi-config.yml`](core/pygeoapi-config.yml) defines the collection metadata and PostGIS providers.
- [`README.md`](README.md) documents `/ogcapi` as part of the primary application deployment.

At the same time, the repo now has a dedicated GeoServer infrastructure path.

- [`geoserver_iac/main.tf`](geoserver_iac/main.tf) provisions a standalone GeoServer VM, instance group, and HTTPS load balancer.
- [`geoserver_iac/startup-geoserver.sh.tpl`](geoserver_iac/startup-geoserver.sh.tpl) mounts a GCS-backed data directory and runs the GeoServer container.
- [`services/aem_ingest.py`](services/aem_ingest.py) already emits STAC asset links that assume GeoServer-hosted WMS/WFS endpoints.

This creates an architectural fork:

1. Keep OGC API - Features embedded in the FastAPI service via `pygeoapi`.
2. Move geospatial service delivery to the standalone GeoServer instance.
3. Use a hybrid model, where GeoServer becomes the primary public geospatial delivery tier while `pygeoapi` remains temporarily in place during migration.

## Decision Drivers

- Reduce coupling between geospatial delivery and the main FastAPI process.
- Avoid unnecessary operational overhead for datasets that only need simple feature delivery.
- Prioritize public geospatial delivery around features plus WFS/WMS.
- Reduce fragmentation between feature delivery and map-service delivery.
- Keep deployment and maintenance costs proportionate to the actual capability gain.
- Keep geospatial publishing in a platform designed for ongoing GIS-oriented administration.

## Option A: Keep Mounted pygeoapi

### Pros

- Single application deployment model. The same FastAPI service owns `/`, `/admin`, and `/ogcapi`, which keeps routing and release management simple.
- Lower platform overhead. There is no separate VM, load balancer, mounted data directory, or GeoServer admin surface required for the core feature API.
- Strong fit for the current in-app implementation. The repo already documents `/ogcapi` and has tests around the mount behavior.
- Configuration remains code-adjacent. Collection definitions and mount behavior live in the repo alongside the application and migrations.
- Easier developer workflow for API teams. Local startup of the main app is enough to exercise the OGC API - Features surface.
- Better alignment with the repo’s existing PostGIS-backed feature views and materialized views created specifically for `pygeoapi`.

### Cons

- The main API process remains responsible for geospatial feature serving, which increases startup/config complexity and widens the blast radius of failures.
- `pygeoapi` is limited to the feature-serving use case. It is not the natural home for broader geospatial publishing patterns like WMS administration, styling, or richer GIS interoperability.
- Runtime config is generated into ephemeral local storage and depends on deployment-time environment variables, which is workable but operationally less explicit than a dedicated service.
- Scale characteristics are tied to the FastAPI deployment model. If geospatial traffic grows independently from the main API, the system cannot scale those concerns cleanly.
- AEM and STAC already point toward GeoServer for map services, so the platform story is split.

## Option B: Migrate to GeoServer

### Pros

- Clear separation of concerns. GeoServer becomes the dedicated geospatial publishing tier, while FastAPI remains the application/API tier.
- Better fit for WMS/WFS and map-serving use cases. This is already reflected in the AEM/STAC service code.
- Independent scaling and operations. GeoServer traffic, cache behavior, and admin workflows can evolve without forcing changes to the primary API deployment.
- Mature GIS ecosystem support. GeoServer is widely used for desktop GIS, styled layers, and operational geospatial publishing.
- The repo already has infrastructure investment in this direction, including load-balanced deployment and mounted data access.

### Cons

- Higher operational burden. A standalone VM, Docker container, mounted bucket, and GeoServer data directory all add platform surface area, failure modes, and patching responsibility.
- More configuration likely moves out of normal application code paths and into GeoServer workspace/layer state, which can reduce reviewability unless rigorously managed as code.
- Local development becomes heavier if engineers need both the API stack and GeoServer to validate common geospatial changes.
- Migration effort is non-trivial. Existing `pygeoapi` collections, database views, docs, tests, and downstream integrations would all need review.
- GeoServer introduces a second security and administration surface that the team must own.

## Option C: Hybrid Transition

### Pros

- Lowest migration risk. The team can move toward GeoServer as the primary public geospatial tier without a flag-day cutover.
- Allows GeoServer to take over both feature-serving and WFS/WMS incrementally.
- Keeps current delivery working while GeoServer workspaces, layers, and operational practices mature.
- Lets the team validate GeoServer administration and configuration-as-code patterns before fully retiring `pygeoapi`.

### Cons

- Two geospatial publishing paths remain in service for some period.
- Metadata and ownership boundaries must be kept clear to avoid confusion over which platform is authoritative for which dataset.
- Some duplicated operational knowledge is unavoidable during transition.

## Discussion

The core tradeoff is simplicity versus specialization.

Mounted `pygeoapi` is simpler for the current feature API. It keeps geospatial feature delivery close to the application code, close to the data-model changes, and close to the existing developer workflow. That is a real advantage when the primary need is straightforward OGC API - Features publication from PostGIS-backed views.

GeoServer is stronger when the public delivery target includes both feature access and WFS/WMS. The repo already shows this direction: the AEM pipeline emits GeoServer WMS/WFS links, and the new infrastructure exists because some publishing cases benefit from a dedicated geospatial server. Given that public geospatial delivery is expected to prioritize features plus WFS/WMS, GeoServer is not just an add-on. It is the better long-term publishing tier.

The biggest risk in a full migration is not contract loss, because the team is not locked into the current mounted surface. The real risks are operational ownership, configuration discipline, and migration execution. If the team says "move to GeoServer" but does not explicitly define how layers are managed, reviewed, tested, and promoted, then the result will be platform sprawl rather than a cleaner architecture.

The biggest risk in staying on `pygeoapi` only is strategic fragmentation. The system would continue to operate two geospatial stories anyway: `pygeoapi` for feature collections and GeoServer for WFS/WMS-oriented publication. Given the stated public delivery goals, that split would become harder to justify over time.

## Recommendation

Adopt GeoServer as the primary public geospatial delivery platform.

Use a staged migration rather than an immediate flag-day cutover:

- Publish new public geospatial layers through GeoServer by default.
- Migrate existing `pygeoapi` collections into GeoServer in planned batches.
- Keep `pygeoapi` only as a temporary bridge during migration, not as the long-term primary surface.
- Require answers to three concrete implementation questions before each migration wave:
  1. How will GeoServer configuration be managed with the same review and repeatability standards as code in this repo?
  2. What validation will prove the migrated layers still meet feature and WFS/WMS requirements?
  3. What is the rollback path if a migrated collection or workspace fails in production?

This recommendation favors GeoServer strategically and incremental rollout operationally. The repo already has working `pygeoapi` feature delivery and emerging GeoServer capabilities. That argues for a deliberate migration, not indefinite dual ownership.

## Consequences

### If the recommendation is accepted

- The current `/ogcapi` surface remains available only for the migration period.
- GeoServer becomes the preferred home for public features and WFS/WMS.
- The team must define configuration-as-code and promotion practices for GeoServer so its state remains reviewable and reproducible.
- `pygeoapi` becomes transitional infrastructure rather than a permanent parallel platform.

### If the team accelerates the cutover

- The project should explicitly plan collection migration, operational ownership, GeoServer configuration management, and test/doc rewrites before beginning each cutover wave.

## Follow-Up Work

- Document which current collections migrate first and which remain on `pygeoapi` only temporarily.
- Define the target public delivery surface for each dataset family across features and WFS/WMS.
- Produce a technical migration checklist covering:
  - auth and access control,
  - configuration-as-code strategy,
  - local developer workflow,
  - observability and incident ownership,
  - rollback plan.
