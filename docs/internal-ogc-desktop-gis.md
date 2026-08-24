# Connecting ArcGIS Pro and QGIS to `/ogcapi-internal`

The internal OGC API mount serves the unfiltered (private- and draft-inclusive)
collections. It is gated by `core/internal_ogc_auth.py`, an ASGI middleware that
runs in front of the raw Starlette Mount — FastAPI's `Depends()` machinery never
sees these requests, so none of the `*_dependency` role parameters apply here.

## Why there are static API keys at all

The mount originally accepted only `Authorization: Bearer <Authentik JWT>`.
Neither desktop client can sustain that:

- **ArcGIS Pro** cannot send a bearer token to an OGC API connection. Its
  connection dialog offers Basic ("Server Authentication"), Esri-portal OAuth,
  and "Custom request parameters" (appended to the request URL). Esri
  [does not support token-secured OGC service connections](https://pro.arcgis.com/en/pro-app/latest/help/data/services/add-ogc-api-services.htm).
- **QGIS** can send one via its OAuth2 or API Header authentication methods, but
  shipped a regression where OGC API - Features requests dropped the
  Authorization header entirely ([qgis/QGIS#60473](https://github.com/qgis/QGIS/issues/60473)).

Neither client can refresh an Authentik access token before it expires, so even
a working bearer flow means re-pasting a token every hour. A static key issued
per user solves both problems.

## Accepted credentials

| Transport | Carries | Used by |
| --- | --- | --- |
| `Authorization: Bearer <secret>` | Authentik JWT **or** API key | QGIS OAuth2 / API Header, scripts |
| `Authorization: Basic <base64(user:secret)>` | API key (or JWT) as the password | ArcGIS Pro, QGIS Basic |
| `?token=<secret>` | API key (or JWT) | ArcGIS Pro custom request parameters |

A JWT must additionally carry the `OGCInternal` group (`INTERNAL_OGC_GROUP` in
`core/permissions.py`); a valid JWT without it gets 403. An API key is a
pre-authorized stand-in for that group and carries no per-user claims.

The `?token=` value is stripped from the query string before the request reaches
pygeoapi, so it never lands in the `self`/`next` links pygeoapi echoes into
response bodies. It is still recorded in App Engine's request log — prefer Basic
where the client supports it.

## Where the keys live

Only the **SHA-256 digests** are stored, never the keys themselves. The digest
list lives in a Google Secret Manager secret named `internal-ogc-api-keys`, one
per GCP project (production, staging, testing) — the same place the Jira and
Slack credentials live, not a GitHub secret.

CD reads it at deploy time (`Fetch application secrets from Secret Manager` in
each `.github/workflows/CD_*.yml`) and `envsubst` renders it into `app.yaml` as
the `INTERNAL_OGC_API_KEYS` environment variable, which
`core/internal_ogc_auth.py` parses. The app makes no Secret Manager call at
runtime.

Consequences worth knowing:

- **The secret must exist before the next deploy of any environment.**
  `get-secretmanager-secrets` fails the whole job on a missing secret. Seed each
  project with a placeholder that parses to zero keys:

  ```bash
  printf 'placeholder:none' | gcloud secrets create internal-ogc-api-keys --data-file=- --project <PROJECT_ID>
  ```

  The parser skips any entry whose digest is not 64 hex characters, so that
  value is inert and means "bearer-JWT access only".

- **Revoking a key requires a redeploy.** Adding a secret version does not
  affect a running instance. If revocation ever needs to be immediate, that is
  the point to switch to a runtime fetch with a TTL cache (same shape as the
  JWKS cache in `core/permissions.py`) or to a keys table in Postgres.

- The deploy service account needs `roles/secretmanager.secretAccessor` on
  `internal-ogc-api-keys` in each project, alongside the four it already has.

## Issuing a key

```bash
python -c "import secrets,hashlib;k=secrets.token_urlsafe(32);print('key:   ',k);print('digest:',hashlib.sha256(k.encode()).hexdigest())"
```

Give the **key** to the user over a secure channel and keep only the digest.
Append `<label>:<digest>` to the secret's value — comma- or whitespace-separated
entries, where the label is bookkeeping only (the person's name or the machine):

```bash
gcloud secrets versions add internal-ogc-api-keys --data-file=- --project <PROJECT_ID>
```

Then redeploy that environment. For local development set
`INTERNAL_OGC_API_KEYS` in `.env` directly; leaving it unset means bearer-JWT
access only.

## ArcGIS Pro

Basic auth (preferred):

1. **Insert** > **Connections** > **Server** > **New OGC API Server**.
2. Server URL: `https://<host>/ogcapi-internal`
3. Authentication: **Server Authentication**. User: anything (`apikey`).
   Password: the issued key. Check **Save Login** to persist it.

If Basic is refused by an intermediary, use the query parameter instead: leave
Authentication as **No Authentication** and add a custom request parameter with
name `token` and value the issued key. Pro re-appends it to every request it
issues, including paging.

## QGIS

1. **Layer** > **Data Source Manager** > **WFS / OGC API - Features** > **New**.
2. URL: `https://<host>/ogcapi-internal`
3. Authentication tab > **Create a new authentication configuration**:
   - **Basic authentication** — username `apikey`, password the issued key. Works
     on all supported QGIS versions.
   - Or **API Header** — header `Authorization`, value `Bearer <key>`. Avoid on
     3.40.3, where OGC API - Features drops the header.
4. **Connect**, then add the collections you need.

Staff who prefer real Authentik identity can instead configure QGIS's **OAuth2**
authentication method against the Authentik provider; the mount accepts those
tokens unchanged, provided the account is in `OGCInternal`.

## Advertised URLs

pygeoapi stamps an absolute server URL into every `links` href, and both clients
follow those links to page through `items`. `_internal_server_url()` in
`core/pygeoapi.py` derives that from `PYGEOAPI_SERVER_URL`'s application root, so
no additional deploy variable is required. Set
`PYGEOAPI_INTERNAL_SERVER_URL` only if the internal mount is served from a
different host than the public `/ogcapi` mount.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| 401 with `WWW-Authenticate: Basic` | No credential reached the server. In QGIS, confirm the auth config is selected on the *connection*, not just created. |
| 403 | Valid Authentik token, but the account is not in the `OGCInternal` group. |
| 424 | `AUTHENTIK_DISABLE_AUTHENTICATION=1` with `MODE` other than `development`. Misconfigured deploy. |
| First page loads, paging fails against `localhost` | `PYGEOAPI_SERVER_URL` unset or wrong for the environment. |
