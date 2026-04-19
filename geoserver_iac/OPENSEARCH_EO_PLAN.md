# OpenSearch For EO Module Plan

## Purpose

The GeoServer deployment under [`geoserver_iac/`](./) needs the OpenSearch for EO
community module installed for STAC and EO-oriented discovery work.

This module is **not bundled by default** with the base GeoServer image.

## Requirement

- Download the **OpenSearch for EO** community module from the GeoServer
  community builds for the **exact GeoServer version** being deployed.
- Extract the module JARs and drop them into GeoServer's `WEB-INF/lib/`.
- Treat this as part of the GeoServer runtime assembly, not as an optional
  manual post-deploy tweak.

## Version Matching

- The module version must match the deployed GeoServer version exactly.
- If [`geoserver_iac/variables.tf`](./variables.tf) or
  [`geoserver_iac/terraform.tfvars`](./terraform.tfvars) changes the
  `geoserver_image` version, the OpenSearch for EO module must be updated in
  lockstep.
- Do not mix module JARs from a different minor or patch release.

## Expected Installation Approach

1. Determine the GeoServer version from the configured `geoserver_image`.
2. Download the matching OpenSearch for EO community build artifact.
3. Copy the required JARs into `WEB-INF/lib/` inside the GeoServer webapp.
4. Restart GeoServer so the module is loaded.
5. Verify the module is present before treating the instance as ready.

## Implementation Note

This repo does not yet automate that installation in
[`geoserver_iac/startup-geoserver.sh.tpl`](./startup-geoserver.sh.tpl).
When that automation is added, it should:

- use the deployed GeoServer version as the source of truth
- fetch the matching community module artifact
- install it deterministically into `WEB-INF/lib/`
- fail fast if the matching module cannot be fetched or installed
