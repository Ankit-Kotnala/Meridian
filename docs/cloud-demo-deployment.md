# Cloud-portable demo deployment

This profile keeps the product's durable job model while avoiding a permanent
Celery worker/scheduler in hosted demo environments. It is designed for a
public portfolio/demo deployment, not an approved production release.

## Target topology

```text
Cloudflare Workers (Next.js) ──same-origin BFF──> API (Railway/Render)
                                                  │
QStash ─signed HTTPS─> Job runner (Railway/Render)┤──> PostgreSQL + pgvector
                                                  └──> Cloudflare R2
```

Use a normal Python container host for the API and job runner. Cloudflare
Workers can host the Next.js edge/front-end path, but cannot run the existing
Python PDF/DOCX parsing and ClamAV work.

## Required managed services

| Concern                | Recommended demo provider      | Notes                                                                                  |
| ---------------------- | ------------------------------ | -------------------------------------------------------------------------------------- |
| Frontend               | Cloudflare Workers             | First run the framework compatibility check; keep current Next deployment as fallback. |
| API and job runner     | Railway or Render              | Two separate public HTTPS services.                                                    |
| SQL                    | Neon or Supabase Postgres      | Enable `vector` before applying migrations.                                            |
| Document/catalog store | MongoDB Atlas                  | Required when `MONGODB_ENABLED=true`, including the hosted job-catalog source.         |
| Object storage         | Cloudflare R2                  | S3-compatible; private bucket; exact CORS origin only.                                 |
| Background delivery    | Upstash QStash                 | Queue messages are UUID-only and QStash-signed.                                        |
| Email                  | Resend or another SMTP service | Configure SMTP and a verified sender domain.                                           |
| Malware scanning       | Isolated ClamAV host           | Required to allow public file uploads.                                                 |

Do not configure a demo deployment with `MALWARE_SCANNER_PROVIDER=disabled` and
claim that uploads are safe. It fails closed by design.

`staging` is a public environment in Rezumi. It has the same secure configuration
requirements as `production`; it is not a permissive halfway mode. An API or
worker with a local default, a missing secret, or an unencrypted public-service
connection refuses to start instead of accepting user data unsafely.

## API service

Build from the repository root with Dockerfile `backend/api/Dockerfile`.

Use a public hostname such as `https://api-staging.example.com` and set:

```dotenv
REZUMI_ENVIRONMENT=staging
REZUMI_DEBUG=false
REZUMI_DOCS_ENABLED=false
REZUMI_LOG_LEVEL=INFO
REZUMI_TRUSTED_HOSTS=["api-staging.example.com"]
REZUMI_ALLOWED_ORIGINS=["https://app-staging.example.com"]
REZUMI_PUBLIC_APP_URL=https://app-staging.example.com
REZUMI_COOKIE_SECURE=true

REZUMI_DATABASE_URL=postgresql+asyncpg://...
REZUMI_REDIS_URL=rediss://...  # sessions and rate limiting; TLS is required
REZUMI_MONGODB_ENABLED=true  # required to retain the hosted job-catalog source
REZUMI_MONGODB_URL=mongodb+srv://...
REZUMI_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
REZUMI_S3_PUBLIC_ENDPOINT_URL=https://uploads-staging.example.com
REZUMI_S3_REGION=auto
REZUMI_S3_BUCKET=rezumi-documents
REZUMI_S3_ACCESS_KEY_ID=<R2 access key>
REZUMI_S3_SECRET_ACCESS_KEY=<R2 secret>
REZUMI_S3_USE_SSL=true

REZUMI_EMAIL_PROVIDER=smtp
REZUMI_SMTP_HOST=smtp.resend.com
REZUMI_SMTP_PORT=587
REZUMI_SMTP_USERNAME=resend
REZUMI_SMTP_PASSWORD=<SMTP credential>
REZUMI_SMTP_START_TLS=true
REZUMI_EMAIL_FROM_ADDRESS=no-reply@example.com

REZUMI_MALWARE_SCANNER_PROVIDER=clamav
REZUMI_CLAMAV_HOST=clamav.internal.example.com
REZUMI_CLAMAV_PORT=3310

REZUMI_AUTH_TOKEN_PEPPER=<at-least-32-random-UTF-8-bytes>
REZUMI_RESUME_CAPABILITY_PEPPER=<at-least-32-random-UTF-8-bytes>
REZUMI_BFF_CLIENT_SIGNAL_SECRET=<at-least-32-random-UTF-8-bytes>

REZUMI_JOB_DELIVERY_PROVIDER=qstash
REZUMI_QSTASH_TOKEN=<publish token>
REZUMI_QSTASH_JOB_RUNNER_URL=https://jobs-staging.example.com/internal/jobs/qstash
REZUMI_QSTASH_BASE_URL=https://qstash.upstash.io
REZUMI_QSTASH_RETRIES=3
REZUMI_QSTASH_DELIVERY_TIMEOUT_SECONDS=330
```

Use a secret manager or protected platform environment variables for every
placeholder above. Do not copy a value from `.env.example`, put secrets in a
`NEXT_PUBLIC_*` variable, share them in screenshots, or commit them to Git.
The S3 bucket must remain private; `S3_PUBLIC_ENDPOINT_URL` names the browser
upload origin and does not make stored objects public.

Configure the same MongoDB values on the runner if it executes catalog sync
tasks. If no Atlas database is available, set `MONGODB_ENABLED=false`; the
application can start, but the Mongo-backed job-catalog ingestion capability is
intentionally unavailable rather than silently losing data.

## Job runner service

Build from the repository root with `backend/worker/Dockerfile`. Set the same
database/S3/scanner/QStash variables as the API, plus:

```dotenv
REZUMI_ENVIRONMENT=staging
REZUMI_LOG_LEVEL=INFO
REZUMI_DATABASE_URL=postgresql+asyncpg://...
REZUMI_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
REZUMI_S3_PUBLIC_ENDPOINT_URL=https://uploads-staging.example.com
REZUMI_S3_REGION=auto
REZUMI_S3_BUCKET=rezumi-documents
REZUMI_S3_ACCESS_KEY_ID=<R2 access key>
REZUMI_S3_SECRET_ACCESS_KEY=<R2 secret>
REZUMI_S3_USE_SSL=true
REZUMI_MALWARE_SCANNER_PROVIDER=clamav
REZUMI_CLAMAV_HOST=clamav.internal.example.com
REZUMI_CLAMAV_PORT=3310

REZUMI_JOB_DELIVERY_PROVIDER=qstash
REZUMI_QSTASH_TOKEN=<publish token>
REZUMI_QSTASH_JOB_RUNNER_URL=https://jobs-staging.example.com/internal/jobs/qstash
REZUMI_QSTASH_CURRENT_SIGNING_KEY=<current receiver key>
REZUMI_QSTASH_NEXT_SIGNING_KEY=<next receiver key>
```

The image automatically starts the HTTP runner when
`JOB_DELIVERY_PROVIDER=qstash`. Set the host health-check path to `/health`.
Never expose ClamAV directly to the public internet.

## Web service

Set these **server-only** values on the Next.js deployment. The BFF secret must
exactly equal `REZUMI_BFF_CLIENT_SIGNAL_SECRET` on the API, but it must never be
published with the `NEXT_PUBLIC_` prefix.

```dotenv
REZUMI_ENVIRONMENT=staging
API_BASE_URL=https://api-staging.example.com
API_BFF_CLIENT_SIGNAL_SECRET=<same value as REZUMI_BFF_CLIENT_SIGNAL_SECRET>
API_TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip
NEXT_PUBLIC_UPLOAD_ORIGIN=https://uploads-staging.example.com
```

Use the client-address header set by your chosen edge only. For example,
Cloudflare sets `CF-Connecting-IP`; a platform that supplies only
`X-Forwarded-For` must use `x-forwarded-for`. Do not allow a client to select the
header, and do not forward arbitrary client-supplied forwarding headers.

## Public deployment verification

Before allowing real users, verify the following through the deployed HTTPS
domains, not only localhost:

1. Both API and runner start with no `Unsafe public configuration` error.
2. An API response includes `Cache-Control: no-store`, `X-Content-Type-Options:
nosniff`, anti-framing policy, and HSTS. The web response has its CSP and
   security headers too.
3. The API accepts only the exact application origin; a request with a different
   `Origin` cannot complete a state-changing operation.
4. Private object URLs deny anonymous reads, and a signed upload/download URL
   expires when expected.
5. The malware scanner is reachable only from private application services; an
   EICAR test file is rejected and never parsed.
6. Logs, error pages, job messages, browser source, and deployment previews do
   not contain credentials, tokens, raw resumes, signed URLs, or document text.
7. Rotate one non-production secret and verify that a stale session/job signature
   is rejected. Maintain a written, owner-controlled rotation runbook.

## Create schedules once

After the runner is publicly available, run this as a one-off command in the
job-runner service:

```sh
python -m rezumi_worker.scripts.configure_qstash_schedules
```

It creates/replaces two schedules with fixed IDs:

- `rezumi-maintenance-v1`: every 15 minutes; dispatches and reconciles durable
  outboxes, cleanup, and local reminder materialization.
- `rezumi-job-catalog-v1`: daily at 03:17 UTC.

The Upstash free tier's current 1,000 messages/day and 10 active-schedule limits
make this reasonable only for a modest demo. Monitor the queue dashboard and
dead-letter queue. See [QStash pricing](https://upstash.com/pricing/qstash) and
[signature verification](https://upstash.com/docs/qstash/howto/signature).

## Rollback

Pause/delete those schedules in QStash, set both API and runner back to
`JOB_DELIVERY_PROVIDER=celery`, and bring up the existing `worker` and
`worker-scheduler` Compose services. Data remains in the durable PostgreSQL
outboxes; no database rollback is required.
