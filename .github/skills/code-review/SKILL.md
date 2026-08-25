---
name: code-review
description: Repository-specific review rules for OcotilloAPI pull requests. Use this when reviewing a pull request in this repository, so review comments account for the authorization, schema, domain-layer, and migration conventions that are easy to violate silently.
---

# Reviewing OcotilloAPI pull requests

OcotilloAPI is a FastAPI + PostgreSQL/PostGIS geospatial service for the New Mexico
Bureau of Geology and Mineral Resources. Read `CLAUDE.md` at the repository root for
the full architecture; this skill lists the mistakes worth flagging in review because
they fail silently rather than breaking a test.

Use the GitHub MCP server tools (`list_workflow_runs`, `summarize_job_log_failures`,
`get_job_logs`) to check whether the `Test Suite` workflow is failing before commenting
on behavior — a failing `unit-tests` job often explains the diff better than the diff does.

## Authorization is opt-in, so omissions are invisible

Authorization is applied per endpoint via a parameter in the route signature, not by a
router-level `dependencies=[...]`. Two failure modes to flag:

1. A new route with no `user: <role>_dependency` parameter is fully public and raises no
   error. If the pull request adds a route, check whether it belongs in the anonymous-route
   allowlist in `tests/test_authorization.py`. If it does not, it needs a role dependency.
2. The dependency must be a **type annotation** (`user: viewer_dependency`), never a default
   value (`user=viewer_dependency`). The latter silently disables the dependency, and FastAPI
   reinterprets it as a query parameter. Flag this every time.

Role families are orthogonal: general `Admin` confers nothing in the `AMP*` or `Lexicon*`
families. Only tiers within one family nest. A diff that treats `Admin` as a superset of
`AMPEditor` is wrong.

`@in_public_schema` controls anonymous OpenAPI visibility only. It grants no access and
removes no dependency; flag any use that appears to be standing in for authorization.

`/ogcapi-internal` is a raw Starlette Mount and is gated at the ASGI layer in
`core/internal_ogc_auth.py`, outside `Depends()`. Changes to its credential paths should
cite `docs/internal-ogc-desktop-gis.md`.

The development auth bypass (`AUTHENTIK_DISABLE_AUTHENTICATION=1`) is honored only when
`MODE=development`. Any change that widens that condition is a security finding.

## Model changes are a five-step workflow

A pull request that edits a model in `db/` is incomplete unless it also covers the matching
Pydantic schemas in `schemas/`, an Alembic migration, test fixtures and payloads in `tests/`,
and the field mappings in `transfers/` when the field is populated from the legacy AMPAPI
data. Flag whichever step is missing.

Schema conventions: `Create` schemas use `<type>` for non-nullable and `<type> | None = None`
for nullable; `Update` schemas make every field optional with a `None` default; `Response`
schemas use `<type>` for non-nullable and `<type> | None` for nullable.

Validation split: input validation belongs in Pydantic validators and produces 422s. Database
constraint checks are manual in the endpoint and produce 409s. Custom exceptions should use
`PydanticStyleException` from `services/exceptions_helper.py` so error bodies stay consistent.

## Layer boundaries

`domain/` holds business rules as plain functions over plain values. Modules there must not
import from `api/`, `db/`, `schemas/`, or `services/`, and must not import `fastapi`,
`sqlalchemy`, `pydantic`, or `httpx`. Flag any new import that breaks this — it is what keeps
the rules testable without a database. Domain errors subclass `ValueError` because the CSV
importers treat a `ValueError` on a row as a per-row validation failure; an exception type
that does not subclass `ValueError` will escape that handling. See `ADR4.md`.

`services/` is the layer that loads data, calls the domain rule, and persists the result.

## Spatial and query specifics

All geometries are WGS84 (SRID 4326). Legacy transfer scripts convert from UTM (SRID 26913);
a missing transformation puts points in the wrong hemisphere rather than raising.

List filters arrive from the Refine UI as repeated `filter` query parameters containing JSON.
Association-backed columns are virtual and map to EXISTS subqueries in
`services/query_helper.py`, not to `ILIKE` on an ORM proxy. Sorting by monitoring status or
well status must use SQL subqueries on `StatusHistory`, because `ORDER BY` cannot see a Python
`@property`. See `docs/refine-json-filters-and-virtual-fields.md`.

## Migrations

Alembic schema migrations run automatically in the deployment pipeline. Registered *data*
migrations do not — they sit unapplied until someone runs them by hand. If a pull request adds
a data migration, ask how and when it will be run.
