# ADR5: One Enforcement Engine, Two Grant Tables

## Status

Proposed. Decides PUB-D14 / PERM-D3, the engine-count fork named in the
whitepaper *Who May See What, and Who May Do What* (Confluence, Ocotillo space).
Nothing is built yet. This record exists so the grant table and the visibility
layer are not designed twice.

## Summary

Ocotillo needs to answer one question everywhere: *may this principal exercise
this capability within this scope?* The whitepaper argues that publication
consent (a landowner's agreement about their well) and internal permission (an
institution's trust in a person) reduce to the same grammar, and then leaves
open whether they should therefore share one policy engine.

**Decision: two tables, one engine.** Landowner publication consent and internal
permission grants are stored separately, with separate governance, separate
admin surfaces, and separate audit semantics. Both are evaluated by a single
visibility layer and projected through a single field-allowlist chokepoint. No
service answers "is this published" on its own.

The split is about *who decides and on what authority*. The join is about *where
the answer is computed*. Those are different questions, and the current codebase
already shows what happens when the second one is answered "in each view."

## Context

### Enforcement is currently distributed, and it has already drifted

Publication today is a `release_status` column plus a filter re-written into
every consuming view. There are twelve of them — six public collections
(`ogc_locations`, `ogc_waterlevels`, `ogc_water_chemistry`,
`ogc_actively_monitored_wells`, `ogc_latest_tds_wells`, `ogc_project_areas`) and
six internal mirrors that deliberately carry non-public rows for authenticated
staff GIS clients. Each carries its own copy of the rule in SQL.

Migration `baba91fe5e83` is the drift, in the repository, with a date on it:
`ogc_waterlevels` filtered on the reading's own `release_status` and not the
parent well's, so a well marked `draft` or `private` still published its public
readings through OGC API - EDR — with the well's name and coordinates attached.
`ogc_water_chemistry` had required the parent thing to be public since
`d9e0f1a2b3c4`. Two views, two answers to the same question, and the difference
was invisible until someone read both.

That is not a bug in a view. It is what distributed enforcement does over time,
and every new destination multiplies it. The engine-count decision is really a
decision about whether that class of defect stays possible.

### Publication is currently a bulk act, not a consent record

`data_migrations/migrations/20260714_0001_publish_project_areas.py` publishes by
setting `release_status='public'` across a selection. That is the coarse
mechanism the whitepaper describes: association publishes everything about a
record, and an owner who would share water levels but not chemistry cannot be
represented at all.

### The grant shape already exists twice

`db/permission.py`'s `Permission` was landowner field-access consent —
`contact_id`, `allow_sampling`, `allow_installation`, an optional date range, a
polymorphic target (`permissible_id` / `permissible_type`). It was also dead:
unregistered in `db/__init__.py`, with no table in any migration and no caller.
It has been deleted, along with `PermissionMixin`. `PermissionHistory`
generalizes the same idea into a typed, lexicon-controlled `permission_type`
with `permission_allowed`, a required `start_date`, an optional `end_date`, and
`target_id` / `target_table`; it is now `FieldAccessConsent`, table
`field_access_consent`. Neither decides what an API caller may see.

Both are consent about physical site access. Neither is authorization. The shape
recurring independently is evidence the shape is right; it is not an argument
for merging those tables into the access-control model.

### Principals are already more than users

`/ogcapi-internal` is gated at the ASGI layer by `core/internal_ogc_auth.py`,
which accepts an Authentik JWT carrying `OGCInternal` **or** a static API key,
because ArcGIS Pro cannot present a bearer token. That key is a principal with
no user behind it, and today its scope is "everything the internal mount
serves." Any model that assumes principal == person is already wrong here.

### Two axes in one column

San Acacia data is public and provisional at once; `automated_ingestion/
ocotillo/loader.py` says so in a comment and works around it. `ReleaseMixin`
gave one lexicon column defaulting to `draft`, and that lexicon lists `draft`,
`public`, `private`, `published`, and `archived` — visibility — as siblings of
`provisional` and `final` — review state. Two axes, one column, so a record
could hold only one of the two answers.

`ReleaseMixin` now carries `data_maturity` alongside `release_status`. This is
not a new vocabulary: the lexicon category (`provisional`, `in review`,
`approved`, described in `core/lexicon.json` as "orthogonal to release_status")
and the column already existed on `transducer_observation`, and the split
generalizes them rather than inventing a parallel flag. Grants will need the
second axis, because some destinations want approved data only.

## Decision

### 1. Two tables

**`permission_grant`** — internal authorization. Principal (user subject, role,
API key), capability (read, enter, correct, administer), scope (project, thing,
data type, field group), time bounds, `granted_by`, `granted_at`, `reason`.
Governed by data services staff. Answers "is this person trusted with this."

**`publication_consent`** — landowner-facing publication. One row per
(thing, destination, data type), against a destination registry that holds the
anonymous public, NGWMN, and partner agencies. Carries the consenting contact,
the date it was recorded, and who recorded it. Governed by the data owner and by
whoever took the phone call. Answers "did the owner agree to this."

Neither table gets a NULL-as-wildcard data type. A grant names its types, so a
data type added next year is never published by an existing row.

### 2. One engine

A single visibility layer resolves both tables into one answer per request, and
a single serialization chokepoint applies the per-audience field allowlist and
its transformation hooks (coordinate rounding is the known case). The
never-public field list is enforced there and nowhere else.

Grants are read from the database at request time. They are never encoded into
token claims, and expiry is checked at use, because immediate revocation is a
promise made to landowners and a claim baked into a token outlives it.

### 3. Both tables feed one append-only authorization audit log

Grant, revocation, consent capture, publication-configuration change, membership
change. The log is shared even though the tables are not, because the question
after an incident — "who granted that, and when" — does not care which table the
row came from. `AuditMixin` and sqlalchemy-continuum cover data attribution and
data history; this is a separate structure, written from the application, with a
database-level backstop for writes that bypass it.

## Why not the alternatives

**One table.** Cheapest to enforce, and the enforcement argument is already won
by the shared engine, so the merge buys little. What it costs is governance: a
landowner's consent and a staff member's clearance would live in one table, one
admin screen, and one review path, decided by different people for different
reasons and with different consequences for being wrong. Revoking consent is a
phone call honored immediately; revoking clearance is an HR-shaped event. The
whitepaper's caution — that consent authoring and permission granting need
visible separation even if they share a surface — is easier to keep with a
schema that separates them than with a column that distinguishes them.

**Two engines.** Cleanest governance separation, and it reintroduces exactly the
`baba91fe5e83` failure: two independent implementations of "is this published,"
diverging quietly, with an outside party finding the difference first. Ocotillo
has one read path per record; it should have one answer.

## What this does not decide

- **Data type granularity** (PUB-U11). Water levels versus chemistry is
  required. Per-analyte grants may be over-engineering. The admin screen decides
  this, not the schema.
- **Whether field sensitivity is global or per destination**, and whether
  protection is removal only or also transformation (PUB-U7 / PUB-U8). The
  chokepoint supports both; which is configured is open.
- **What happens to rows already marked `release_status='provisional'`.** The
  two axes now exist, but no data moves between them. Rewriting those rows as
  a level plus `data_maturity='provisional'` needs someone to say what level
  each of them meant, and data migrations have no CD path in this repo — they
  are run by hand.
- **Whether `provisional` and `final` should leave the `release_status`
  lexicon.** Removing them is what makes the split enforceable rather than
  conventional, and it cannot happen before the row migration above.
- **Where coarse group membership lives**, Authentik or Ocotillo (PERM-D9).
  Authentik roles become role principals with broad grants either way, and
  nobody's access changes on the day the tables land.
- **What each audit event records** (PERM-U11 / PERM-U13). Before-and-after
  capture forces an event-based write path; whether that rigidity is required
  depends on a compliance driver nobody has yet identified.
- **Who owns the never-public field list.** A policy decision with a named
  owner, and a prerequisite to anything shipping externally. Engineering
  guarantees the list is enforced; it cannot decide what is on it.
- **Healy migration** (PUB-D13). Grandfathering wells as full consent preserves
  today's behavior; re-consenting per data type honors the model. The data owner
  chooses, explicitly, and it happens last.

## Consequences

**Good.** New destinations become a registry row plus grants, not a new pipeline
with its own copy of the rules. A field nobody approved is invisible outside the
Bureau by default, including fields added later. The correctness burden
concentrates in one layer that can be reviewed, tested, and monitored, instead
of in the next twelve views. A staff member can tell a well owner what is shared,
per kind of data, and revoke it from a screen.

**Cost.** Two tables to keep coherent where one would do, and a shared engine
that must not leak one table's governance into the other's admin surface. The
visibility layer sits on the read path of every service, so its query shape
matters: grants are few and cacheable per principal, but an unbounded cache
silently defeats the immediate-revocation promise. Cache with short TTLs and
explicit invalidation on revoke.

**Honesty requirement.** For a harvesting destination, revoking consent means
the data stops being offered. Copies already harvested live in someone else's
system. "Unpublish" means "stop offering," and that is what owners should be
told.

## Sequencing implied by this decision

1. This record (here).
2. **Done.** `permission_history` is `field_access_consent`, dead `Permission`
   and `PermissionMixin` are gone, and `ReleaseMixin` carries `release_status`
   (level) plus `data_maturity` (review state).
3. **Done.** `permission_grant`, `publication_consent`, `destination` and
   `authorization_audit` exist; `services/visibility.py` is the single
   evaluator; `api/access.py` is its one tenant. No existing endpoint routes
   through it yet.
4. Field projection at the serialization chokepoint, with the never-public list.
5. Console administration.
6. Healy migration, after the data owner decides grandfathering.

## References

- Confluence, Ocotillo space: *Who May See What, and Who May Do What: A
  scope-based, attribute-level access control system for Ocotillo* (whitepaper
  this record answers), *Ocotillo Needs an Operator Console*, *Authentik
  Access-Control Matrix Summary and Role Definitions*, *User Research Outcomes:
  Ocotillo Permissions Interview with Ethan Mamer*
- [ADR3](ADR3.md): OGC API - EDR collections backed by publication-filtered views
- [ADR4](ADR4.md): the `domain/` layer the grant-evaluation rules belong in
- [db/field_access_consent.py](db/field_access_consent.py): landowner
  field-access consent, and the in-house precedent for the grant shape
- [db/base.py](db/base.py): `ReleaseMixin`, `AuditMixin`, versioning wiring
- [alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py](alembic/versions/baba91fe5e83_gate_ogc_waterlevels_on_thing_release.py):
  the drift this decision is meant to make impossible
- [core/internal_ogc_auth.py](core/internal_ogc_auth.py) and
  [docs/internal-ogc-desktop-gis.md](docs/internal-ogc-desktop-gis.md): the API-key principal
