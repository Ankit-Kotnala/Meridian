# Free-tier deployment runbook

This runbook is the cheapest practical way to put Meridian online as a public
demo without running the local Docker Compose stack in the cloud.

The first deployment target is:

```text
Render Web Service: meridian-api
Render Web Service: meridian-web
Supabase Free: Postgres
Upstash Free: Redis
Cloudflare R2 or another S3-compatible free bucket: document storage
Gmail/Brevo/Resend free SMTP: transactional email
```

Railway is not the first choice for a no-money deployment because its current
free path is trial/credit based. Cloudflare is excellent for static/edge work,
but this repo currently has a Python API and server-side Next.js BFF route, so
Render is the lowest-friction first deploy.

## 1. Create managed services

Create these first, then keep their connection strings ready.

1. Supabase project
   - Create a free project.
   - Copy the database connection string.
   - Convert it for the API from `postgresql://...` to
     `postgresql+asyncpg://...`.
   - Enable the `vector` extension in SQL editor:

```sql
create extension if not exists vector;
```

2. Upstash Redis
   - Create a free Redis database.
   - Copy the TLS URL. It must start with `rediss://`.

3. Object storage
   - Prefer Cloudflare R2 if available.
   - Create a private bucket, for example `meridian-documents`.
   - Create an S3 access key.
   - Use:
     - `REZUMI_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com`
     - `REZUMI_S3_REGION=auto`
     - `REZUMI_S3_BUCKET=meridian-documents`
     - `REZUMI_S3_USE_SSL=true`

4. SMTP
   - Use a free SMTP provider or Gmail app password.
   - The API refuses public startup with local/dev email settings.

## 2. Deploy the API on Render

Create a new Render **Web Service** from the GitHub repo.

Use these settings:

```text
Name: meridian-api
Environment: Docker
Region: Singapore, or the same region as the web service
Branch: development, or your deployment branch
Root Directory: leave empty
Dockerfile Path: backend/api/Dockerfile
Docker Context Directory: .
Health Check Path: /health
```

Use this Docker command so migrations run before the API starts:

```sh
alembic -c backend/core/alembic.ini upgrade head && python -m uvicorn rezumi_api.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Set these environment variables on `meridian-api`:

```dotenv
REZUMI_ENVIRONMENT=staging
REZUMI_DEBUG=false
REZUMI_DOCS_ENABLED=false
REZUMI_LOG_LEVEL=INFO
REZUMI_TRUSTED_HOSTS=["meridian-api.onrender.com"]
REZUMI_ALLOWED_ORIGINS=["https://meridian-web.onrender.com"]
REZUMI_PUBLIC_APP_URL=https://meridian-web.onrender.com
REZUMI_COOKIE_SECURE=true

REZUMI_DATABASE_URL=postgresql+asyncpg://...
REZUMI_REDIS_URL=rediss://...

REZUMI_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
REZUMI_S3_PUBLIC_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
REZUMI_S3_REGION=auto
REZUMI_S3_BUCKET=meridian-documents
REZUMI_S3_ACCESS_KEY_ID=...
REZUMI_S3_SECRET_ACCESS_KEY=...
REZUMI_S3_USE_SSL=true

REZUMI_EMAIL_PROVIDER=smtp
REZUMI_SMTP_HOST=smtp.gmail.com
REZUMI_SMTP_PORT=587
REZUMI_SMTP_USERNAME=...
REZUMI_SMTP_PASSWORD=...
REZUMI_SMTP_START_TLS=true
REZUMI_EMAIL_FROM_ADDRESS=...

REZUMI_GOOGLE_OAUTH_ENABLED=true
REZUMI_GOOGLE_CLIENT_ID=...
REZUMI_GOOGLE_CLIENT_SECRET=...
REZUMI_GOOGLE_REDIRECT_URI=https://meridian-web.onrender.com/api/v1/auth/google/callback

REZUMI_AUTH_TOKEN_PEPPER=<generate-32-plus-random-chars>
REZUMI_RESUME_CAPABILITY_PEPPER=<generate-32-plus-random-chars>
REZUMI_BFF_CLIENT_SIGNAL_SECRET=<generate-32-plus-random-chars>

REZUMI_JOB_DELIVERY_PROVIDER=celery
REZUMI_CELERY_BROKER_URL=rediss://...
REZUMI_MONGODB_ENABLED=false
REZUMI_AI_PROVIDER=disabled
```

Do not paste values from local `.env` into Git. Put them only in Render's
environment variable UI.

## 3. Deploy the web app on Render

Create a second Render **Web Service** from the same GitHub repo.

Use these settings:

```text
Name: meridian-web
Environment: Docker
Region: same as API
Branch: development, or your deployment branch
Root Directory: leave empty
Dockerfile Path: frontend/web/Dockerfile
Docker Context Directory: .
Health Check Path: /api/health
```

Set these environment variables on `meridian-web`:

```dotenv
REZUMI_ENVIRONMENT=staging
API_BASE_URL=https://meridian-api.onrender.com
API_BFF_CLIENT_SIGNAL_SECRET=<same value as REZUMI_BFF_CLIENT_SIGNAL_SECRET>
API_TRUSTED_CLIENT_IP_HEADER=x-forwarded-for
NEXT_PUBLIC_APP_URL=https://meridian-web.onrender.com
NEXT_PUBLIC_UPLOAD_ORIGIN=https://<account-id>.r2.cloudflarestorage.com
```

## 4. Update Google OAuth

In Google Cloud Console, update the OAuth client:

```text
Authorized JavaScript origin:
https://meridian-web.onrender.com

Authorized redirect URI:
https://meridian-web.onrender.com/api/v1/auth/google/callback
```

The local callback can remain for development:

```text
http://localhost:3000/api/v1/auth/google/callback
```

## 5. Important free-tier limitation

Public file upload processing needs a malware scanner. This code intentionally
fails closed for public environments when ClamAV is not configured. That is the
right security behavior.

For a fully usable public demo with resume uploads, add a reachable ClamAV host
and set:

```dotenv
REZUMI_MALWARE_SCANNER_PROVIDER=clamav
REZUMI_CLAMAV_HOST=<private-or-protected-clamav-host>
REZUMI_CLAMAV_PORT=3310
```

Do not expose ClamAV directly to the public internet. If you cannot host ClamAV
for free yet, keep upload functionality off for public users and demo the
platform with seeded/sample data until scanning is available.

## 6. Smoke test

After both services deploy:

1. Open `https://meridian-api.onrender.com/health`.
2. Open `https://meridian-api.onrender.com/ready`.
3. Open `https://meridian-web.onrender.com/api/health`.
4. Try Google sign-in.
5. Confirm the browser stays on the web domain after callback.
6. Check Render logs for `Unsafe public configuration`; if present, fix the
   listed environment variable instead of bypassing the guard.

## 7. Later migration to Cloudflare

After Render is working, move the web layer to Cloudflare Pages/Workers only if
the Next.js runtime compatibility is verified. Keep the Python API on Render or
another Python host unless the backend is intentionally migrated to Workers.
