# CareerOS web

Next.js App Router frontend for the CareerOS public experience, Phase 1
authentication/onboarding workspace, and isolated fictional product preview.

## Commands

Run these from the repository root:

```bash
pnpm --filter @careeros/web dev
pnpm --filter @careeros/web lint
pnpm --filter @careeros/web typecheck
pnpm --filter @careeros/web test
pnpm --filter @careeros/web build
pnpm --filter @careeros/web test:e2e
```

The health endpoint is `GET /api/health`. Public auth routes include `/register`,
`/verify-email`, `/login`, `/forgot-password`, `/reset-password`, and
`/get-started`. `/dashboard`, `/onboarding`, `/settings`, `/settings/sessions`, and
`/settings/consent` are protected and use persisted API state. The real dashboard
intentionally renders an empty state until Phase 2; fictional fixtures are
isolated at `/demo/dashboard`.

Browser API traffic uses the strict same-origin `/api/v1/*` proxy. Its upstream
base is server-only, redirects and forwarded headers are allowlisted, and session
authority remains in HTTP-only API cookies. Do not introduce local-storage bearer
tokens or memoize current-user lookups across requests. The package-level
`test:e2e` command targets an already running web/API stack; use the repository's
isolated full-stack runner for phase verification.

The Dockerfile expects the repository root as its build context:

```bash
docker build -f apps/web/Dockerfile -t careeros-web .
docker run --rm -p 3000:3000 careeros-web
```
