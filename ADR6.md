# ADR6: Operator Console

## Propose

This record defines the Ocotillo Operator Console's initial location, responsibilities, and
architectural boundaries. It builds on ADR5 (One Enforcement Engine, Two Grant Tables) and the
Ocotillo Access-Control Vocabulary and Scope Taxonomy.

## Summary

Ocotillo needs an administrative interface that lets authorized users manage permissions, principal
groups, API keys, and review activity without direct database access, changes to Authentik
configuration, or engineering intervention.

**Decision**: Build the Operator Console as an authorization-gated sub-route within Ocotillo, with
Ocotillo owning authorization and Authentik retaining responsibility for authentication.

The console will initially serve as the administrative interface for scope-based access control
(SBAC) and API key lifecycle management.

Ocotillo will manage principal groups and their associated grants in its database. Groups will serve
as reusable collections of explicitly defined permissions, allowing administrators to assign or
remove access without changing application code or authentication-provider configuration.

A single append-only activity log will capture authorization changes and other selected operational
events. Events will be classified by type and protected by a SHA-256 hash chain to support integrity
verification.

API keys will have a default and maximum lifetime of 365 days, with a 30-day rotation overlap.
Expiration warnings will appear in the console and be delivered by email.

Performance optimizations, including authorization caching, will be deferred until baseline
measurements identify a need.

The console provides the administrative surface for authorization. It does not become a second
authorization engine.

## Context

### 0. Administrative operations currently lack a unified surface

Ocotillo’s existing access-control behavior is distributed between Authentik group membership,
application-level authorization checks, static API credentials, and database records.

Some administrative operations require configuration changes, updating group membership in
Authentik, or involving an engineer.

As Ocotillo expands to support multiple research programs, students, collaborators, and federal
harvesters, this arrangement becomes difficult to administer consistently.

ADR5 establishes two independently governed authorization data sources:

- `permission_grant` — internal authorization.
- `publication_consent` — landowner-approved publication.

Both are evaluated through one shared visibility engine.

The Operator Console is the administrative interface through which authorized users will eventually
manage these policies.

The immediate need is an interface for internal permission and API-key management.
Publication-consent administration must retain the governance separation established by ADR5, even
if it is eventually exposed through the same console.

The console should not require a separate application or operational deployment solely to administer
Ocotillo resources.

### 1. Authentication and authorization must be separated

Authentik currently serves as both the identity provider and a source of authorization through role
names interpreted by application code.

This creates an administrative dependency on the authentication system for changes that are
fundamentally authorization decisions.

Under the proposed model:

**Authentik owns authentication**:

- User identity and stable subject identifiers.
- Credentials and authentication sessions.
- Multifactor authentication.
- Identity-provider account lifecycle.

**Ocotillo owns authorization**:

- Principal identities used for authorization.
- Permission grants and their scopes.
- Principal groups and grant assignments.
- API-key authorization.
- Authorization delegation and revocation.

An authenticated user does not automatically receive access to a resource. The shared policy engine
determines what that user is allowed to do.

Treat groups as administrative conveniences for assigning sets of grants, not as hardcoded
application roles with implicit permissions.

A group such as `AMMP Viewer` should have an inspectable collection of grants. Administrators should
be able to determine exactly what access the group confers before assigning a principal to it.

The existing `Group` model used to organize domain resources should not be confused with principal
groups used for authorization.

### 2. Administrative delegation must support program-level governance

Centralizing every permission change under a small number of system administrators would create a
management bottleneck as Ocotillo grows.

The console should support authorized program managers and other delegated operators managing access
within their responsibilities.

For example, an AMMP program manager may need to add a student to an AMMP permission group or revoke
that student’s access when their work ends.

Such delegation must not allow the manager to grant access outside their authorized scope.

The capability to `administer` access is distinct from the capability to read or modify scientific
data.

The console therefore needs to support two kinds of questions:

1. What capabilities and scopes does a principal currently possess?
2. What capabilities and scopes is the current operator authorized to grant or revoke?

A user must not be able to expand their own administrative authority by creating broader grants or
modifying group definitions beyond their delegated scope.

Cross-program grants or assignments that exceed a program manager’s authority may require escalation
to the data services team.

The exact delegation hierarchy and group-administration permissions remain undefined.

### 3. Authorization changes and operational activity require a unified audit trail

Ocotillo already records some operations in a historical Slack channel, but it does not provide a
complete audit trail of administrative activity.

The system needs to answer basic questions following an authorization incident or unexpected change:

- Who performed the operation?
- What operation was performed?
- When did it happen?
- Which principal, resource, or grant was affected?
- What changed?

Maintaining separate, unrelated logs for authorization events and general administrative activity
would complicate investigation and administration. A single activity log with explicit event
classification would allow authorized users to search, sort, and filter events by type.

Authorization events and relevant data operations should therefore share one logical activity-log
structure, without requiring every HTTP request or GIS feature read to generate a persistent audit
entry.

To support integrity verification, log records will include a SHA-256 hash calculated from a
canonical representation of the event and the preceding event’s hash.

From the application’s perspective, the log must be append-only. Administrative users may view
events according to their permissions but must not edit or delete existing events.

Hash chaining makes unauthorized modification detectable when the chain is verified against a
trusted checkpoint. It does not, by itself, prevent a database administrator or attacker with
sufficient privileges from rewriting an entire chain. Database permissions, protected checkpoints,
and verification procedures are therefore necessary parts of the design.

### 4. API-key management, GIS compatibility, and performance

Ocotillo’s internal OGC services support conventional Authentik JWTs and API-key credentials,
including query-parameter transport used by desktop GIS clients.

Database-backed API keys already support expiration and revocation. Static API-key configuration
will be deprecated. This record covers database-backed API-key management.

Currently, API Key management is done in the user’s settings page. Move it out of that page and into
the console, which should provide a consistent administrative interface to issue, review, rotate,
and revoke database-backed API keys.

API keys should have a default and maximum lifetime of 365 days. A 30-day rotation overlap allows an
existing key and a replacement key to remain valid simultaneously while desktop GIS connections are
migrated.

Expiration warnings should appear in the console and be delivered by email.

Desktop GIS clients such as ArcGIS Pro and QGIS may have limitations or differences in how they
configure authorization headers for OGC connections. Query-parameter authentication therefore
remains a practical compatibility mechanism.

Because credentials in URLs may be exposed through access logs and monitoring systems, Ocotillo must
redact authentication parameters throughout its logging infrastructure.

The shared authorization engine will initially validate active grants directly against the database.

## Decisions

### 0. Implement the Operator Console within Ocotillo

The Operator Console will be implemented as an authorization-gated route within the existing
Ocotillo application.

It will reuse the application’s identity context, backend services, and established user-interface
infrastructure.

Initial functionality will include:

- Viewing principals and their effective permissions.
- Viewing and administering authorized principal groups.
- Inspecting the grants associated with each group.
- Assigning and revoking permissions within an operator’s authorized scope.
- Creating and managing database-backed API keys.
- Viewing API-key expiration and revocation status.
- Viewing relevant activity and authorization-change history.

The console’s interface must be gated by server-side authorization. Hiding navigation elements or
pages in the frontend is not sufficient protection.

The administer capability will govern access-management operations, subject to the operator’s
permitted scope.

The precise UI placement—navigation page, settings subsection, or another arrangement—will be
determined through interface design and review. This decision establishes that the console belongs
within Ocotillo, not the final navigation layout.

The initial implementation will focus on access control and API-key administration.

### 1. Manage authorization and principal groups in Ocotillo

Authentik will remain the identity provider, while Ocotillo will maintain the authorization records
the shared policy engine uses.

Ocotillo’s authorization model will represent principal groups.

A group represents a reusable, named collection of explicitly defined permission grants.

Principals may be assigned to multiple groups and may receive direct grants where their
authorization requirements are unique.

The console must expose the grants associated with each group before an operator assigns that group
to a principal.

Group membership changes and grant modifications must become effective through the shared
authorization engine without requiring application code changes or redeployment.

Program-level administrators may manage grants and memberships only within their delegated
authorization scope.

The implementation must prevent privilege escalation, including cases where a delegated operator
attempts to assign a group containing grants broader than the operator is authorized to administer.

Internal authorization continues to use ADR5’s `permission_grant` model.

Landowner publication approval continues to use `publication_consent`. Its independent governance
and administrative responsibilities must not be collapsed into internal group administration.

Both authorization sources continue to feed the same shared visibility engine and field-projection
enforcement point.

### 2. Establish one append-only activity log

Ocotillo will maintain a unified activity-log structure with event classification.

The initial event categories should include:

- Authorization grant creation, modification, and revocation.
- Principal-group creation and membership changes.
- API-key creation, rotation, expiration, and revocation.
- Publication-consent and publication-configuration changes.
- Selected consequential data modifications and deletions.
- Other administrative operations identified during implementation.

Each event will record, at minimum:

- A unique event identifier.
- Event type.
- Acting principal.
- Event timestamp.
- Affected resource or authorization object.
- Relevant event metadata (depends on the event and is nullable).
- Previous event hash.
- Current event hash.

The hash chain will use SHA-256, with a canonical event representation that includes the preceding
event hash.

Integrity verification must be possible without allowing normal application or administrative users
to rewrite history.

Application-level logging will capture the acting principal and operation context. Database-level
protections or supplementary capture mechanisms should protect against writes that bypass the normal
application path.

The console will expose searchable and filterable activity history to appropriately authorized
users.

Delegated program administrators should generally be limited to activity relevant to their
authorized programs. Broader log access requires separate authorization.

Existing data versioning may continue to serve record-history and rollback requirements; the unified
activity log is not intended to replace those mechanisms.

The exact event schema, retention requirements, chain verification process, and trusted checkpoint
storage remain implementation decisions.

### 3. Define API-key lifecycle and defer premature optimization

Database-backed API keys will use the following defaults:

- Default lifetime: 365 days.
- Maximum lifetime: 365 days.
- Rotation overlap: Up to 30 days before expiration.
- Expiration notifications: 45, 30, 14, 7, and 1 day before expiration.
- Notification channels: Operator Console and email.
- Revocation: Available to authorized administrators and, where permitted, the key owner.
- Compromised credentials: Immediately revocable without waiting for the rotation window.

A rotation creates a replacement credential while the existing key remains valid until its scheduled
expiration or earlier revocation. The overlap does not extend the old key’s original expiration.

The console should display key ownership, relevant authorization scope, creation date, expiration
date, revocation status, and last-used information when available. Do not expose raw API-key secrets
again after initial showing.

API keys must be evaluated through the same authorization engine as other principals. The key’s
validity does not independently authorize access beyond its current grants.

## Why not the alternatives

### A standalone operator-console application.

A separate application would add another deployment, authentication integration, and maintenance
boundary for functionality specific to Ocotillo.

The current requirements do not justify that additional operational complexity.

### Managing authorization groups solely through Authentik.

This preserves the existing dependency on authentication-provider configuration for authorization
administration and limits delegated operators' ability to manage access through Ocotillo.

Authentik should identify users; Ocotillo should determine what those identities are permitted to
do.

### Assigning every individual grant manually or through scripts.

Individual grants remain useful for exceptional cases, but repeatedly assigning common permission
sets creates administrative overhead.

Explicit, inspectable groups provide a simpler administrative abstraction without changing the
underlying grant model.

### Separate authorization and activity-log tables.

Separate logs may simplify specialized storage, but they fragment administrative history and
complicate reconstruction of related events.

A shared logical activity log with event classification better supports the initial console
requirements.

### Authorization-result caching from the first implementation.

Caching introduces invalidation, stale-state, and multi-worker consistency concerns before a
measured performance problem exists.

Direct database validation provides a simpler starting point and makes revocation behavior easier to
reason about.

### A custom desktop GIS authentication proxy.

A local proxy could remove reusable credentials from GIS connection URLs, but would require
additional software distribution, platform support, credential storage, and OGC protocol handling.

The initial decision favors lower-cost mitigations such as HTTPS, log redaction, scoped credentials,
and revocation. The risk may be reassessed later.

## What this does not decide

- **Final UI navigation**. Whether the console appears as a dedicated navigation item, under
  settings, or through another arrangement requires design review.
- **Exact database schema**. Principal groups, group memberships, reusable grant definitions, and
  grant assignments require further modeling with the authorization implementation team.
- **Delegation boundaries**. Which operators may create groups, modify group grants, manage
  memberships, or authorize cross-program access remains to be formalized.
- **Grant conflict resolution**. Evaluation of overlapping or conflicting permissions remains a
  shared-engine policy decision.
- **Publication-consent administration**. The console may eventually expose consent-management
  functionality, but ADR5’s separate governance model remains in force.
- **Audit-log completeness**. The exact activity types, metadata, retention period, event ordering,
  and before-and-after capture requirements need further review.
- **Audit integrity infrastructure**. Hash-chain checkpoints, database-level protections,
  verification schedules, and protection against privileged tampering require implementation design.
- **Performance optimization**. No authorization-cache architecture or TTL is selected until
  baseline measurements identify a bottleneck.

## Consequences

### **Good**.

Authorized staff can administer access without requiring direct database edits, redeployments, or
routine changes to Authentik.

Group definitions become explicit and inspectable, allowing an operator to understand the
capabilities assigned to a principal before granting access.

Delegated program administrators can manage appropriate permissions while central administrators
retain oversight of broader authorization.

API-key lifecycle management becomes visible and operationally manageable, improving awareness of
expirations, rotation, and incident response.

A unified activity log improves accountability and supports investigations, program oversight, and
administrative transparency.

The console provides a common administrative interface without creating a competing authorization
engine.

### **Cost**.

Ocotillo becomes responsible for the correctness and security of authorization administration,
principal-group membership, and delegated access-management operations.

The activity log introduces storage, integrity-verification, and access-control responsibilities.

Email notifications and API-key rotation require supporting lifecycle processes.

The shared authorization engine introduces database reads into protected request paths. Monitor
performance, and optimization may become necessary as usage increases.

Query-parameter authentication continues to carry credential-exposure risk outside the locations
controlled by server-side logging. That risk is mitigated, not eliminated.

### Operational requirement.

The Operator Console must never become an alternative path around ADR5’s shared authorization and
visibility rules.

All administrative actions must be validated server-side, recorded in the activity log where
applicable, and constrained by the acting principal’s effective administrative authority.

## Sequencing implied by this decision

1. Establish Ocotillo-managed groups, permission grants, and the necessary backend authorization
   endpoints for controlling the authorization changes.
2. Establish the activity-log foundation. Define initial event types, minimum event metadata,
   append-only protections, and SHA-256 hash-chain construction before enabling administrative
   mutations through the console.
3. Implement the gated console interface. Introduce the console within Ocotillo with principal,
   group, grant, and effective-permission views. Enforce all administrative operations server-side.
4. Create an email notification system in Ocotillo and attach an active email address to each
   principal. Then enforce a policy requiring all principals to have an associated email address.
5. Introduce API-key administration to the operator console. Expose key creation, status,
   expiration, revocation, and rotation workflows, together with console and email notifications.
   Validate the existing key implementation against the agreed lifecycle policy.
6. Support delegated administration. Add scope-limited grant and group management for empowered
   principles after validating delegation rules and privilege-escalation protections.
7. Measure performance and refine. Benchmark authorization checks, high-frequency reads, and
   activity logging under representative workloads. Introduce caching or usage-metadata
   optimizations only when measurements justify them.
8. Expand only after the initial console is stable. Consider publication-consent administration,
   user preferences, saved queries, and other features through separate requirements and design
   review.

## Glossary

| Term                | Definition                                                                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Authentication      | Verification of an identity or credential. Managed primarily by Authentik.                                                                             |
| Authorization       | Determination of what an identified principal is permitted to do. Owned by Ocotillo.                                                                   |
| Principal           | An identity evaluated for authorization, such as a user, principal group, or API key.                                                                  |
| Principal Group     | A named administrative collection through which principals receive a reusable set of grants.                                                           |
| Capability          | An action a principal may perform, such as read, create, update, delete, or administer, subject to final vocabulary alignment.                         |
| Scope               | The resource boundaries within which a capability applies, such as global, project, thing, or program, with additional data-type or field constraints. |
| Permission Grant    | An authorization record describing a permitted capability and its applicable recipient and scope.                                                      |
| Publication Consent | A separately governed record authorizing disclosure of particular data to a publication destination, as defined in ADR5.                               |
| Visibility Engine   | The shared server-side policy-evaluation mechanism that resolves applicable permissions and publication rules.                                         |
| Rotation Overlap    | The controlled period during which an existing API key and its replacement are simultaneously valid.                                                   |
| Activity Log        | The unified, append-only record of selected authorization and operational events.                                                                      |
| Hash Chain          | An integrity-verification structure in which each event hash incorporates the previous event’s hash and the current event’s canonical content.         |
| Operator Console    | Ocotillo’s gated administrative interface for managing authorization, credentials, and relevant operational information.                               |

## References

- Confluence, Ocotillo space: Who May See What, and Who May Do What: A scope-based, attribute-level
  access control system for Ocotillo.
- Confluence, Ocotillo space: Ocotillo Needs an Operator Console.
- ADR5: One Enforcement Engine, Two Grant Tables.
- Ocotillo Access-Control Vocabulary and Scope Taxonomy.
- Technical Feasibility Review, October 29, 2026 — operator console, authorization, audit logging,
  API-key lifecycle, and GIS authentication discussion.
- Authentik Access-Control Matrix Summary and Role Definitions.
- services/api_key_auth.py: Database-backed API-key authentication.
