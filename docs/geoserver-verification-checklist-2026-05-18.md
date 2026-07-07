# GeoServer Verification Checklist (2026-05-18)

Use this checklist to close the unknowns identified in the current-state analysis.

## A. Production Usage Verification
- [ ] Pull 30-day request logs for:
  - GeoServer LB endpoint
  - /ogcapi endpoints
- [ ] Quantify request volume by endpoint family (WMS/WFS/WCS vs /ogcapi).
- [ ] Identify top clients (service accounts, applications, external consumers).
- [ ] Confirm which datasets are actively consumed from GeoServer vs pygeoapi.

Evidence to capture:
- URL and date range of logs queried.
- Table of volumes by endpoint family.
- Named systems consuming each interface.

## B. GeoServer Configuration Governance

**Known from IaC**: GeoServer data directory (workspaces, stores, layers, styles) is persisted in GCS and mounted into the container via gcsfuse at `/opt/geoserver_data`. The `geoserver_data_bucket` Terraform variable names the authoritative bucket; the `geoserver_data_only_dir` prefix (default `data_dir`) scopes the mount within that bucket. An optional second bucket (`surveys_bucket`) is mounted read-only at `/opt/geoserver_data/surveys` for raster asset access. The GCS buckets are therefore the source of truth for GeoServer configuration state — not the container filesystem and not a separate config-as-code repo.

- [ ] Confirm which GCS bucket(s) are the live `geoserver_data_bucket` and `surveys_bucket` in production.
- [ ] Confirm whether workspaces/stores/layers are created via admin UI writes (persisted to GCS through the mount) or via REST API calls from code.
- [ ] Document whether changes are:
  - API-driven from code,
  - manual in admin UI (changes go directly to GCS data dir),
  - imported from data directory snapshots.
- [ ] Define promotion process across environments (dev/staging/prod).
- [ ] Define review gate (PR, change ticket, approvals).

Evidence to capture:
- Bucket names for each environment.
- Owner(s) and approver group.
- Step-by-step promotion procedure.
- Rollback procedure and tested example.

## C. Security and Access Controls
- [ ] Verify public exposure scope (only intended paths/services).
- [ ] Verify GeoServer admin endpoint restrictions.
- [ ] Verify credential rotation policy for GEOSERVER_USERNAME/PASSWORD.
- [ ] Verify VM and container patch/update cadence.
- [ ] Verify SSH access controls still match current admin roster.

Evidence to capture:
- Current access matrix (who can do what).
- Rotation schedule and last rotation date.
- Hardening checklist status.

## D. Observability and Operations
- [ ] Confirm logging coverage for publish attempts and failures.
- [ ] Confirm alerts for:
  - LB health-check failure
  - GeoServer process/container down
  - repeated publish failures
- [ ] Confirm dashboards for latency/error rate/throughput.
- [ ] Confirm incident ownership and escalation path.

Evidence to capture:
- Alert definitions and destinations.
- Dashboard links.
- On-call ownership mapping.

## E. Data Resilience and Recovery

**Known from IaC**: GeoServer config state lives in `geoserver_data_bucket` (gcsfuse mount). GCS object versioning or bucket-level backup policy is therefore the backup mechanism for GeoServer config — no separate data-directory backup step exists unless versioning is enabled on that bucket.

- [ ] Confirm GCS versioning and/or object lifecycle policy on `geoserver_data_bucket`.
- [ ] Confirm backup policy for GeoServer data directory (backed by GCS — see section B).
- [ ] Confirm restore drill has been tested and documented.
- [ ] Confirm RPO/RTO targets and current achieved posture.

Evidence to capture:
- Backup schedule and retention.
- Last successful restore test date.
- Recovery runbook location.

## F. ADR/Cutover Status
- [ ] Confirm current status of ADR3 recommendation in practice.
- [ ] List datasets already migrated to GeoServer.
- [ ] List datasets still on pygeoapi only.
- [ ] Define explicit transition milestones and decision gates.

Evidence to capture:
- Dataset inventory by serving surface.
- Owner and timeline for each migration wave.

## G. IaC and Environment Consistency
- [ ] Confirm Terraform state is authoritative and current for active environment.
- [ ] Confirm repo IaC variables match deployed values (domain, buckets, mounts, image).
- [ ] Remove ambiguity from local state artifacts in repo workflows.
- [ ] Capture environment bootstrap steps needed for repeatable deploy.

Evidence to capture:
- Terraform state backend details and last apply metadata.
- Drift report summary.
- Environment parity table (desired vs actual).

## Exit Criteria
- [ ] Every checklist section has an owner and due date.
- [ ] Unknowns list is reduced to zero or converted into tracked risks.
- [ ] Final architecture decision (hybrid vs full GeoServer primary) is documented with measurable readiness criteria.
