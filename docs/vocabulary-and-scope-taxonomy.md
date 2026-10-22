# Ocotillo Access-Control Vocabulary and Scope Taxonomy

**Status:** First draft
**References:** ADR5, "One Enforcement Engine, Two Grant Tables"

## Summary

Before any schema or migration work begins on ADR5's `permission_grant`
table, this document finalizes three things: who can hold a grant
(**principal types**), what a grant lets them do (**capabilities**), and
what data a grant applies to (**scope**). It does not cover
`publication_consent`'s destination registry (public, NGWMN, partner
agencies) — that is a separate vocabulary. Legacy `Permission`/`PermissionHistory`
records are unrelated: they represent landowner/field-site access consent
(renamed `FieldAccessConsent` per ADR5), not `permission_grant` authorization.

## How this relates to Authentik

Today, Authentik (our login provider) does two jobs at once: it proves who
someone is, and — because `core/dependencies.py` hardcodes what each group
name means — it also decides what they can do. This document is part of
separating those two jobs. Under the new design, Authentik's job shrinks to
just *identity and group membership*: who is this, and what groups are they
in. The `permission_grant` table becomes the only place that decides what a
group, user, or API key is actually allowed to do. The payoff: changing who
is in a group never requires a code change, and changing what a group can do
never requires touching the login system.

## 1. Principal Types

| Type | Meaning | Grounded in |
|---|---|---|
| `user` | An individual person | Forward-looking — access is decided entirely by group membership today. Individual identity is recorded for audit only (JWT `sub`), never used to gate access. |
| `group` | A named set of people | Today's actual mechanism: Authentik JWT group membership (`Admin`, `Editor`, `Viewer`, `AMPAdmin`, `AMPEditor`, `AMPViewer`, etc., checked in `core/dependencies.py`). Renamed from ADR5's `role` to match standard terminology (see open questions). |
| `api_key` | A credential with no person behind it | The static keys in `core/internal_ogc_auth.py`, used because ArcGIS Pro/QGIS can't hold a session. |

**Excluded:** `anonymous_public`. The public is never an authenticated
principal holding a grant — it's a *destination* that already-published data
is served to. That belongs in `publication_consent`'s destination registry,
not here.

## 2. Capabilities

Closed set of five. ADR5 originally proposed four (`read`, `enter`,
`correct`, `administer`); `create`/`update` replace `enter`/`correct` to
match standard terminology, and `delete` has been added as its own
capability:

| Capability | Meaning | Grounded in |
|---|---|---|
| `read` | View data | Today's `Viewer` tier |
| `create` | Create new records | Today's `Admin` tier's actual meaning — **not the same thing as the group named "Admin."** |
| `update` | Edit existing records | Today's `Editor` tier |
| `delete` | Remove records | **New, as its own capability.** Today, every DELETE route checked (`api/thing.py`, `api/location.py`, `api/sample.py`, `api/observation.py`, `api/contact.py`, etc.) is gated by the same `admin`/`amp_admin` tier already used for `create` — delete isn't missing a tier, it's merged into the create tier today. |
| `administer` | Manage grants themselves (who can grant/revoke access) | **New.** Does not exist under any name today. Must not be confused with the existing "Admin" group, which actually means `create`. Similar to Azure's `User Access Administrator` role, which treats managing access as its own permission, separate from data actions. |

**How these relate to each other:** `create`, `update`, and `delete` each
imply `read` — if a principal can create, update, or delete a record, they
can also view it. `create` and `update` are independent of each other:
granting one does not grant the other.

**Not chosen:** `view`/`edit` — alternate wording for `read`/`update`, not
separate capabilities.

**Excluded for a structural reason:** `publish`. Publication is governed
entirely by `publication_consent`, a separate table with separate governance
— adding `publish` as a `permission_grant` capability would collapse that
split back into one table.

**Naming note:** `db/publication.py`/`api/publication.py` already exists in
this codebase as an unrelated bibliographic-citation registry (academic
papers, DOIs). Worth keeping the two concepts clearly distinguished.

## 3. Scope

A grant narrows "what data" along up to four independent fields on the same
row, which can be combined (e.g. `scope_type=project` + `data_type=water
chemistry` on one grant):

| Field | Meaning | Values / source |
|---|---|---|
| `scope_type` | The broad category being scoped | `global` (no restriction), `project`, `thing`, `program` |
| `scope_id` | The specific instance within `scope_type` | `global`: blank — applies everywhere, nothing specific to name.<br>`project`: not yet decided — likely the existing `Group` model (`db/group.py`), but unconfirmed; see open questions.<br>`thing`: the well/spring/stream's own `Thing.id`.<br>`program`: a value like `AMP` or `Geothermal` — see the `scope_type = program` section below. |
| `data_type` | Which kind of data | Grounded in the real `activity_type` lexicon: `well inventory`, `groundwater level`, `water chemistry`. Nullable (no restriction) when not specified. Extensible — not a hardcoded enum. |
| `field_group` | Which subset of fields | **New concept, no existing precedent.** `docs/water-well-field-operations-layer.md` already considered and declined a finer-grained PII split under the old credential model — implementing `field_group` now reopens that question under the new engine. Flag for implementers, not a blocker. |

A single grant row holds exactly one `scope_id`. A principal who needs access
to more than one instance of a scope (e.g. two programs, or two projects)
gets **multiple grant rows**, not a multi-valued column.

### `scope_type = thing`, not `well`

`Thing.thing_type` is a lexicon column with ~20 values (9 well subtypes, plus
spring, stream, meteorological station, etc.). A scope called "well" would
structurally exclude most of what the system monitors.

### `scope_type = program`

Grounded in one real example, implemented the old way: **AMP (Aquifer
Mapping Program)**, today a hardcoded Authentik group family
(`AMPAdmin`/`AMPEditor`/`AMPViewer`) gating observations, chemistry, and
contacts for anyone in the group — not a per-record tag. **Geothermal** is a
confirmed future program value, with no access control today.

`program` must be an open, extensible value set (e.g. a small
lexicon/reference table), not a hardcoded two-value enum, since a second
value is already known to be coming.

Each grant row holds exactly one `scope_id` — never a list of programs. The
enforcement engine only ever needs to check "does this principal hold a
grant for *this* program," never "does this principal hold one grant
covering multiple programs at once."

**Resolved:** for small numbers of cross-program users, add them to both
relevant groups; if the pattern grows into a recurring population, create a
dedicated cross-program group instead.

## 4. Worked examples

| # | principal_id | principal_type | capability | scope_type | scope_id | data_type | field_group | created_by | created_date | expiry_date | What this means |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `Viewer` | group | `read` | `global` | — | — | — | `jake` | `2026-01-01` | — | Everyone in the generic Viewer group can read everything |
| 2 | `AMPViewer` | group | `read` | `program` | `AMP` | — | — | `kelsey` | `2026-02-10` | — | AMP's existing group, expressed as a grant row instead of hardcoded Python |
| 3 | `chase` | user | `update` | `thing` | `well-4521` | — | — | `likitha` | `2026-09-01` | `2026-12-01` | A genuine one-off: one person, one well — nothing to usefully group. Time-bound, unlike the other rows. |
| 4 | `field-laptop-01` | api_key | `read` | `global` | — | — | — | `tyler` | `2026-03-15` | `2027-03-15` | Today's actual behavior: a static key (labeled by person/machine, per convention) gets unrestricted read access to everything the internal mount serves — no narrowing by project, thing, or data type exists today. Keys currently expire after one year. |

## 5. Naming convention for Authentik groups

- **Broad, universal groups** that apply system-wide, not to one specific
  population, stay generic: `Viewer`, `Editor`, `Admin`.
- **Population-specific groups** (a program's staff, a project's team) should
  be named descriptively, including both who they are and what level they
  hold — e.g. `AMP Viewer`, `AMP Editor`, `Geothermal Viewer`. This is good
  practice, not something to avoid.
- **What actually changed is not the naming, it's the cost of creating one.**
  Under the old design, a group like `GeothermalViewer` required writing new
  Python in `core/dependencies.py` and redeploying the service. Under the new
  design, creating a descriptively-named group means inserting a group plus
  one grant row — a data operation, never a code change.
- **Shared access, even for a small number of people, gets a group — not
  individual grants.** A group costs nothing extra to create, and it means
  adding or removing the next member never touches the grant table. Reserve
  direct `user` grants for access that is genuinely about one specific
  person's unique situation (row 3 above), not as a shortcut for "the group
  happens to be small."

## Open questions

**Blockers** — need resolution before schema/implementation work begins:

1. **Final naming for the principal type currently called `group` remains
   open, pending PR comments and further review.** Options raised in
   discussion: keep `group`, revert to ADR5's `role`, or use `usergroup`/
   `principalgroup`.
2. **Does `scope_type = project` reuse the existing `Group` model**
   (`db/group.py`), or is it a new concept? Leaning towards reusing the
   `Group` model, confirmation needed.

**Future** — do not block this draft, flagged for later design work:

3. **How should `delete` actually behave?** Soft delete vs. hard delete (row removal), and whether a
   confirmation pop up is required in the UI before a delete completes.
4. **Naming convention for API key principal IDs issued to third parties**
   (external partners, integrations).
5. **Policy-engine conflict-resolution rules** for overlapping or
   conflicting grants (e.g. one grant allows a request, another restricts
   the same request) — not decided here.
6. **API key revocation flow** — what should actually happen, end to end,
   when a key needs to be revoked

