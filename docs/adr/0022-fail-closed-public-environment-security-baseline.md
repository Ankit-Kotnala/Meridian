# ADR 0022: Fail-closed public-environment security baseline

- Status: Accepted
- Date: 2026-09-30
- Deciders: Engineering

## Context

Rezumi's cloud-portable demo profile intentionally uses `staging` while it is
being prepared for a public HTTPS domain. The prior configuration model applied
several critical safety checks only when `REZUMI_ENVIRONMENT=production`. A
misconfigured staging deployment could therefore start with local service names,
default credentials, non-secure cookies, a local SMTP sink, disabled scanning,
or cacheable user-facing API responses.

Staging may contain real accounts, resumes, evidence, sessions, and OAuth
credentials. Its exposure boundary is public even when its availability and
support guarantees differ from production.

## Decision

Treat `staging` and `production` as public environments for configuration and
transport hardening.

- API startup rejects debug logging, interactive API docs, local/wildcard hosts,
  local/default database, Redis, S3, SMTP, scanner, and secret configuration.
  It requires HTTPS browser origins, secure cookies, authenticated TLS SMTP,
  non-local encrypted Redis/object storage, ClamAV, and TLS MongoDB when MongoDB
  is enabled.
- Worker startup applies the same public baseline to local/default database,
  object storage, scanner, and Celery broker/result-backend configuration. QStash
  remains its signed HTTPS delivery alternative.
- Every API response receives explicit no-store and browser security headers.
  HSTS is enabled in public environments. The web application extends its
  existing CSP/anti-framing header baseline with HSTS only in production builds.
- API and worker containers use a digest-pinned, supported CPython 3.14 runtime.
  High-severity fixed base-image findings block the image security gate instead
  of being ignored.
- Web and edge containers likewise use a digest-pinned Node 24.21.0 image,
  removing the fixable Node findings in the previously pinned 24.18.0 base.
- The final web image is built after an npm production-only prune; TypeScript,
  test, lint, and other development tooling are not copied into the runtime
  container.
- Grype uses no application-level allowlist. The gate evaluates every reported
  issue and blocks all fixable high or critical findings in the exact images
  built for release.
- Local Compose and `development`/`test` retain their current safe-for-local
  defaults. This avoids requiring public secrets or network services for tests.

## Rollout and rollback

1. Add all required managed secrets and exact public host/origin values in the
   platform's protected environment settings.
2. Deploy the API and worker. A rejected configuration is a safe startup failure;
   correct the reported setting instead of relabelling a public deployment as
   `development` or disabling the scanner.
3. Verify header, CORS/CSRF, private-object, scanner, OAuth, and secret-rotation
   behavior through the deployed HTTPS domains using the deployment checklist.

Rollback is a normal application release rollback after assessing the security
impact. It is not acceptable to bypass this decision by downgrading a public
service to a local environment label, allowing wildcard origins, retaining
default credentials, or disabling malware scanning.

## Consequences

### Positive

- Public demo deployments fail before processing user data if essential security
  controls are missing.
- The API explicitly prevents browser and intermediary storage of responses that
  can contain user data.
- Operators receive a concise deployment checklist for the existing Render,
  Railway, Cloudflare, R2, QStash, and managed-database topology.

### Costs and risks

- Staging now requires real managed service credentials, an authenticated SMTP
  provider, encrypted Redis, and a reachable isolated ClamAV service.
- HSTS is intentionally domain-only and omits `includeSubDomains`/`preload` so a
  hosted-preview platform cannot accidentally lock unrelated subdomains into an
  HTTPS policy it does not control.
- This does not make a hosted deployment automatically safe: provider IAM,
  backup/retention, edge DDoS/WAF policy, secret rotation, monitoring, and
  incident response still require account-owner operational review.
- At this review date, the Python 3.14.7 API and worker images have four
  unsuppressed medium/low CPython findings for which Grype lists only unreleased
  CPython 3.15 builds as fixes. They are not acceptable as a reason to use a
  pre-release runtime; reassess them immediately when a supported release ships.
