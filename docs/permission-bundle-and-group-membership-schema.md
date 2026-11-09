# Permission Bundle and Group Membership Schema

**Status:** First draft

**References:** ADR5, "One Enforcement Engine, Two Grant Tables"; ADR6,
"Operator Console"; `docs/vocabulary-and-scope-taxonomy.md`

**Note:** Some table and column names in this document are proposals, not
decisions. Each one has a matching entry in Open Questions below.

## Summary

ADR6 establishes that Ocotillo's database, not Authentik, will own principal
groups: their identity, their membership, and what they are allowed to do.
This document proposes the schema that makes that possible -- a table for a
principal group's identity and membership, and a reusable, editable
permission bundle ("custom role") that a principal group can be assigned --
with live-reference semantics: editing a bundle's permissions takes effect
immediately for every principal group already assigned it, with no re-sync
step. This matches how Google Cloud IAM custom roles work.

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

**`principal_group`** (proposed name) -- the group's identity:

| Column | Meaning |
|---|---|
| `id` | Primary key |
| `name` | e.g. "AMMP Viewer" |
| `description` | What the group is for |
| `created_by` | Who created it |
| `created_at` | When |

**`principal_group_member`** (proposed name) -- its membership, one row per
person:

| Column | Meaning |
|---|---|
| `principal_group_id` | FK to `principal_group.id` |
| `member_id` | The Authentik-issued `sub` identifying the person |
| `added_by` | Who added them |
| `added_at` | When |

## Permission bundle schema

**`custom_role`** (proposed name) -- the bundle's identity:

| Column | Meaning |
|---|---|
| `id` | Primary key |
| `name` | e.g. "AMMP Viewer Base Permissions" |
| `description` | What the bundle grants, in plain language |
| `created_by` | Who created it |
| `created_at` | When |

**`custom_role_item`** (proposed name) -- the bundle's actual contents, one
row per permission:

| Column | Meaning |
|---|---|
| `custom_role_id` | FK to `custom_role.id` |
| `capability` | Same vocabulary as `permission_grant.capability` |
| `scope_type` | Same vocabulary as `permission_grant.scope_type` |
| `scope_id` | Same vocabulary as `permission_grant.scope_id` |
| `data_type` | Same vocabulary as `permission_grant.data_type` |
| `field_group` | Same vocabulary as `permission_grant.field_group` |

Editing `custom_role_item` is the entire propagation mechanism. Nothing else
needs to change for an edit to take effect -- every principal group assigned
the role resolves its current contents fresh on every check.

## How `permission_grant` relates to a bundle assignment

`permission_grant` gains one new nullable column, `custom_role_id` (proposed
name), a FK to `custom_role.id`. A row means one of two things, never both:

- `custom_role_id` is `NULL` -- a direct grant, exactly as today:
  `capability`/`scope_type`/`scope_id`/`data_type`/`field_group` filled in
  directly on the row.
- `custom_role_id` is set -- an assignment to a bundle. The row's own
  `capability`/`scope_type`/etc. stay `NULL`; the actual permissions are
  resolved by joining `custom_role_item` on `custom_role_id` at evaluation
  time.

`granted_by`/`granted_at`/`start_date`/`end_date`/`reason` apply to both
cases, since who assigned what, and when, doesn't change based on whether a
row is a direct grant or a role assignment.

## Worked example

`principal_group`:

| id | name | description |
|---|---|---|
| 1 | AMMP Viewer | AMMP program staff with read access to program data |

`principal_group_member`:

| principal_group_id | member_id | added_by |
|---|---|---|
| 1 | auth0\|sub-kelsey | jake |
| 1 | auth0\|sub-tyler | jake |
| 1 | auth0\|sub-chase | jake |

`custom_role`:

| id | name | description |
|---|---|---|
| 1 | AMMP Viewer Base Permissions | Read access to AMMP program data |

`custom_role_item`:

| id | custom_role_id | capability | scope_type | scope_id | data_type |
|---|---|---|---|---|---|
| 1 | 1 | read | program | AMMP | water chemistry |
| 2 | 1 | read | program | AMMP | groundwater level |
| 3 | 1 | read | program | AMMP | well inventory |

`permission_grant`, the assignment:

| id | principal_type | principal_id | capability | scope_type | custom_role_id |
|---|---|---|---|---|---|
| 10 | principal_group | 1 | — | — | 1 |

Checking "can AMMP Viewer read water chemistry under AMMP": look up
`permission_grant` for `principal_group` 1 -> row 10 has `custom_role_id=1`
-> join `custom_role_item` for role 1 -> row 1 matches. Allowed.

Later, AMMP Viewers also need read access to contact records. Insert one row
into `custom_role_item`:

| id | custom_role_id | capability | scope_type | scope_id | data_type |
|---|---|---|---|---|---|
| 4 | 1 | read | program | AMMP | contact |

Nothing in `permission_grant` changes. Every member of AMMP Viewer gets
contact-read access on their next request, through the same join that was
already checking role 1.

## Naming decisions

`custom_role`, not plain `role`:

- This codebase already has an actively-used `Role` enum (`core/enums.py`,
  built from a `role` lexicon category) meaning a contact's role in a field
  event -- landowner, operator, driller. A table literally named `role` would
  share a name with that, unrelated meaning, in the same codebase.

`custom_role` keeps the GCP IAM vocabulary already used when discussing this
design -- GCP itself distinguishes "predefined roles" from "custom roles,"
and a custom role there is exactly this: a user-defined permission bundle.

## Open questions

**Blockers** -- need resolution before schema/implementation work begins:

1. Confirm `principal_group` as the table name for group identity.
2. Confirm `principal_group_member` as the table/column names for
   membership, and whether `member_id` needs to be more than a bare
   Authentik `sub` -- e.g. whether the Operator Console needs a local
   display name/email per member, which would mean a separate `user` table
   rather than a bare string.
3. Confirm `custom_role` as the table name for the permission bundle.
4. Confirm `custom_role_item` as the table/column names for bundle contents.
5. Confirm `custom_role_id` as the new column name on `permission_grant`.
6. Can a bundle (`custom_role`) be assigned to `user`/`api_key` directly, or
   only to a `principal_group`? Today's `permission_grant` allows direct
   grants to all three principal types -- bundle-assignment following the
   same rule is an open decision, not an assumption.
7. Does group or bundle assignment need delegation boundaries now (ADR6
   section 2's program-manager scenario), or does that stay a named open
   question here and get its own design doc once this schema is settled?

**Future** -- do not block this draft, flagged for later design work:

8. Can a principal hold more than one `custom_role` assignment, or mix a
   direct grant with a role assignment, at the same time?

   - **Option 1 -- allow both, unrestricted** *(proposed)*. A principal can
     hold multiple `custom_role` assignments at once, and can mix a direct
     grant with a role assignment. This matches GCP IAM, where a principal
     commonly holds several simultaneous role bindings (e.g. a user bound to
     both a predefined role and a custom one) -- there's no "one role per
     principal" restriction there.

     Example of mixing a role assignment with a direct grant: AMMP Viewer is
     assigned the "AMMP Viewer Base Permissions" `custom_role` for its
     baseline read access. One AMMP Viewer member separately needs `update`
     access to a single well's reading, just for a short correction window --
     one person, one well, time-bound, not worth building a whole
     `custom_role` for. That's a direct `permission_grant` row on top of the
     same principal's existing role assignment, not a replacement for it.

     Example of a `principal_group` holding more than one `custom_role`:
     AMMP Viewer could hold both "AMMP Viewer Base Permissions" and a
     separate "Geothermal Viewer Base Permissions" `custom_role`, if AMMP
     staff also need baseline read access to Geothermal program data. Each
     role's `custom_role_item` rows contribute independently; the group's
     effective access is the union of both.

   - **Option 2 -- restrict a principal to exactly one assignment type at a
     time.** Would force every one-off exception into its own `custom_role`,
     adding overhead with no clear benefit, and has no GCP precedent to
     point to.
