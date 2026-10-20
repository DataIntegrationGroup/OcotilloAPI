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

Closed set of four, per ADR5:

| Capability | Meaning | Grounded in |
|---|---|---|
| `read` | View data | Today's `Viewer` tier |
| `enter` | Create new records | Today's `Admin` tier's actual meaning — **not the same thing as the group named "Admin."** |
| `correct` | Edit existing records | Today's `Editor` tier |
| `administer` | Manage grants themselves (who can grant/revoke access) | **New.** Does not exist under any name today. Must not be confused with the existing "Admin" group, which actually means `enter`. Similar to Azure's `User Access Administrator` role, which treats managing access as its own permission, separate from data actions. |

**Not chosen:** `view`/`edit` — alternate wording for `read`/`correct`, not
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
covering multiple programs at once." How a principal ends up covered for
more than one program (e.g. both AMP and Geothermal) is a separate, still
open question — see open questions.

## 4. Worked examples

| # | principal_id | principal_type | capability | scope_type | scope_id | data_type | field_group | What this means |
|---|---|---|---|---|---|---|---|---|
| 1 | `Viewer` | group | `read` | `global` | — | — | — | Everyone in the generic Viewer group can read everything |
| 2 | `AMPViewer` | group | `read` | `program` | `AMP` | — | — | AMP's existing group, expressed as a grant row instead of hardcoded Python |
| 3 | `jane` | user | `correct` | `thing` | `well-4521` | — | — | A genuine one-off: one person, one well — nothing to usefully group |
| 4 | `field-laptop-01` | api_key | `read` | `global` | — | — | — | Today's actual behavior: a static key (labeled by person/machine, per convention) gets unrestricted read access to everything the internal mount serves — no narrowing by project, thing, or data type exists today. |

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

1. **Should `role` stay `group`, or revert to ADR5's original term?** `group`
   was chosen because it matches standard terminology. If there's any
   particular consideration for keeping `role`, we can discuss it and revert.
2. **Should `enter`/`correct` be standardized to `create`/`update`** to match
   standard terminology? If `enter`/`correct` were chosen deliberately — e.g.
   to distinguish *entering a new field observation* from *correcting a
   previously recorded value*, which may carry real meaning in a
   scientific-data context — we can proceed with that instead.
3. **Should `delete` be added as a capability?** The current closed set of
   four has no equivalent. Out of scope for this draft unless there's a real
   need for it now.
4. **Does `scope_type = project` reuse the existing `Group` model**
   (`db/group.py`), or is it a new concept? Not decided here.
5. **When AMP's existing hardcoded groups are eventually expressed as
   `program`-scoped grants**, does that require tagging every
   observation/chemistry/contact record with a `program`, or does it stay a
   coarse grant ("AMP members get `read`, `correct` on these resource types,
   no per-record tagging")? Affects schema design, not vocabulary, but named
   here so it isn't discovered by surprise later.
6. **How should someone needing access to more than one program (e.g. both
   AMP and Geothermal) actually be granted that?** Three options:
   1. Add them to both existing groups (e.g. `AMPViewer` and a future
      `Geothermal Viewer`) — no new grant rows, no new groups.
   2. Grant them directly as an individual `user` — only fits a genuine
      one-off, not a shared need.
   3. Create one dedicated combined group for that population and grant it
      both programs — only worth it if "people who need both" is itself a
      real, recurring population, not an incidental overlap of a couple of
      people.

   **Leaning towards Option 1** as the default: it costs nothing (reuses
   grants that already exist), and it matches the general rule that shared
   access should go through a group rather than individuals, even for small
   numbers (see Section 5). Options 2 and 3 remain valid for their specific
   cases above.

