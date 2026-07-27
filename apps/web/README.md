# CareerOS web

Next.js App Router frontend for the CareerOS public experience, Phase 1
authentication/onboarding workspace, Phase 2 Resume Health workflow, and
isolated fictional product preview.

## Commands

Run these from the repository root:

```bash
pnpm dev:web       # backend containers plus Next.js hot reload
pnpm test:web      # focused web tests
pnpm --filter @careeros/web lint
pnpm --filter @careeros/web typecheck
pnpm --filter @careeros/web build
pnpm --filter @careeros/web test:e2e
```

Product behavior lives under `src/modules/<feature>`; App Router files remain
thin delivery shells. Reusable application-neutral components belong in
`packages/ui`. See `docs/local-development.md` for the complete repository map,
Docker rebuild rules, and full-stack workflows.

The health endpoint is `GET /api/health`. Public auth routes include `/register`,
`/verify-email`, `/login`, `/forgot-password`, `/reset-password`, and
`/get-started`. `/dashboard`, `/onboarding`, `/settings`, `/settings/sessions`, and
`/settings/consent`, `/resume-health/account`, and its document workflow routes
are protected and use persisted API state. `/resume-health/guest` provides the
short-lived guest workflow. The real dashboard summarizes the latest persisted
resume processing or analysis state; fictional fixtures remain isolated at
`/demo/dashboard`.

Browser API traffic uses the strict same-origin `/api/v1/*` proxy. Its upstream
base is server-only, redirects and forwarded headers are allowlisted, and session
authority remains in HTTP-only API cookies. Do not introduce local-storage bearer
tokens or memoize current-user lookups across requests. The package-level
`test:e2e` command targets an already running web/API stack; use the repository's
isolated full-stack runner for phase verification.

Resume bytes bypass the application proxy and upload only to the exact object
storage origin configured by `NEXT_PUBLIC_UPLOAD_ORIGIN`; admission, finalization,
parsing, review, analysis, report access, claiming, and durable deletion still go
through the same-origin API proxy. Keep the public upload origin aligned with the
web Content Security Policy and storage CORS policy.

The Dockerfile expects the repository root as its build context:

```bash
docker build -f apps/web/Dockerfile -t careeros-web .
docker run --rm -p 3000:3000 careeros-web
```
