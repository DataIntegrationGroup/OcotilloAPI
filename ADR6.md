# ADR6: Operator Console

## Status

## Summary

## Context

### Subpoint 0

### Subpoint 1

### Subpoint 2

### Subpoint 3

### Subpoint 4

## Decision

### 1. 

### 2.

### 3. 

### 4. 

## Why not the alternatives

## What this does not decide

## Consequences

## Sequencing implied by this decision

## References

- Confluence, Ocotillo space: *Who May See What, and Who May Do What: A
  scope-based, attribute-level access control system for Ocotillo* (whitepaper
  this record answers), *Ocotillo Needs an Operator Console*, *Authentik
  Access-Control Matrix Summary and Role Definitions*, *User Research Outcomes:
  Ocotillo Permissions Interview with Ethan Mamer*
- [ADR3](ADR3.md): OGC API - EDR collections backed by publication-filtered views
- [ADR4](ADR4.md): the `domain/` layer the grant-evaluation rules belong in
- [db/permission_history.py](db/permission_history.py): landowner
  field-access consent, and the in-house precedent for the grant shape
- [db/base.py](db/base.py): `ReleaseMixin`, `AuditMixin`, versioning wiring
- [alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py](alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py):
  the drift this decision is meant to make impossible
- [core/internal_ogc_auth.py](core/internal_ogc_auth.py) and
  [docs/internal-ogc-desktop-gis.md](docs/internal-ogc-desktop-gis.md): the API-key principal
