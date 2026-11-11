# Permission Bundle and Group Membership Schema

**Status:** First draft

**References:** ADR5, "One Enforcement Engine, Two Grant Tables"; ADR6,
"Operator Console"; `docs/vocabulary-and-scope-taxonomy.md`

**Note:** Some table and column names in this document are proposals, not
decisions. Each one has a matching entry in Open Questions below.

## Summary

ADR6 establishes that Ocotillo's database, not Authentik, will own principal
groups: their identity, their membership, and what they are allowed to do.
This document proposes the schema for a principal group's identity and
membership. Its permissions attach directly to `permission_grant`, with no
new table and no change to that table's existing columns or constraints --
`principal_type='principal_group'` already exists today. A separate,
reusable permission bundle is not part of this proposal: nothing today needs
the same set of permissions shared across more than one group, user, or API
key, so there is nothing yet to justify the extra schema, validation, and
audit surface that would come with one. See Open Question 5 for how to add
that if it ever becomes necessary.

## Background

Today, `principal_group` (per `docs/vocabulary-and-scope-taxonomy.md`) is a
bare Authentik JWT group name -- Authentik owns both the group and its
membership, and Ocotillo only stores grants against the name as a string.

ADR6 changes this: Authentik is scoped down to identity and authentication
only (user accounts, credentials, issuing the JWT). Ocotillo's database
becomes the owner of principal groups, their membership, and the permissions
assigned to them. This was confirmed in team discussion following the
2026-11-05 backlog meeting.

## Principal group schema

**`principal_group`** -- the group's identity:

| Column | Meaning |
|---|---|
| `id` | Primary key |
| `name` | e.g. "AMMP Viewer" |
| `description` | What the group is for |
| `created_by` | Who created it |
| `created_at` | When |

**`principal_group_member`** -- its membership, one row per person:

| Column | Meaning |
|---|---|
| `principal_group_id` | FK to `principal_group.id` |
| `member_id` | The Authentik-issued `sub` identifying the person |
| `added_by` | Who added them |
| `added_at` | When |

## How a principal group gets permissions

No new column, no new table. `permission_grant` already supports
`principal_type='principal_group'` today -- the only change is that
`principal_id` now refers to a real `principal_group.id`, instead of a bare
Authentik group name string. A group's full set of permissions is simply
every `permission_grant` row where `principal_type='principal_group'` and
`principal_id` matches that group -- an inspectable collection, satisfying
ADR6's requirement that "a group such as AMP Viewer should have an
inspectable collection of grants," with no bundle table needed to get that
view.

Editing a group's access means adding or removing `permission_grant` rows
for that group. This is live-reference by construction: the enforcement
engine reads `permission_grant` fresh on every check, so a new row takes
effect for every member of the group on their next request, with no re-sync
step and no separate propagation mechanism to build.

`permission_grant`'s existing constraints are untouched: `capability`,
`scope_type`, and `scope_id` stay `NOT NULL`, exactly as they are today,
with no new nullable column and no `CHECK` constraint needed to keep a row
from being only partly filled in.

## Worked example

`principal_group`:

| id | name | description | created_by | created_at |
|---|---|---|---|---|
| 1 | AMMP Viewer | AMMP program staff with read access to program data | jake | 2026-02-10 |

`principal_group_member`:

| principal_group_id | member_id | added_by | added_at |
|---|---|---|---|
| 1 | auth0\|sub-kelsey | jake | 2026-02-10 |
| 1 | auth0\|sub-tyler | jake | 2026-02-10 |
| 1 | auth0\|sub-chase | jake | 2026-02-10 |

`permission_grant` -- these rows are AMMP Viewer's permission set, no second
table involved:

| id | principal_type | principal_id | capability | scope_type | scope_id | data_type | field_group | start_date | end_date | granted_by | granted_at | reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | principal_group | 1 | read | program | AMMP | water chemistry | — | 2026-02-10 | — | jake | 2026-02-10 | AMMP staff need read access to their own program's data |
| 11 | principal_group | 1 | read | program | AMMP | groundwater level | — | 2026-02-10 | — | jake | 2026-02-10 | AMMP staff need read access to their own program's data |
| 12 | principal_group | 1 | read | program | AMMP | well inventory | — | 2026-02-10 | — | jake | 2026-02-10 | AMMP staff need read access to their own program's data |

Checking "can AMMP Viewer read water chemistry under AMMP": look up
`permission_grant` for `principal_group` 1 -> row 10 matches directly. No
join through a second table.

Later, AMMP Viewers also need read access to contact records. Insert one
more row, same shape as the three above (`principal_type=principal_group`,
`principal_id=1`, `capability=read`, `scope_type=program`,
`scope_id=AMMP`, `data_type=contact`, with its own `granted_by`/
`granted_at`). Every member gets it on their next request -- the same
live-reference result, and the new row is itself a fully audited grant, with
`granted_by`/`granted_at`/`reason`/`end_date` all present, same as any other
`permission_grant` row.

## Open questions

**Blockers** -- need resolution before schema/implementation work begins:

1. Confirm `principal_group` as the table name for group identity.
2. Confirm `principal_group_member` as the table/column names for
   membership, and whether `member_id` needs to be more than a bare
   Authentik `sub` -- e.g. whether the Operator Console needs a local
   display name/email per member, which would mean a separate `user` table
   rather than a bare string.
3. Does group assignment need delegation boundaries now (ADR6 section 2's
   program-manager scenario), or does that stay a named open question here
   and get its own design doc once this schema is settled?
4. How do changes to `principal_group`/`principal_group_member` get logged?
   Two options: rely on ADR6's planned append-only, hash-chained activity
   log (an event per change, nothing extra stored on these two tables), or
   give them their own history mechanism, closer to the existing
   `StatusHistory` pattern (`db/status_history.py`) -- effective-dated rows
   that can answer "who was in this group as of a past date," which an event
   log alone cannot. Separately: do these tables need `updated_by`, and does
   either need `updated_at`? `updated_by` would match the `created_by`/
   `added_by` columns already proposed above; `updated_at` would be new --
   today's `AutoBaseMixin` (`db/base.py`) tracks who last updated a row, but
   not when.

**Future** -- do not block this draft, flagged for later design work:

5. No mechanism here lets multiple groups/users/API keys share one reusable
   permission set without duplicating rows. If that need becomes real:
   either make `custom_role` a principal type (permissions stay as ordinary
   `permission_grant` rows; a small `custom_role_assignment` table tracks
   who's assigned which role), or let a `principal_group` nest inside
   another `principal_group` (reuses `principal_group_member`, but needs
   cycle prevention and transitive resolution). Not a decision to make
   before the need is concrete.
