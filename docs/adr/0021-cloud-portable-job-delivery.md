# ADR 0021: Cloud-portable HTTP job delivery

- Status: Accepted for staging/demo deployment; production approval remains open
- Date: 2026-09-28
- Deciders: Engineering

## Context

Local Compose runs Redis, Celery workers, Celery Beat, MinIO, Mailpit, and
ClamAV alongside the API and web application. That is a productive local
topology, but a poor fit for low-cost hosted platforms: a permanent worker and
scheduler require paid compute, and a public web service must not accept
unauthenticated task requests.

The product already stores job ownership, idempotency, fences, outboxes,
attempts, retries, and dead-letter state in PostgreSQL. Queue messages carry
only durable identifiers.

## Decision

Keep Docker Compose and the Celery transport for local development. Add an
opt-in QStash delivery profile for hosted staging/demo environments:

```text
API / job runner → transactional outbox → QStash → signed worker HTTP endpoint
                                      ↘ PostgreSQL durable job state
```

- QStash uses authenticated REST publishing and QStash's signed JWT delivery.
- The worker owns a small FastAPI job-runner endpoint; the public API never
  imports worker code.
- The endpoint verifies the raw request body, exact public URL, issuer, expiry,
  and JWT HMAC signature before parsing an allowlisted UUID-only envelope.
- QStash delivery is bounded and retryable. Database job leases, idempotency,
  and outboxes remain the source of truth for duplicate or delayed delivery.
- Two deterministic schedules are created by an explicit one-off command:
  a 15-minute maintenance sweep and a daily job-catalog refresh. This stays
  within a small demo account's schedule/message budget.
- Object storage remains S3-compatible, so Cloudflare R2 can replace MinIO by
  configuration rather than a code rewrite.

The cloud job runner is a normal HTTP container. Deploy it to a service that
can execute Python work for the configured time limit (for example Railway or
Render). Cloudflare serves the Next.js edge/frontend path and R2; it does not
run this Python document-processing worker.

## Security and privacy controls

- No resume, evidence, document text, credentials, or signed object URL enters
  QStash; only UUIDs, task names, and redacted trace IDs are sent.
- QStash request bodies are redacted in QStash operational logs.
- The runner rejects unsigned, expired, altered, malformed, or unknown tasks.
- Replays are harmless only because all job processors retain their existing
  ownership, version, lease, and idempotency checks. The short QStash signature
  expiry narrows the replay window.
- ClamAV remains fail-closed. A public deployment must provide a reachable,
  isolated scanner. This ADR does not weaken upload security merely to fit a
  free serverless tier.

## Rollout and rollback

1. Deploy API and runner with `JOB_DELIVERY_PROVIDER=celery`; no behavior changes.
2. Configure managed PostgreSQL/R2, then deploy the runner with QStash
   credentials and verify `/health`.
3. Create the two schedules and send one signed test job.
4. Switch API and runner together to `JOB_DELIVERY_PROVIDER=qstash`.
5. Watch outbox age, QStash DLQ, job retry/dead-letter counts, and upload paths.

Rollback is configuration-only: pause/delete the two QStash schedules, switch
both services back to `celery`, then start the existing worker and scheduler.
No destructive migration or data rewrite is required.

## Consequences

### Positive

- The web/API and worker can be deployed independently and moved between
  Render, Railway, or another conventional container host.
- No Redis/Celery worker/scheduler is required in the QStash profile.
- Local development remains reproducible and independent of cloud credentials.

### Costs and risks

- This is a staging/demo topology, not a declaration of production readiness.
- Free provider quotas and cold starts make it unsuitable for a guaranteed SLA.
- ClamAV still requires a real isolated runtime; there is no safe purely-free
  serverless substitute for scanning untrusted public uploads.
- Managed database, storage, email, backup, and scanner configuration require
  separate protected-environment review before public production use.
