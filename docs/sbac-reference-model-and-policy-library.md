# A reference model and policy library for Ocotillo scope-based access control

**Status:** First draft, for discussion

**References:** ADR5, "One Enforcement Engine, Two Grant Tables"; ADR6,
"Operator Console"; `docs/vocabulary-and-scope-taxonomy.md`;
`docs/permission-bundle-and-group-membership-schema.md`; `db/permission_grant.py`

## Summary

We have decided what Ocotillo's scope-based access control (SBAC) should say.
The vocabulary is settled, `permission_grant` exists, and ADR6 moves group
ownership into our database. What we have not decided is how the engine
evaluates a grant. So far each design document has had to invent its own
answer to questions that other systems settled years ago.

This paper proposes two things.

1. **Adopt Google Cloud IAM as the reference model.** Its grant row, resource
   hierarchy, and inheritance rule match ours almost one for one. Where we
   need a rule we have not written yet, we take IAM's unless we have a
   reason not to. Kubernetes RBAC is the second reference, used only for
   delegation.
2. **Use Cedar, through the `cedarpy` package, as the evaluator behind a
   small set of helper functions** in a new `services/authz/` package. Cedar
   is AWS's open-source policy language. `cedarpy` wraps its Rust engine and
   runs inside the API process, with no sidecar service.

Cedar answers "may this principal do this to this record." It does not tell
us which rows a principal may list, and no Python library we found does that
well enough to depend on. So the list filter stays hand-written, built from
the same grant rows, and a parity test keeps it in step with Cedar.

## 1. Where we are

The access-control vocabulary (`docs/vocabulary-and-scope-taxonomy.md`) and
`core/lexicon.json` fix the parts of a grant.

| Part | Values |
|---|---|
| Principal type | `user`, `principal_group`, `api_key` |
| Capability | `read`, `create`, `update`, `delete`, `administer` |
| Scope type | `global` (`scope_id = '*'`), `program`, `project` (a `Group`), `thing` |
| Data type | `activity_type` terms, e.g. `groundwater level`, `water chemistry`. Never null. |
| Field group | Free text, no values defined yet |
| Time bounds | `start_date`, optional `end_date` |

`db/permission_grant.py` stores these as one row per grant. Nothing reads the
table yet. Routes still check Authentik group names through
`core/dependencies.py`, about 170 times across `api/`, and the OGC views each
carry their own copy of the `release_status` rule.

The engine has to do four jobs.

- **Check.** Decide whether a principal may take one action on one record.
  This covers every write and every single-record read.
- **Filter.** Produce the set of rows a principal may see, as SQL, for list
  endpoints and the OGC views. On our read paths this is the main workload.
- **Explain.** Say which grant allowed or denied a request. The Operator
  Console needs this, and so does anyone debugging a 403.
- **Delegate.** Let a program manager grant access within their own program
  and nowhere else.

## 2. Why we should copy an existing model

Every rule we write from scratch costs a meeting and leaves an edge case
nobody thought about. The vocabulary document's open questions show this
already. Conflict resolution, delegation limits, and what an empty grant set
means are all open, and all of them have standard answers.

A borrowed model also gives the team a reference that is written down
somewhere other than our heads. When someone asks "does a project grant
cover a well in a child project," we can point at the IAM docs and say yes,
and why.

## 3. Reference model: Google Cloud IAM

### 3.1 The mapping

| GCP IAM | Ocotillo |
|---|---|
| Principal (user, group, service account) | Principal (`user`, `principal_group`, `api_key`) |
| Permission, e.g. `storage.objects.get` | Capability plus data type, e.g. `read` on `water chemistry` |
| Role, a named set of permissions | Not adopted in v1. See 3.3. |
| Resource hierarchy: organization, folder, project, resource | `global`, `program`, `project`, `thing`, then the record |
| Allow policy binding: (principal, role, resource) | One `permission_grant` row |
| Inheritance: a binding on a parent applies to every descendant | A grant on a project covers its things and their records |
| IAM Conditions, CEL expressions on time and attributes | `start_date`, `end_date`, `data_type`, `field_group` |
| Policy Troubleshooter | `explain()` and the Operator Console |
| Default deny: no binding, no access | Same |

### 3.2 Rules we take from IAM

1. **Default deny.** A principal with no matching grant gets nothing. An
   authenticated user with zero grants can log in and see nothing. This is
   ADR6's "an authenticated user does not automatically receive access."
2. **Allow-only, additive grants.** Access is the union of every grant the
   principal holds, directly or through a group. No grant takes anything
   away. That answers the vocabulary document's open question 5 for v1: a
   conflict cannot happen because there is nothing to conflict with. GCP ran
   this way for years before adding deny policies. If we need deny later,
   Cedar has `forbid` (section 4.5).
3. **Inheritance flows down the hierarchy and never up.** A grant on project
   12 covers every thing in project 12 and every child project of 12. A
   grant on one thing says nothing about its project.
4. **The hierarchy can be a graph, not a tree.** In IAM a resource has one
   parent. In Ocotillo a `Thing` can belong to several `Group`s through
   `GroupThingAssociation`, and groups nest through `parent_group_id`. A
   grant on any ancestor covers the thing. This is the one place we depart
   from IAM, and Cedar handles it without extra work because its entities
   can have several parents.
5. **Conditions narrow a grant and never widen it.** Data type, field group,
   and time bounds each restrict the row they sit on.
6. **Time bounds are checked at use.** A grant past its `end_date` is gone
   on the next request, as ADR5 requires. Nothing is cached in a token.

### 3.3 What we do not take from IAM

**Roles.** IAM bundles permissions into roles and grants the role. The
permission bundle document already argues against a bundle table in v1,
and that holds here. A principal group with its own grant rows does the
same job. The one place we need role-like behavior is capability
implication. `create`, `update`, and `delete` each imply `read`. We encode
that in one table in code (section 5.2), not in data.

**Organization policies and service-account impersonation.** Neither has a
use case in Ocotillo.

### 3.4 Delegation: borrow from Kubernetes RBAC

IAM's rule for who may change a policy is coarse. Kubernetes has the rule we
want. A user may create a RoleBinding in a namespace only if they already
hold every permission in the role they are granting, in that namespace. It
calls this escalation prevention.

Our version:

> A principal may create or revoke a grant only if (a) they hold
> `administer` on a scope that covers the grant's scope, and (b) they
> themselves hold the grant's capability and data type on a scope that
> covers the grant's scope.

So an AMMP program manager holding `administer` and `update` on
`program:AMP` can give a student `read` or `update` on AMP water levels.
They cannot grant anything on Geothermal, and they cannot grant `delete`
unless they hold it. `administer` itself can only be granted by someone who
holds `administer` on a covering scope. That keeps delegation within the
manager's program, which is what ADR6 section 2 asks for.

## 4. Evaluator: Cedar through `cedarpy`

### 4.1 What Cedar is

Cedar is a policy language and evaluation engine released as open source by
AWS. It is what Amazon Verified Permissions runs. A Cedar request has four
parts, principal, action, resource, and context, which matches our grant
shape. Entities form a hierarchy through `in`, which matches our scope tree.

`cedarpy` is a Python binding to the official Rust engine. It is maintained
by k9 Security, not AWS. Version 4.12.2 was released on 2026-10-14, and the
package has published releases since July 2023. It evaluates in-process.

### 4.2 Why Cedar over the alternatives

| Option | Why not |
|---|---|
| Plain Python, no library | Workable, and our fallback (section 7). We would write and test hierarchy walking, capability implication, and explanation ourselves, with no schema validation. |
| PyCasbin | Mature, but its matcher config is string-based and untyped, and it expects its own policy table. Scope inheritance over a graph needs custom functions. |
| Cerbos | Strongest SQL filter story of the external engines, but it runs as a separate service we would deploy beside every API instance. |
| OpenFGA, SpiceDB | Grants would live in their store and need syncing from ours. ADR5 wants one source of truth, read at request time. |
| Oso (open source) | Deprecated. Oso Cloud is a hosted service on the request path. |
| `purview-authz`, `sqla-authz` | The right idea, one rule for both checks and filters, but first released in 2026 and at version 0.x. Worth re-checking in a year. |

Cedar gives us three things we would otherwise build.

- **Hierarchy over a graph.** `resource in Scope::"project:12"` is true if
  project 12 is any ancestor of the resource, along any path.
- **Schema validation.** We declare entity types and actions once. A policy
  that names a misspelled action or impossible attribute fails at load time,
  not as a silent deny in production.
- **Explanation.** Each decision lists the ids of the policies that
  determined it. If each grant row becomes one policy with the row's id, the
  explanation is the grant id.

### 4.3 How grants become Cedar

We do not keep Cedar policy files for grants. On each request,
`services/authz` loads the caller's active grant rows and turns each into one
Cedar policy. A typical caller has a handful of rows, so this is cheap.

A `permission_grant` row

| id | principal | capability | scope | data_type |
|---|---|---|---|---|
| 412 | `principal_group:AMP Editor` | `update` | `program:AMP` | `groundwater level` |

becomes

```cedar
@id("grant-412")
permit (
  principal in PrincipalGroup::"AMP Editor",
  action in [Action::"update", Action::"read"],
  resource in Scope::"program:AMP"
)
when { resource.data_type == "groundwater level" };
```

`read` appears because `update` implies it (section 5.2). Time bounds do not
appear at all. The loader's SQL drops grants outside their dates before
Cedar sees them, so expiry is checked at use without Cedar knowing about
dates.

The entities passed with the request describe where the record sits.

```text
Observation::"88123"   attrs {data_type: "groundwater level"}
  parent  Thing::"4521"
Thing::"4521"
  parents Scope::"project:12", Scope::"project:40"
Scope::"project:12"
  parent  Scope::"program:AMP"
Scope::"project:40"
  parent  Scope::"global"
Scope::"program:AMP"
  parent  Scope::"global"
User::"<authentik sub>"
  parents PrincipalGroup::"AMP Editor"
```

Cedar then answers whether `User::"<sub>"` may `update` `Observation::"88123"`.
Here the answer is yes, because of `grant-412`.

### 4.4 The schema

A first cut, to be refined in the spike:

```cedar
entity PrincipalGroup;
entity User in [PrincipalGroup];
entity ApiKey;
entity Scope in [Scope];
entity Thing in [Scope];
entity Observation in [Thing] = { data_type: String };
entity Sample in [Thing]      = { data_type: String };

action read, create, update, delete, administer
  appliesTo { principal: [User, ApiKey], resource: [Thing, Observation, Sample, Scope] };
```

### 4.5 If we ever need deny

GCP added deny policies years after allow policies. If Ocotillo needs one,
for example "this student may read AMP data except well 4521," it is a Cedar
`forbid` policy, and in Cedar `forbid` always beats `permit`. That is a
decision for later. The v1 schema does not need to change to allow it.

### 4.6 What Cedar does not do for us

Cedar decides one request at a time. It cannot produce the `WHERE` clause
for "every water level this user may read." Cedar's partial evaluation can
in principle return a residual policy that could become SQL, but it is
experimental in the Rust engine, and we have not confirmed that `cedarpy`
exposes it. We plan as if it does not.

## 5. The helper library

Routes and services call these helpers and nothing else. No route imports
`cedarpy`. If we replace Cedar, only `services/authz/` changes.

### 5.1 Interface

```python
# services/authz/__init__.py  (illustrative signatures)

def resolve_principal(request) -> Principal:
    """Authentik JWT (sub + groups) or API key -> Principal with its active
    grants loaded once, in one query. Expired grants are filtered in SQL."""

def can(principal: Principal, capability: str, resource: Resource) -> bool:
    """Point check. Builds entities for `resource`, evaluates with Cedar."""

def require(capability: str, *, resource_from: Callable) -> Depends:
    """FastAPI dependency factory. 403 on deny. Replaces viewer_dependency
    and friends one route at a time."""

def visible(principal: Principal, capability: str, data_type: str) -> ColumnElement[bool]:
    """SQLAlchemy WHERE expression for list queries. Built from the same
    grant rows, not from Cedar."""

def explain(principal: Principal, capability: str, resource: Resource) -> Decision:
    """Allow or deny, plus the grant ids that decided it. For the console
    and for 403 debugging."""

def grant(actor: Principal, row: GrantInput, reason: str) -> PermissionGrant:
def revoke(actor: Principal, grant_id: int, reason: str) -> None:
    """The only writers of permission_grant. Enforce the delegation rule
    (section 3.4) and write the audit log in the same transaction."""
```

### 5.2 Capability implication

One table in code:

```python
IMPLIES = {
    "read":       {"read"},
    "create":     {"create", "read"},
    "update":     {"update", "read"},
    "delete":     {"delete", "read"},
    "administer": {"administer"},
}
```

`administer` does not imply `read`. Managing who may see AMP data and seeing
it are separate, as the vocabulary document says.

### 5.3 How `visible()` works

`visible()` turns the caller's grants for one capability and data type into
a SQL predicate. A `global` grant becomes `true`. A `thing` grant becomes
`thing_id = :id`. A `project` grant becomes an `EXISTS` over
`group_thing_association`, joined to a recursive CTE over `parent_group_id`
so child projects are covered. A `program` grant depends on how programs
attach to projects (open question 1). The predicates are ORed together, and
no grants gives `false`.

The OGC views need the same rule in SQL. We write it once more as a Postgres
function, `ocotillo_visible(principal, capability, data_type, thing_id)`, and
the views call it instead of carrying their own `release_status` logic.

That gives us three implementations of one rule: Cedar, `visible()`, and the
Postgres function. ADR5 warns that copies drift, so the copies are tested
against each other.

### 5.4 The parity test

A pytest module builds a fixture world with nested projects, a thing in two
projects, programs, and a mix of user, group, and API key grants, some
expired. For every principal, capability, data type, and record in that
world it asserts three things agree.

- `can()` through Cedar
- whether the record appears under `visible()`
- whether the record appears through `ocotillo_visible()`

A change to any one implementation that the others do not match fails CI.
This is the test that would have caught migration `baba91fe5e83`.

## 6. Request flow

```text
request
  -> resolve_principal()        one query: grants for sub, its groups, or the key
  -> require("update", ...)     single record: Cedar via can()
     or visible("read", ...)    list: SQL predicate ANDed into the query
  -> handler
  -> 403 body includes explain() output when MODE=development
```

Grants load once per request. Cedar evaluates in microseconds for a policy
set this size. List endpoints never call `can()` per row.

## 7. Risks

| Risk | Mitigation |
|---|---|
| `cedarpy` is a third-party binding and could stop being maintained. | Everything sits behind `services/authz/`. The fallback is a pure-Python `can()` over the same grant rows, about 150 lines, and the parity test already defines correct behavior for it. |
| Three implementations of one rule drift. | The parity test in 5.4, gating CI. |
| Generating policies per request is unusual for Cedar. | Measure in the spike. If it costs too much, cache compiled policy sets per principal, keyed on the latest grant change, so a revocation still applies on the next request. |
| The scope graph gets deep or wide. | Projects nest a few levels today. The recursive CTE and Cedar's ancestor walk both handle that. Revisit if a thing ends up in dozens of groups. |
| Seeding changes someone's access on day one. | Seed grants that reproduce today's Authentik behavior exactly (section 8, step 2), and test before and after for every route in `tests/test_authorization.py`. |

## 8. Plan

1. **Spike, one week.** Add `cedarpy`. Build `resolve_principal`, `can`,
   `explain`, and the schema. Put one read route and one write route behind
   `require()`. Measure per-request overhead. Write the parity test with
   `can()` and `visible()` only.
2. **Seed grants that reproduce today.** `Viewer` gets `read` on `global`
   for every data type. `Editor` adds `update`. `Admin` adds `create` and
   `delete`. `AMP.*` groups get the same capabilities on `program:AMP`.
   Nobody's access changes.
3. **Swap the dependencies.** Re-implement `viewer_dependency` and the
   others as `require()` calls. Route signatures stay the same.
4. **Lists and OGC views.** Move list services to `visible()`, add
   `ocotillo_visible()`, and point the OGC views at it. Extend the parity
   test to cover it.
5. **Narrow.** Replace broad seeded grants with program and project grants,
   starting with AMMP.
6. **Console.** `grant()`, `revoke()`, and `explain()` back the Operator
   Console screens in ADR6.

## 9. Open questions

1. **How does a thing belong to a program?** No column records it today.
   AMP is an Authentik group family, not a tag on records. Options are to
   make each program a root `Group` that projects nest under, or to add a
   program attribute to `Group`. The first fits the scope graph with no new
   concept.
2. **Field groups.** Cedar can carry `field_group` as a resource attribute,
   but the field projection belongs at ADR5's serialization chokepoint, not
   in a yes/no check. This needs its own design.
3. **API key principals in Cedar.** Keys have no groups. Do they get grants
   directly, or do we let a key belong to a principal group?
4. **`publication_consent`.** ADR5 says one engine evaluates both tables.
   Consent rows could become Cedar policies the same way grants do, with the
   anonymous public as a principal. This paper covers internal grants only.
5. **Where does `explain()` output go in production?** It names grants and
   groups. Returning it in a 403 body to any caller leaks how access is
   organized. Logging it is safe.

## References

- Google Cloud IAM overview and resource hierarchy:
  https://cloud.google.com/iam/docs/overview,
  https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy
- Google Cloud IAM deny policies: https://cloud.google.com/iam/docs/deny-overview
- Kubernetes RBAC, privilege escalation prevention:
  https://kubernetes.io/docs/reference/access-authn-authz/rbac/#privilege-escalation-prevention-and-bootstrapping
- Cedar language: https://www.cedarpolicy.com/
- `cedarpy`: https://pypi.org/project/cedarpy/
