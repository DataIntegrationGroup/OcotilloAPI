# API Monitoring & Public Status Page — Options and Recommendation

**Purpose:** Choose how to (1) monitor the OcotilloAPI production deployment (FastAPI + PostgreSQL/PostGIS on Google App Engine) and (2) publish a **public status page** so users and developers can see live service health, incidents, and planned maintenance.

**Out of scope:** Full APM/tracing platforms (SigNoz, Grafana Tempo, Datadog APM). Those are a heavier, separate decision. This doc is about uptime/health checks and a status page.

**Date:** 2026-07-07

---

## TL;DR

- **Recommended: [OpenStatus](https://www.openstatus.dev/).** It is the only option that combines a **first-class public status page**, **monitoring-as-code** (YAML + Terraform, matching this repo's config-as-code habits), and a **SaaS-to-self-host path** — start managed, migrate later without switching tools.
- **Start on the SaaS free tier**, monitoring `https://<prod-host>/health`, published to a custom-domain status page. Zero infrastructure, external probe vantage by default. Commit the monitor definition (YAML/Terraform) to the repo.
- **If config-as-code is not a requirement**, the fastest polished alternatives are **Better Stack** (free, all-in-one) or **Instatus** (best-looking page, ~$15/mo).
- **Non-negotiable constraint:** the probe must run **outside GCP**. A status page that goes dark during a platform outage is worthless — see [Probe independence](#probe-independence).

---

## What we need

OcotilloAPI is a FastAPI service backed by PostgreSQL + PostGIS, deployed on App Engine. The monitoring + status-page solution should cover:

- **Reachability** of the public API — HTTP/HTTPS status codes and TLS certificate validity/expiry.
- **Health-endpoint assertion** — check `/health` and assert the JSON body, not just a 200.
- **Response-time thresholds** — flag slow spatial queries before users notice.
- **Alerting** to a channel the team watches (email, Slack, PagerDuty).
- **A public status page** — a branded page users and developers can visit for current uptime, incident history, and scheduled maintenance, with email/RSS/webhook subscriptions.
- **Config-as-code** (preferred) — monitor definitions versioned in the repo, consistent with this project's release-please, templated `app.yaml`, and `geoserver_iac/` Terraform.

### Health endpoint

A monitor is only as good as what it checks. `/health` already exists (`core/app.py`) but currently returns `{"status": "ok", "version": ...}` **without** touching the database — a 200 from it does not prove PostGIS is reachable. Before wiring up monitoring, extend it to verify DB connectivity so the status page reflects real health:

```python
@router.get("/health")
async def health(session=Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok", "version": settings.version}
```

Every tool below can assert on `"db": "ok"` (JSON query or body match).

### Probe independence

A status page exists to be trustworthy **when the service is down**. If the monitor runs inside the same GCP project / App Engine service it watches, a platform-level outage takes the status page down with it — exactly when users need it. Therefore:

- Prefer a **SaaS probe** (checks from external regions), or
- Self-host the probe on **separate infrastructure** (different provider/region), never on the monitored App Engine service.

This rules out running the monitor as just another container in the production stack.

---

## Recommendation

**Adopt OpenStatus, starting on the managed SaaS free tier.**

Rationale, weighted to the stated goal (public status page for users + developers):

1. **The status page is the product, not a side feature.** Custom domain, branded theme, timestamped incident reports, scheduled maintenance windows, and automatic status updates during incidents. Users and developers self-subscribe via email, RSS/Atom, or webhook.
2. **Monitoring-as-code.** Checks are defined in YAML with a Terraform provider, CLI, and GitHub Actions integration — the same config-as-code model already used for deployments here. Monitor changes become reviewable commits.
3. **No lock-in on hosting.** Begin on SaaS (zero infra, external probe vantage) and migrate to self-hosted later if cost or data-residency demands it — same tool, same config. Most tools force an either/or.
4. **Fits the endpoint we have.** HTTP checks assert on `/health` status, latency, and JSON body.

**Trade-offs to accept:** AGPL-3.0 license (fine for internal self-hosting; matters only if the code is modified *and* redistributed); the SaaS free tier is limited to one monitor / one status page / 10-minute checks (≈$30/mo unlocks more monitors and faster intervals); smaller community than Uptime Kuma, maintained by a small bootstrapped team.

**If config-as-code is dropped as a requirement**, pick for speed instead:
- **Better Stack** — all-in-one uptime + incident + status page, generous free tier.
- **Instatus** — the best-looking, fastest-loading status page; ~$15/mo with basic monitoring included.

### Rollout plan

1. Extend `/health` to verify PostGIS connectivity (snippet above).
2. Create an OpenStatus SaaS account (free tier). Add one HTTP monitor on `https://<prod-host>/health` asserting `[STATUS] == 200`, `[BODY].db == ok`, and a response-time ceiling.
3. Publish a public status page on a custom domain (e.g. `status.<domain>`); enable email/RSS subscriptions.
4. Wire alerts to the team's Slack (and PagerDuty if used).
5. Export the monitor as YAML/Terraform and commit it to the repo so the config is versioned.
6. Revisit self-hosting (or a paid tier) only when more monitors or sub-10-minute intervals are needed.

---

## Shortlist

The five worth serious consideration, in priority order for this project:

1. **OpenStatus** *(recommended)* — status-page-first, config-as-code, SaaS-or-self-host. Best overall fit.
2. **Better Stack** *(SaaS, zero-ops)* — all-in-one, generous free tier; pick if you want managed and don't need config-as-code.
3. **Instatus** *(SaaS, prettiest page)* — cheapest polished public page; monitoring is basic.
4. **Gatus** *(self-host, GitOps)* — excellent YAML health checks, but a thin status page; pick if internal monitoring matters more than the public page.
5. **Uptime Kuma** *(self-host, easiest UI)* — friendly dashboard and a decent status page, but single-location probe and no native GitOps.

Everything else below is context for why these five rise to the top.

---

## Full catalog

### Self-hosted, open source

- **OpenStatus** — AGPL-3.0, TypeScript. Status page + monitoring + incidents; YAML/Terraform config; also offered as SaaS. *(Shortlisted #1.)*
- **Gatus** — Apache-2.0, Go. Config-as-code health checks with JSON body assertions and flap-resistant thresholds; lightweight built-in dashboard; thin status page. *(Shortlisted #4.)*
- **Uptime Kuma** — MIT, Node/Vue. ~76k★, the most popular self-hosted monitor; rich UI + status page; single-location probe; config lives in its DB (no native GitOps). *(Shortlisted #5.)*
- **OneUptime** — open-source all-in-one suite (monitoring + status page + incidents + on-call). The closest full-suite rival to OpenStatus; heavier to run; self-host or cloud.
- **Checkmate** (ex-BlueWave Uptime) — React/Node/Mongo; modern UI; active but newer/smaller community.
- **Cachet** — the original OSS status page. **Caution:** last release 2023, mid a v3.0 rewrite; status-page-only (needs a separate monitor).
- **Statping-ng** — all-in-one monitor + page; dated UI, uncertain maintenance.
- **Vigil** / **Uptimepage** — Rust, microservice-oriented; fast standalone binaries; sparser status-page polish, more infra effort.
- **Prometheus Blackbox Exporter** — Apache-2.0, Go. Probe-to-metrics; production-grade but a *component*, not a product — assumes a Prometheus + Alertmanager (+ Grafana) stack, and has **no status page**. Right choice only once Prometheus exists for broader infra metrics.

### SaaS (external probe by default — satisfies probe independence)

- **Better Stack** — all-in-one uptime + incident management + status page; generous free tier. *(Shortlisted #2.)*
- **Instatus** — best-looking, fastest status pages; ~$15/mo; basic monitoring included. *(Shortlisted #3.)*
- **UptimeRobot** — cheapest/free uptime + status pages; simple.
- **Atlassian Statuspage** — the polished incumbent for incident communication; pricier.
- **Checkly** — monitoring-as-code (Playwright, Terraform); very developer/GitOps-oriented; pricier and broader than a status page.
- **incident.io** — Slack-centric incident management + status page; priced for incident-heavy teams.

---

## Comparison

Focused on the shortlist plus the two reference points from the original evaluation (Blackbox, as the Prometheus path).

| Criterion | OpenStatus | Better Stack | Instatus | Gatus | Uptime Kuma | Blackbox Exporter |
|---|---|---|---|---|---|---|
| Hosting | SaaS **or** self-host | SaaS | SaaS | Self-host | Self-host | Self-host |
| License (self-host) | AGPL-3.0 | — | — | Apache-2.0 | MIT | Apache-2.0 |
| Public status page | **First-class** | Yes | **Best-looking** | Basic | Yes | No |
| Status-page subscriptions | Email/RSS/webhook | Email/SMS/webhook | Email/Slack/webhook | No | Limited | No |
| Config-as-code | Yes (YAML + Terraform) | Partial (API/TF) | No | **Yes (native)** | No | Yes |
| JSON health-body assertion | Yes | Yes | Basic | Yes (`[BODY]`) | Yes (JSON query) | Regex on body |
| TLS expiry checks | Yes | Yes | Yes | Yes | Yes | Yes |
| Alerting | Slack/Discord/PagerDuty/email/webhook | Many + on-call | Slack/email/webhook | Many built-in | Many built-in | Via Alertmanager |
| External probe by default | Yes (SaaS) | Yes | Yes | No (you host) | No (you host) | No (you host) |
| Setup effort | Low (SaaS) / Med (self-host) | Low | Low | Low (1 container) | Low (1 container) | High (full stack) |
| Best when… | Public page **+** config-as-code | Managed all-in-one, free | Prettiest page, cheap | GitOps health checks | Friendly UI fast | Already run Prometheus |

---

## Decision guide

- **Want a public status page *and* config-as-code (the stated goal):** → **OpenStatus**.
- **Want managed, all-in-one, free to start, don't care about GitOps:** → **Better Stack**.
- **Want the prettiest public page for the least money:** → **Instatus** (or **UptimeRobot** if cost is the only axis).
- **Care most about versioned internal health checks, public page secondary:** → **Gatus** (pair with a status-page tool later).
- **Want the quickest friendly UI, self-hosted:** → **Uptime Kuma**.
- **Already adopting Prometheus for infra metrics:** → **Blackbox Exporter**, folded into that stack.

---

## Sources

- [OpenStatus — official site](https://www.openstatus.dev/)
- [OpenStatus — GitHub](https://github.com/openstatusHQ/openstatus)
- [OpenStatus — self-hosting guide](https://docs.openstatus.dev/guides/self-hosting-openstatus/)
- [OpenStatus — self-host status page only (lightweight)](https://docs.openstatus.dev/guides/self-host-status-page-only/)
- [OpenStatus — Best Open Source Status Page Tools in 2026](https://www.openstatus.dev/guides/best-opensource-status-page-2026)
- [UptimeRobot — Best Status Page Tools in 2026 (SaaS and open source)](https://uptimerobot.com/knowledge-hub/comparisons-and-alternatives/best-status-page-tools/)
- [Hyperping — Top Statuspage Alternatives (2026)](https://hyperping.com/blog/best-statuspage-alternatives)
- [OneUptime — Best Statuspage Alternatives (2026)](https://oneuptime.com/blog/post/2026-03-10-best-statuspage-alternatives/view)
- [Instatus — Best Self-Hosted Status Pages for 2026](https://instatus.com/blog/best-self-hosted-status-pages)
- [awesome-status-pages (curated list)](https://github.com/ivbeg/awesome-status-pages)
- [Uptime Kuma — GitHub](https://github.com/louislam/uptime-kuma)
- [Gatus — GitHub](https://github.com/TwiN/gatus)
- [Prometheus Blackbox Exporter — GitHub](https://github.com/prometheus/blackbox_exporter)
