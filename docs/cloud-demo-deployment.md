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

## API service

Build from the repository root with Dockerfile `backend/api/Dockerfile`.

Use a public hostname such as `https://api-staging.example.com` and set:

```dotenv
REZUMI_ENVIRONMENT=staging
JOB_DELIVERY_PROVIDER=qstash
QSTASH_TOKEN=<publish token>
QSTASH_JOB_RUNNER_URL=https://jobs-staging.example.com/internal/jobs/qstash
QSTASH_BASE_URL=https://qstash.upstash.io
QSTASH_RETRIES=3
QSTASH_DELIVERY_TIMEOUT_SECONDS=330

REZUMI_DATABASE_URL=postgresql+asyncpg://...
REZUMI_REDIS_URL=rediss://...  # still used for sessions/rate limiting
MONGODB_ENABLED=true  # required to retain the hosted job-catalog source
MONGODB_URL=mongodb+srv://...
REZUMI_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
REZUMI_S3_PUBLIC_ENDPOINT_URL=https://uploads-staging.example.com
REZUMI_S3_REGION=auto
REZUMI_S3_BUCKET=rezumi-documents
REZUMI_S3_ACCESS_KEY_ID=<R2 access key>
REZUMI_S3_SECRET_ACCESS_KEY=<R2 secret>
REZUMI_S3_USE_SSL=true
REZUMI_ALLOWED_ORIGINS=["https://app-staging.example.com"]
REZUMI_PUBLIC_APP_URL=https://app-staging.example.com
REZUMI_COOKIE_SECURE=true
```

Use strong generated values for `AUTH_TOKEN_PEPPER`,
`RESUME_CAPABILITY_PEPPER`, and `BFF_CLIENT_SIGNAL_SECRET`. Do not copy values
from `.env.example`.

Configure the same MongoDB values on the runner if it executes catalog sync
tasks. If no Atlas database is available, set `MONGODB_ENABLED=false`; the
application can start, but the Mongo-backed job-catalog ingestion capability is
intentionally unavailable rather than silently losing data.

## Job runner service

Build from the repository root with `backend/worker/Dockerfile`. Set the same
database/S3/scanner/QStash variables as the API, plus:

```dotenv
REZUMI_ENVIRONMENT=staging
JOB_DELIVERY_PROVIDER=qstash
QSTASH_TOKEN=<publish token>
QSTASH_JOB_RUNNER_URL=https://jobs-staging.example.com/internal/jobs/qstash
QSTASH_CURRENT_SIGNING_KEY=<current receiver key>
QSTASH_NEXT_SIGNING_KEY=<next receiver key>
```

The image automatically starts the HTTP runner when
`JOB_DELIVERY_PROVIDER=qstash`. Set the host health-check path to `/health`.
Never expose ClamAV directly to the public internet.

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
