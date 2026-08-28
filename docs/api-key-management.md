# API key management — design draft

Status: **draft, not implemented.** Branch `feat/api-key-management`.

Companion to [OcotilloUI#360](https://github.com/DataIntegrationGroup/OcotilloUI/pull/360),
whose settings page ships a generate / rename / revoke / one-time-reveal card
driven entirely by local component state. This document is the backend that card
is waiting on.

## What already exists

`core/internal_ogc_auth.py` gates the `/ogcapi-internal` mount and already
accepts a static API key on three transports (bearer, Basic password, `?token=`).
Those keys live as `label:sha256hex` entries in the `INTERNAL_OGC_API_KEYS`
environment variable, rendered from the Secret Manager secret
`internal-ogc-api-keys` at deploy time. See `docs/internal-ogc-desktop-gis.md`.

Two properties of that scheme are the reason this work exists:

- **Revoking a key requires a redeploy.** Adding a secret version does not touch
  a running instance.
- **Issuing a key requires an operator.** A user cannot get one themselves, and
  the label is bookkeeping only — a key is not attributable to a person in any
  enforced way.

That doc already names the exit: *"or to a keys table in Postgres."* This is it.

## The one security decision

An API key today is a pre-authorized stand-in for the `OGCInternal` Authentik
group. It buys access to the unfiltered, draft-inclusive internal collections.

So **the route that mints a key must be gated on the group the key stands in
for**, not on a general role. If key creation were gated on `viewer_dependency`,
any Viewer could mint themselves a credential that reaches the internal mount —
a privilege escalation with a UI button on it.

```python
# core/dependencies.py
internal_ogc_function = authenticated(any_of=["OGCInternal"])
internal_ogc_dependency: TypeAlias = Annotated[dict, Depends(internal_ogc_function)]
```

`INTERNAL_OGC_GROUP` currently lives in `core/permissions.py` precisely because
nothing Depends()-shaped needed it. This adds the first such consumer; the
constant stays where it is and `core/dependencies.py` references it.

Consequence for the UI: the API keys card is only meaningful for accounts in
`OGCInternal`. Everyone else should get an empty state explaining that, not a
Generate button that 403s. That is a change to PR #360.

## Scope: what a key authorizes

**Decided: v1 keys authorize `/ogcapi-internal` and nothing else.**

The alternative — a key that acts as its owner across the whole API — means
`authenticated()` has to accept a non-JWT credential and synthesize a payload
dict that every route reads claims from. Every `*_dependency` in
`core/dependencies.py` becomes reachable by a static string, and the blast radius
of a leaked key goes from "reads internal collections" to "writes anything its
owner can write." Not in the same change as the storage.

The table carries an explicit `scope` column set to `ogc_internal` for every row,
so widening later is a value, not a migration. No wildcard value — same reason
`ADR5.md` gives for grants having no term meaning "all."

## Storage

New model `db/api_key.py`, table `api_key`. Not in `db/permission.py`: that
`Permission` is a landowner's site-access consent and shares nothing with this.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | `AutoBaseMixin` |
| `name` | String(255) | User-supplied label. "Field laptop", "QGIS at the office". |
| `token_digest` | String(64), unique, indexed | SHA-256 hex. Same format the env-var parser already validates, so one comparison path serves both sources. |
| `token_preview` | String(32) | `ocot_ab12cd…wxyz`. All the list view ever shows. |
| `owner_sub` | String(255), indexed | Authentik `sub` claim. The owner of record. |
| `owner_name` | String(255), nullable | Display only, from `preferred_username`/`email`. Denormalized on purpose — there is no user table to join. |
| `scope` | String(50) | `ogc_internal`. See above. |
| `expires_at` | DateTime(tz), **not null** | Always set. See "Expiry" below — there is no never-expiring key. |
| `last_used_at` | DateTime(tz), nullable | |
| `revoked_at` | DateTime(tz), nullable | Soft. The row survives revocation so `last_used_at` and the audit trail survive with it. |

Plus `AuditMixin` for `created_at` / `created_by_*`.

There is no user table to key against — `db/base.py`'s `User` exists for audit
strings and nothing populates it. `owner_sub` is the identity, matching how
`AuditMixin` already records people.

### Token format and hashing

`ocot_` + `secrets.token_urlsafe(32)`. The prefix matches what
`src/utils/apiKeys.ts` already generates, so the reveal dialog is already sized
right.

Stored as unsalted SHA-256, deliberately, not bcrypt/argon2:

- The secret is 256 bits of CSPRNG output, not a password. There is no dictionary
  to attack and no rainbow table to build, so a salt buys nothing.
- Verification is a single indexed lookup by digest. A salted scheme forces a
  scan with one KDF invocation per row, which is a denial-of-service surface on
  an unauthenticated endpoint.
- It matches the existing digests in `INTERNAL_OGC_API_KEYS`, so both sources
  compare identically.

## Expiry

**Decided: every key expires, 365 days after creation by default.**

`domain/api_key.py` holds the rule as a plain function over plain values, per
`ADR4.md`:

```python
DEFAULT_LIFETIME = timedelta(days=365)
MAX_LIFETIME = DEFAULT_LIFETIME

def expiry_for(created_at: datetime, lifetime: timedelta | None = None) -> datetime
```

The create route accepts an optional shorter lifetime and clamps it to
`MAX_LIFETIME`. `expires_at` is `NOT NULL`: there is no way to ask for a key that
never expires. The operator-issued entries in `INTERNAL_OGC_API_KEYS` remain the
escape hatch for a credential that has to outlive that, and those are deliberately
harder to get.

Checked at use, in `resolve_api_key()`. Nothing sweeps the table — an expired row
stays for its `last_used_at` history, same rule `ADR5.md` sets for grants.

Two things follow from a lifetime this long, both worth stating plainly:

- **365 days is a backstop against abandoned keys, not a security control.** At
  that length the window is wide enough that expiry stops nobody who has stolen a
  key. What it does buy is that a key belonging to someone who left, or saved in
  an ArcGIS Pro dialog on a decommissioned laptop, eventually stops working
  without anyone remembering to revoke it. The real control is revocation, which
  this design makes instant — that is the whole reason the table exists.
- **A key will die silently in the middle of someone's work.** There is no email
  or notification infrastructure here, so the first sign is ArcGIS Pro or QGIS
  failing to connect, roughly a year after the person set it up and forgot about
  it. `expires_at` must therefore be in the list response and rendered in the UI,
  with a visible warning as it approaches — see the UI section below.

## Verification path

`services/api_key_auth.py`:

```python
def resolve_api_key(session, secret: str, *, now: datetime) -> ApiKeyPrincipal | None
```

Digest the presented secret, look it up, reject if `revoked_at` is set or
`expires_at` has passed. Expiry is checked **at use** — nothing sweeps the table,
same rule `ADR5.md` sets for grants.

`core/internal_ogc_auth.py` gains this as a second check, after the existing
`api_key_label()` env-var lookup and before the JWT decode. Order matters only
for cost: the env lookup is free, the DB lookup is a query.

Two wrinkles, both from the middleware being raw ASGI:

- **It has no DB session.** It opens a short-lived one from `db/engine.py`'s
  factory, only on the path where the env-var check has already missed, and
  closes it before calling through. It must not hold a session across the
  downstream `await` — the internal mount streams paginated GeoJSON up to
  `max_items: 10000`, and a session held for the response body would pin a pool
  connection for the whole stream.
- **No caching.** One indexed query per internal-mount request. A TTL cache would
  reintroduce exactly the revocation delay this work exists to remove; the mount's
  request rate does not justify trading that away.

`last_used_at` is written at most once per 15 minutes per key — compare in
Python, skip the write if it is already fresh — so a paging client does not turn
every page into a write.

## Routes

`api/api_key.py`, `APIRouter(prefix="/api_key", tags=["api_key"])`, singular to
match `/location`, `/contact`, `/asset`.

| Method | Path | Returns |
| --- | --- | --- |
| `POST` | `/api_key` | The full token, **once**. The only response that ever contains it. |
| `GET` | `/api_key` | The caller's own keys. Preview only. |
| `PATCH` | `/api_key/{id}` | Rename. `name` is the only mutable field. |
| `DELETE` | `/api_key/{id}` | Revoke — sets `revoked_at`, returns 204. Never deletes the row. |

Every route takes `user: internal_ogc_dependency` and filters on
`owner_sub == user["sub"]`. A key belonging to someone else is a 404, not a 403 —
existence of another person's key is not the caller's business.

No admin list-all route in v1. It is the obvious next ask, and it is a different
gate (general `Admin`, which confers nothing in this family), so it gets its own
change.

### Response shape

Matches `ApiKey` in `src/utils/apiKeys.ts` so the card swaps local state for
calls without reshaping:

```json
{
  "id": "12",
  "name": "Field laptop",
  "token": "ocot_…",           // POST only, never again
  "tokenPreview": "ocot_ab12cd…wxyz",
  "createdAt": "2026-08-28T17:04:00Z",
  "expiresAt": "2027-08-28T17:04:00Z",
  "lastUsedAt": null,
  "revokedAt": null
}
```

The UI's `id` is a string; the column is an int. Serialize as a string rather
than changing the UI type — it already treats the id as opaque.

## Relationship to the ADR5 access layer

`ADR5.md`, `services/visibility.py`, `domain/access.py`, and `api/access.py` are
**not on `staging`** — they are on `feat/ui-surface-grants`, unmerged. This
branch is based on `staging` and therefore cannot see them.

That is fine for v1, because a key of scope `ogc_internal` never consults the
grant evaluator: the internal mount is outside the field-projection chokepoint by
design. But the moment a key authorizes anything else, a key becomes a
*principal*, and the right move is a grant whose principal is the key — not a
second authorization path. That is the reason to keep v1 narrow.

If the grant layer merges first, `services/access_admin.py` writes an
`authorization_audit` row in the same transaction as every change, and key
issue/revoke should do the same.

## Env-var keys after this

Both sources stay live. `INTERNAL_OGC_API_KEYS` is not removed in this change:
existing holders have keys in ArcGIS Pro connection dialogs, and breaking them to
land a table is not worth it. Deprecation is a follow-up once holders have
re-issued from the settings page, at which point the Secret Manager secret goes
back to its inert placeholder.

## Tests

`tests/test_api_key.py`:

- POST returns the token; GET never does, for the same key.
- No stored column contains the token — assert on the row, not the response.
- A revoked key 401s on `/ogcapi-internal`; an expired key 401s; a valid one passes.
- Create sets `expires_at` 365 days out by default, honors a shorter requested
  lifetime, and clamps a longer one to the maximum.
- Revocation takes effect on the next request, with no redeploy and no cache flush.
- Another user's key is invisible to GET and 404s on PATCH and DELETE.
- A user without `OGCInternal` gets 403 on POST — the escalation test.
- Env-var keys still work with the table empty, and a table key still works with
  `INTERNAL_OGC_API_KEYS` unset.
- `tests/test_authorization.py`'s anonymous-route allowlist is unchanged: every
  new route is gated.

## Changes needed in OcotilloUI#360

The card as written does not carry everything the API returns, and one of its
assumptions is wrong for this design.

1. **`expiresAt` is a new field** on the `ApiKey` type in `src/utils/apiKeys.ts`,
   shown in the table and warned about as it nears — a key that stops working a
   year later with no warning is a support ticket, not a security win.
2. **The card is only meaningful for `OGCInternal` accounts.** Everyone else needs
   an empty state that says the keys are for desktop GIS access and how to request
   the group — not a Generate button that 403s. *Still open: hide the section
   entirely, or show it disabled with the explanation?*
3. `id` arrives as a string, as the UI already assumes; the column is an int
   serialized as one.

## Settled

- **Scope:** internal-only. Keys authorize `/ogcapi-internal` and nothing else.
- **Expiry:** 365 days by default, `NOT NULL`, clamped as the maximum, checked at
  use.
